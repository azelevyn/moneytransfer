from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    account_number = Column(String, unique=True, index=True)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    tx_id = Column(String, unique=True, index=True)
    from_user_id = Column(String, nullable=True)
    to_user_id = Column(String, nullable=True)
    amount = Column(Float)
    currency = Column(String)
    status = Column(String)  # pending, completed, failed
    type = Column(String)  # send, receive, deposit
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Deposit(Base):
    __tablename__ = "deposits"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    amount = Column(Float)
    currency = Column(String)
    address = Column(String)
    tx_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, confirmed, completed
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_account_number(telegram_id):
    """Generate IBAN-like account number"""
    import hashlib
    import time
    
    seed = f"{telegram_id}{time.time()}"
    hash_obj = hashlib.md5(seed.encode()).hexdigest().upper()
    return f"TB{hash_obj[:18]}"
