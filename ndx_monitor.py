import os
from datetime import datetime
import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

def get_config():
    """获取配置参数，优先从环境变量读取"""
    return {
        'TICKER': '^NDX',
        'ALERT_THRESHOLD': -0.03,  # 大跌阈值 -3%
        'SMTP_SERVER': os.getenv('SMTP_SERVER', 'smtp.example.com'),  # 从环境变量读取或使用默认值
        'SMTP_PORT': int(os.getenv('SMTP_PORT', 587)),
        'EMAIL_FROM': os.getenv('EMAIL_FROM', 'your_email@example.com'),
        'EMAIL_TO': os.getenv('EMAIL_TO', 'your_alert_email@example.com'),
        'SMTP_USERNAME': os.getenv('SMTP_USERNAME', 'your_email@example.com'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD', 'your_email_password'),
        'DATA_FILE': 'ndx_daily_data.csv',
        'MAX_RETRIES': 3,
        'RETRY_DELAY': 300  # 重试间隔(秒)
    }

def send_alert_email(config, subject, message):
    """发送警报邮件"""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['EMAIL_FROM']
        msg['To'] = config['EMAIL_TO']
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT']) as server:
            server.starttls()
            server.login(config['SMTP_USERNAME'], config['SMTP_PASSWORD'])
            server.send_message(msg)
        print("警报邮件发送成功")
    except Exception as e:
        print(f"发送邮件失败: {e}")

def main():
    config = get_config()
    
    # 获取当天数据逻辑
    # ...
    
    # 大跌检查逻辑
    if daily_change <= config['ALERT_THRESHOLD']:
        subject = f"NDX大跌警报: {daily_change*100:.2f}%"
        message = f"纳斯达克100指数今日下跌{daily_change*100:.2f}%\n开盘价: {open_price}\n收盘价: {close_price}"
        send_alert_email(config, subject, message)

if __name__ == "__main__":
    main()
