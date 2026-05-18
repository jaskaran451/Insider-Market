from flask import Flask, render_template, request
import requests
from config import COMPANY_MAP
import time
import threading
from config import TICKERS
app = Flask(__name__)

API_KEY = "3S9G9VER47CI2ZT3"
FINNHUB_KEY = "d85n6lpr01qitd92s09gd85n6lpr01qitd92s0a0"

stock_cache = {ticker: {"price": "--", "change": 0} for ticker in TICKERS}

last_updated = 0
CACHE_INTERVAL = 120  # seconds (2 min)

@app.route("/", methods=["GET", "POST"])
def home():
    data = None

    if request.method == "POST":

        symbol = request.form.get("symbol")

        company_name = COMPANY_MAP.get(symbol, "Unknown Company")

        url = f"https://www.alphavantage.co/query?function=INSIDER_TRANSACTIONS&symbol={symbol}&apikey={API_KEY}"

        response = requests.get(url)
        json_data = response.json()

        transactions_raw = json_data.get("data", [])

        transactions = []

        for t in transactions_raw:
            transactions.append({
                "date": t.get("transaction_date"),
                "executive": t.get("executive"),
                "title": t.get("executive_title"),
                "type": "Buy" if t.get("acquisition_or_disposal") == "A" else "Sell",
                "shares": t.get("shares"),
                "price": t.get("share_price"),
                "security": t.get("security_type")
            })

        data = {
            "symbol": symbol,
            "name": company_name,
            "transactions": transactions
        }

    return render_template("index.html", data=data, companies=COMPANY_MAP)

@app.route("/api/stocks")
def get_stocks():
    ordered_data = []
    PRIORITY = ["AAPL", "MSFT", "NVDA", "TSLA"]
    for ticker in PRIORITY + [t for t in TICKERS if t not in PRIORITY]:
        if ticker in stock_cache:
            ordered_data.append({
                "symbol": ticker,
                **stock_cache[ticker]
            })
        else:
            ordered_data.append({
                "symbol": ticker,
                "price": "--",
                "change": 0,
                "percent": 0
            })

    return {
        "data": ordered_data,
        "updated": last_updated
    }

def fetch_quotes():
    global stock_cache, last_updated
    while True:
        for ticker in TICKERS:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
                res = requests.get(url)
                data = res.json()
                stock_cache[ticker] = {
                    "price": data.get("c"),
                    "change": data.get("d"),
                    "percent": data.get("dp")
                }

                last_updated = time.time()
                time.sleep(0.8)
            except Exception as e:
                print("Error:", ticker, e)

        time.sleep(CACHE_INTERVAL)

threading.Thread(target=fetch_quotes, daemon=True).start()
if __name__ == "__main__":
    app.run(debug=True)
