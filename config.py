import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot Token
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # CoinPayments API
    COINPAYMENTS_PUBLIC_KEY = os.getenv('COINPAYMENTS_PUBLIC_KEY')
    COINPAYMENTS_PRIVATE_KEY = os.getenv('COINPAYMENTS_PRIVATE_KEY')
    COINPAYMENTS_MERCHANT_ID = os.getenv('COINPAYMENTS_MERCHANT_ID')
    COINPAYMENTS_IPN_SECRET = os.getenv('COINPAYMENTS_IPN_SECRET')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///payments.db')
    
    # Bot Settings
    MIN_SEND_AMOUNT = 0.01  # Minimum send amount in USD
    TRANSACTION_FEE = 0.01  # 1% transaction fee
