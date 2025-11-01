import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from sqlalchemy.orm import Session
import config
from database import init_db, get_db, User, Transaction, Deposit, generate_account_number
from coinpayments import CoinPaymentsAPI

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PaymentBot:
    def __init__(self):
        self.coinpayments = CoinPaymentsAPI()
        init_db()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message and create user account"""
        user = update.effective_user
        db = next(get_db())
        
        # Check if user exists
        existing_user = db.query(User).filter(User.telegram_id == str(user.id)).first()
        
        if not existing_user:
            # Create new user
            account_number = generate_account_number(user.id)
            new_user = User(
                telegram_id=str(user.id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                account_number=account_number
            )
            db.add(new_user)
            db.commit()
            existing_user = new_user
        
        welcome_message = f"""
👋 Welcome to Crypto Payment Bot, {user.first_name}!

💼 Your Account Number: `{existing_user.account_number}`
💰 Your Balance: ${existing_user.balance:.2f}

📋 Available Commands:
/balance - Check your balance
/deposit - Deposit funds
/send - Send money to another user
/account - Show your account details
/history - View transaction history

💡 To receive money, share your account number with the sender.
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user balance"""
        user = update.effective_user
        db = next(get_db())
        
        user_data = db.query(User).filter(User.telegram_id == str(user.id)).first()
        
        if user_data:
            message = f"""
💰 Your Balance

Account: `{user_data.account_number}`
Balance: ${user_data.balance:.2f}

Use /deposit to add funds or /send to transfer money.
            """
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ User not found. Please use /start to create an account.")
    
    async def show_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show account details"""
        user = update.effective_user
        db = next(get_db())
        
        user_data = db.query(User).filter(User.telegram_id == str(user.id)).first()
        
        if user_data:
            message = f"""
👤 Account Details

Name: {user_data.first_name} {user_data.last_name or ''}
Username: @{user_data.username or 'N/A'}
Account Number: `{user_data.account_number}`
Balance: ${user_data.balance:.2f}

💡 Share your account number to receive payments!
            """
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ User not found. Please use /start to create an account.")
    
    async def deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle deposit command"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("💰 $10", callback_data="deposit_10")],
            [InlineKeyboardButton("💰 $50", callback_data="deposit_50")],
            [InlineKeyboardButton("💰 $100", callback_data="deposit_100")],
            [InlineKeyboardButton("💵 Custom Amount", callback_data="deposit_custom")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💳 Choose deposit amount or enter custom amount:",
            reply_markup=reply_markup
        )
    
    async def handle_deposit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle deposit amount selection"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = query.from_user
        
        if data == "deposit_custom":
            await query.edit_message_text("💵 Please enter the amount you want to deposit (in USD):")
            context.user_data['awaiting_deposit_amount'] = True
            return
        
        amount = float(data.split('_')[1])
        await self.process_deposit(user, amount, context, query.message)
    
    async def process_deposit(self, user, amount, context, message):
        """Process deposit and create CoinPayments transaction"""
        db = next(get_db())
        
        # Create deposit record
        deposit = Deposit(
            user_id=str(user.id),
            amount=amount,
            currency='BTC'  # Default to BTC, you can make this configurable
        )
        db.add(deposit)
        db.commit()
        
        # Create CoinPayments transaction
        result = self.coinpayments.create_transaction(
            amount=amount,
            currency='BTC',  # Accept Bitcoin
            buyer_email='',  # You can collect user email if needed
            item_name=f'Deposit for user {user.id}'
        )
        
        if result['success']:
            # Update deposit with address and tx_id
            deposit.address = result['address']
            deposit.tx_id = result['txn_id']
            db.commit()
            
            message_text = f"""
💰 Deposit Instructions

Amount: ${amount:.2f} USD
Cryptocurrency: BTC
Address: `{result['address']}`
            
⚠️ Send exactly the equivalent of ${amount:.2f} USD in BTC to the address above.
            
⏰ Please complete within {result['timeout']} seconds.
            
🔗 [Payment Status]({result['checkout_url']})
            """
            
            await message.reply_text(message_text, parse_mode='Markdown')
        else:
            await message.reply_text(f"❌ Error creating deposit: {result.get('error', 'Unknown error')}")
    
    async def send_money(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle send money command"""
        if not context.args or len(context.args) != 2:
            await update.message.reply_text(
                "💸 Send Money\n\n"
                "Usage: /send <account_number> <amount>\n"
                "Example: /send TB1234567890ABCDEF 10.50\n\n"
                "💡 Transaction fee: 1%"
            )
            return
        
        recipient_account = context.args[0]
        try:
            amount = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid amount.")
            return
        
        if amount < config.MIN_SEND_AMOUNT:
            await update.message.reply_text(f"❌ Minimum send amount is ${config.MIN_SEND_AMOUNT:.2f}")
            return
        
        await self.process_send_money(update, context, recipient_account, amount)
    
    async def process_send_money(self, update: Update, context: ContextTypes.DEFAULT_TYPE, recipient_account: str, amount: float):
        """Process money transfer between users"""
        user = update.effective_user
        db = next(get_db())
        
        # Get sender
        sender = db.query(User).filter(User.telegram_id == str(user.id)).first()
        if not sender:
            await update.message.reply_text("❌ User not found. Please use /start first.")
            return
        
        # Check balance
        total_amount = amount * (1 + config.TRANSACTION_FEE)
        if sender.balance < total_amount:
            await update.message.reply_text(f"❌ Insufficient balance. You need ${total_amount:.2f} (including 1% fee).")
            return
        
        # Get recipient
        recipient = db.query(User).filter(User.account_number == recipient_account).first()
        if not recipient:
            await update.message.reply_text("❌ Recipient account not found.")
            return
        
        if sender.account_number == recipient_account:
            await update.message.reply_text("❌ You cannot send money to yourself.")
            return
        
        # Process transaction
        try:
            # Deduct from sender
            sender.balance -= total_amount
            
            # Add to recipient (without fee)
            recipient.balance += amount
            
            # Create transaction record
            transaction = Transaction(
                from_user_id=sender.telegram_id,
                to_user_id=recipient.telegram_id,
                amount=amount,
                currency='USD',
                status='completed',
                type='send'
            )
            db.add(transaction)
            db.commit()
            
            # Notify both users
            fee_amount = amount * config.TRANSACTION_FEE
            await update.message.reply_text(
                f"✅ Payment successful!\n\n"
                f"Sent: ${amount:.2f}\n"
                f"To: {recipient.account_number}\n"
                f"Fee: ${fee_amount:.2f}\n"
                f"Total: ${total_amount:.2f}\n"
                f"New Balance: ${sender.balance:.2f}"
            )
            
            # Notify recipient (if bot is active for them)
            try:
                await context.bot.send_message(
                    chat_id=recipient.telegram_id,
                    text=f"💰 You received ${amount:.2f} from {sender.first_name}!\n"
                         f"New Balance: ${recipient.balance:.2f}"
                )
            except Exception as e:
                logger.warning(f"Could not notify recipient: {e}")
                
        except Exception as e:
            db.rollback()
            await update.message.reply_text("❌ Transaction failed. Please try again.")
            logger.error(f"Transaction error: {e}")
    
    async def transaction_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show transaction history"""
        user = update.effective_user
        db = next(get_db())
        
        transactions = db.query(Transaction).filter(
            (Transaction.from_user_id == str(user.id)) | 
            (Transaction.to_user_id == str(user.id))
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        if not transactions:
            await update.message.reply_text("📝 No transactions found.")
            return
        
        history_text = "📊 Last 10 Transactions:\n\n"
        
        for tx in transactions:
            if tx.from_user_id == str(user.id):
                direction = "➡️ Sent"
                amount = f"-${tx.amount:.2f}"
                counterparty = f"To: {tx.to_user_id}"
            else:
                direction = "⬅️ Received"
                amount = f"+${tx.amount:.2f}"
                counterparty = f"From: {tx.from_user_id}"
            
            history_text += f"{direction} {amount}\n{counterparty}\nDate: {tx.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        await update.message.reply_text(history_text)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        user_data = context.user_data
        
        if user_data.get('awaiting_deposit_amount'):
            try:
                amount = float(update.message.text)
                if amount <= 0:
                    await update.message.reply_text("❌ Please enter a positive amount.")
                    return
                
                context.user_data['awaiting_deposit_amount'] = False
                await self.process_deposit(update.effective_user, amount, context, update.message)
                
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number.")
        else:
            await update.message.reply_text(
                "🤖 I'm a payment bot! Use /start to see available commands."
            )

def main():
    """Start the bot"""
    if not config.Config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in environment variables")
    
    bot = PaymentBot()
    application = Application.builder().token(config.Config.BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("balance", bot.show_balance))
    application.add_handler(CommandHandler("account", bot.show_account))
    application.add_handler(CommandHandler("deposit", bot.deposit))
    application.add_handler(CommandHandler("send", bot.send_money))
    application.add_handler(CommandHandler("history", bot.transaction_history))
    
    application.add_handler(CallbackQueryHandler(bot.handle_deposit_callback, pattern="^deposit_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the Bot
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
