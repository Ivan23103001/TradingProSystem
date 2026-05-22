import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

def test_connection():
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    is_paper = os.getenv("ALPACA_PAPER", "True").lower() == "true"
    
    print(f"Testing Alpaca Connection (Paper={is_paper})...")
    try:
        trading_client = TradingClient(api_key, secret_key, paper=is_paper)
        account = trading_client.get_account()
        print(f"Connection Successful!")
        print(f"Account #: {account.account_number}")
        print(f"Equity: ${account.equity}")
        print(f"Buying Power: ${account.buying_power}")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    test_connection()
