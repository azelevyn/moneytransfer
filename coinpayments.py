import hmac
import hashlib
import requests
import json
from urllib.parse import urlencode
from config import Config

class CoinPaymentsAPI:
    def __init__(self):
        self.public_key = Config.COINPAYMENTS_PUBLIC_KEY
        self.private_key = Config.COINPAYMENTS_PRIVATE_KEY
        self.merchant_id = Config.COINPAYMENTS_MERCHANT_ID
        self.ipn_secret = Config.COINPAYMENTS_IPN_SECRET
        self.base_url = "https://www.coinpayments.net/api.php"
    
    def _create_hmac(self, payload):
        """Create HMAC signature for API requests"""
        encoded_payload = urlencode(payload).encode('utf-8')
        signature = hmac.new(
            bytearray(self.private_key, 'utf-8'),
            encoded_payload,
            hashlib.sha512
        ).hexdigest()
        return signature
    
    def create_transaction(self, amount, currency='USD', buyer_email='', item_name='Deposit'):
        """Create a new transaction for deposit"""
        payload = {
            'cmd': 'create_transaction',
            'version': 1,
            'key': self.public_key,
            'amount': amount,
            'currency1': 'USD',  # Price is in USD
            'currency2': currency,  # Coin to receive
            'buyer_email': buyer_email,
            'item_name': item_name,
            'merchant': self.merchant_id,
            'ipn_url': f'https://your-domain.com/ipn',  # Update with your domain
        }
        
        headers = {
            'HMAC': self._create_hmac(payload),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(self.base_url, data=payload, headers=headers)
            result = response.json()
            
            if result['error'] == 'ok':
                return {
                    'success': True,
                    'amount': result['result']['amount'],
                    'address': result['result']['address'],
                    'txn_id': result['result']['txn_id'],
                    'timeout': result['result']['timeout'],
                    'checkout_url': result['result']['status_url'],
                    'currency': currency
                }
            else:
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_transaction_info(self, tx_id):
        """Get transaction information"""
        payload = {
            'cmd': 'get_tx_info',
            'version': 1,
            'key': self.public_key,
            'txid': tx_id
        }
        
        headers = {
            'HMAC': self._create_hmac(payload),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(self.base_url, data=payload, headers=headers)
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def verify_ipn(self, request_data, hmac_header):
        """Verify IPN request"""
        # Sort the POST values alphabetically
        sorted_data = sorted(request_data.items())
        
        # URL encode the sorted values
        encoded_data = urlencode(sorted_data).encode('utf-8')
        
        # Create HMAC signature
        calculated_hmac = hmac.new(
            bytearray(self.ipn_secret, 'utf-8'),
            encoded_data,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hmac, hmac_header)
