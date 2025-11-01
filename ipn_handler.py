from flask import Flask, request, jsonify
from coinpayments import CoinPaymentsAPI
from database import get_db, Deposit, User

app = Flask(__name__)
coinpayments = CoinPaymentsAPI()

@app.route('/ipn', methods=['POST'])
def handle_ipn():
    # Verify IPN
    if not coinpayments.verify_ipn(request.form, request.headers.get('HMAC', '')):
        return jsonify({'error': 'Invalid HMAC'}), 400
    
    # Process IPN
    status = request.form.get('status')
    txn_id = request.form.get('txn_id')
    
    if status >= 100:  # Payment is complete or escrow released
        db = next(get_db())
        deposit = db.query(Deposit).filter(Deposit.tx_id == txn_id).first()
        
        if deposit and deposit.status != 'completed':
            # Update deposit status
            deposit.status = 'completed'
            
            # Update user balance
            user = db.query(User).filter(User.telegram_id == deposit.user_id).first()
            if user:
                user.balance += deposit.amount
                db.commit()
    
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
