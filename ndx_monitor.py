import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_config():
    """获取配置参数（优先从环境变量读取）"""
    return {
        'TICKER': '^NDX',
        'ALERT_THRESHOLD': float(os.getenv('ALERT_THRESHOLD', -0.03)),
        'SMTP_SERVER': os.getenv('SMTP_SERVER'),
        'SMTP_PORT': int(os.getenv('SMTP_PORT', 587)),
        'EMAIL_FROM': os.getenv('EMAIL_FROM'),
        'EMAIL_TO': os.getenv('EMAIL_TO'),
        'SMTP_USERNAME': os.getenv('SMTP_USERNAME'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD'),
        'DATA_FILE': 'ndx_daily.csv'
    }

def get_market_data(ticker):
    """获取最新市场数据（仅限最近一个交易日）"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')  # 获取最近5天以防周末/节假日
        if hist.empty:
            print("未获取到任何历史数据")
            return None
        latest = hist.iloc[-1]
        latest_date = latest.name  # pandas Timestamp, tz-aware or naive
        # 转为 UTC 日期用于比较
        if latest_date.tz is None:
            latest_date = latest_date.tz_localize('UTC')
        else:
            latest_date = latest_date.tz_convert('UTC')
        today_utc = datetime.now(timezone.utc).date()
        if latest_date.date() != today_utc:
            print(f"最新交易日 {latest_date.date()} 不是今天（{today_utc}），跳过处理（可能是周末或节假日）")
            return None
        return latest
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None

def send_alert(config, current_data):
    """发送价格警报邮件"""
    try:
        change_pct = (current_data['Close'] - current_data['Open']) / current_data['Open']
        msg = MIMEMultipart()
        msg['From'] = config['EMAIL_FROM']
        msg['To'] = config['EMAIL_TO']
        msg['Subject'] = f"NDX警报: 单日跌幅{change_pct*100:.2f}%"
        body = f"""纳斯达克100指数异常波动：
开盘价: {current_data['Open']:.2f}
收盘价: {current_data['Close']:.2f}
涨跌幅: {change_pct*100:.2f}%
最高价: {current_data['High']:.2f}
最低价: {current_data['Low']:.2f}
成交量: {current_data['Volume']:,.0f}
"""
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT']) as server:
            server.starttls()
            server.login(config['SMTP_USERNAME'], config['SMTP_PASSWORD'])
            server.send_message(msg)
        print("警报邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def save_data(config, data):
    """保存每日数据到CSV（避免重复）"""
    try:
        df_new = pd.DataFrame([data])
        if os.path.exists(config['DATA_FILE']):
            existing = pd.read_csv(config['DATA_FILE'], parse_dates=['Date'])
            # 检查是否已存在当天数据
            if data['Date'] in existing['Date'].dt.strftime('%Y-%m-%d').values:
                print(f"今日数据（{data['Date']}）已存在，跳过保存")
                return
            df = pd.concat([existing, df_new], ignore_index=True)
        else:
            df = df_new
        df.to_csv(config['DATA_FILE'], index=False, date_format='%Y-%m-%d')
        print(f"数据已保存至 {config['DATA_FILE']}")
    except Exception as e:
        print(f"数据保存失败: {e}")

def main():
    config = get_config()
    required = ['SMTP_SERVER', 'EMAIL_FROM', 'EMAIL_TO', 'SMTP_USERNAME', 'SMTP_PASSWORD']
    if any(config[k] is None for k in required):
        print("缺少必要的邮件配置参数，请检查 secrets 设置")
        return

    current_data = get_market_data(config['TICKER'])
    if current_data is None:
        return

    daily_change = (current_data['Close'] - current_data['Open']) / current_data['Open']

    # 检查是否触发警报
    if daily_change <= config['ALERT_THRESHOLD']:
        send_alert(config, current_data)

    # 保存数据（save_data 内部会去重）
    save_data(config, {
        'Date': current_data.name.strftime('%Y-%m-%d'),
        'Open': current_data['Open'],
        'High': current_data['High'],
        'Low': current_data['Low'],
        'Close': current_data['Close'],
        'Volume': current_data['Volume'],
        'Change': daily_change
    })

if __name__ == "__main__":
    main()
