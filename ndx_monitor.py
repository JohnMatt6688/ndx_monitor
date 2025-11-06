import os
import io
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone
import smtplib, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# =============================
#  配置监控的指数
# =============================
INDEXES = {
    "^NDX": "纳斯达克100",
    "^GSPC": "标普500",
    "^DJI": "道琼斯工业指数"
}

# =============================
#  获取配置（从环境变量）
# =============================
def get_config():
    return {
        'ALERT_THRESHOLD': float(os.getenv('ALERT_THRESHOLD', -0.03)),
        'SMTP_SERVER': os.getenv('SMTP_SERVER'),
        'SMTP_PORT': int(os.getenv('SMTP_PORT', 587)),
        'EMAIL_FROM': os.getenv('EMAIL_FROM'),
        'EMAIL_TO': os.getenv('EMAIL_TO'),
        'SMTP_USERNAME': os.getenv('SMTP_USERNAME'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD'),
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
        'DISCORD_WEBHOOK_URL': os.getenv('DISCORD_WEBHOOK_URL'),
        'WECHAT_WEBHOOK_URL': os.getenv('WECHAT_WEBHOOK_URL'),
        'DATA_FILE': 'market_daily.csv'
    }

# =============================
#  获取行情数据
# =============================
def get_latest_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")
    if hist.empty:
        print(f"❌ {ticker} 无数据")
        return None
    latest = hist.iloc[-1]
    latest_date = latest.name.tz_convert('UTC').date()
    today_utc = datetime.now(timezone.utc).date()
    if latest_date != today_utc:
        print(f"📅 {ticker} 最新日期 {latest_date} ≠ {today_utc}，跳过")
        return None
    return latest, hist

# =============================
#  生成走势图
# =============================
def make_chart(ticker, hist):
    fig, ax = plt.subplots(figsize=(6, 4))
    hist['Close'].plot(ax=ax, linewidth=2)
    ax.set_title(f"{INDEXES[ticker]} 近7日走势", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# =============================
#  邮件发送函数
# =============================
def send_email(config, subject, body, charts):
    if not config['SMTP_SERVER']:
        print("⚠️ 未配置 SMTP，跳过邮件发送")
        return
    msg = MIMEMultipart()
    msg['From'] = config['EMAIL_FROM']
    msg['To'] = config['EMAIL_TO']
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    for name, chart in charts.items():
        img = MIMEImage(chart.read())
        img.add_header('Content-ID', f"<{name}>")
        msg.attach(img)
    try:
        with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT']) as s:
            s.starttls()
            s.login(config['SMTP_USERNAME'], config['SMTP_PASSWORD'])
            s.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# =============================
#  其他推送方式
# =============================
def send_telegram(config, text):
    if not config['TELEGRAM_BOT_TOKEN']:
        return
    url = f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/sendMessage"
    try:
        requests.post(url, data={'chat_id': config['TELEGRAM_CHAT_ID'], 'text': text})
        print("✅ Telegram 推送成功")
    except Exception as e:
        print(f"❌ Telegram 推送失败: {e}")

def send_discord(config, text):
    if config['DISCORD_WEBHOOK_URL']:
        try:
            requests.post(config['DISCORD_WEBHOOK_URL'], json={"content": text})
            print("✅ Discord 推送成功")
        except Exception as e:
            print(f"❌ Discord 推送失败: {e}")

def send_wechat(config, text):
    if config['WECHAT_WEBHOOK_URL']:
        try:
            requests.post(config['WECHAT_WEBHOOK_URL'], json={
                "msgtype": "text",
                "text": {"content": text}
            })
            print("✅ 企业微信推送成功")
        except Exception as e:
            print(f"❌ 企业微信推送失败: {e}")

# =============================
#  保存 CSV
# =============================
def save_data(config, rows):
    df_new = pd.DataFrame(rows)
    if os.path.exists(config['DATA_FILE']):
        existing = pd.read_csv(config['DATA_FILE'])
        df = pd.concat([existing, df_new]).drop_duplicates(subset=['Date', 'Ticker'])
    else:
        df = df_new
    df.to_csv(config['DATA_FILE'], index=False)
    print(f"💾 数据已保存至 {config['DATA_FILE']}")

# =============================
#  主程序逻辑
# =============================
def main():
    config = get_config()
    all_rows, alerts, charts = [], [], {}
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for ticker in INDEXES:
        result = get_latest_data(ticker)
        if result is None:
            continue
        latest, hist = result
        charts[ticker] = make_chart(ticker, hist)
        change = (latest['Close'] - latest['Open']) / latest['Open']
        row = {
            'Date': today,
            'Ticker': ticker,
            'Name': INDEXES[ticker],
            'Open': latest['Open'],
            'Close': latest['Close'],
            'Change': change
        }
        all_rows.append(row)
        if change <= config['ALERT_THRESHOLD']:
            alerts.append(f"⚠️ {INDEXES[ticker]} 跌幅 {change*100:.2f}%")

    if not all_rows:
        print("⚠️ 今日未获取到任何指数数据，任务结束。")
        return

    save_data(config, all_rows)

    # 构建日报正文
    summary_lines = []
    for r in all_rows:
        summary_lines.append(
            f"{r['Name']} ({r['Ticker']}): 开盘 {r['Open']:.2f}, 收盘 {r['Close']:.2f}, 涨跌幅 {r['Change']*100:.2f}%"
        )
    summary_text = "\n".join(summary_lines)

    if alerts:
        subject = "📉 市场日报（含警报）"
        body = "🚨 触发警报:\n" + "\n".join(alerts) + "\n\n📈 今日指数表现:\n" + summary_text
    else:
        subject = "📈 市场日报（无异常）"
        body = "📊 今日主要指数表现如下：\n" + summary_text

    # 发送多渠道通知
    send_email(config, subject, body, charts)
    send_telegram(config, subject + "\n" + body)
    send_discord(config, subject + "\n" + body)
    send_wechat(config, subject + "\n" + body)

    print("✅ 每日报告发送完成")

# =============================
#  程序入口
# =============================
if __name__ == "__main__":
    main()
