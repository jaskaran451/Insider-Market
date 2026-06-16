from flask import Flask, redirect, session
import requests
from config import COMPANY_MAP
import time
import threading
from config import TICKERS
import os
from datetime import datetime, date
from typing import Dict
from utils.cache_utils import load_cache, save_cache
from collections import defaultdict
from utils.charts import create_insider_chart
import base64
from utils.edgar_wrapper import get_logo_of_company
from flask import render_template, request
from services.insider_service import insider_service
from utils.edgar_wrapper import edgar_client
from sec.parser import filing_parser
from flask import flash
import pandas as pd
import numpy as np

from werkzeug.security import (generate_password_hash,check_password_hash)
from utils.notifier import notifier
from services.manager_portfolio_service import manager_portfolio_service
from dataclasses import asdict
from services.edgar_insider_api_adapter import edgar_insider_api_adapter
from services.stock_data_service import build_prediction_response
import yfinance as yf
from flask import jsonify
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("secret_key1")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
CACHE_FOLDER_insider = "cache/insider"
CACHE_FOLDER_institutions = "cache/institutions"
CACHE_FOLDER_news = "cache/news"

os.makedirs(CACHE_FOLDER_insider, exist_ok=True)
os.makedirs(CACHE_FOLDER_institutions, exist_ok=True)
os.makedirs(CACHE_FOLDER_news, exist_ok=True)


stock_cache = {ticker: {"price": "--", "change": 0} for ticker in TICKERS}

last_updated = 0
CACHE_INTERVAL = 120  # seconds (2 min)
CACHE_EXPIRY_HOURS = 24

# website traffic
page_views = defaultdict(int)
daily_visits = 0
last_reset = time.time()


def fetch_market_data(data_type, symbol):
    symbol = symbol.upper().strip()
    cache_key = symbol

    folder_map = {
        "insider": CACHE_FOLDER_insider,
        "institutions": CACHE_FOLDER_institutions,
        "news": CACHE_FOLDER_news,
    }

    folder = folder_map.get(data_type)

    if not folder:
        print(f"Invalid data_type: {data_type}")
        return {}

    data = load_cache(folder, cache_key, max_age_seconds=24 * 3600)

    if data_type == "insider":
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=INSIDER_TRANSACTIONS"
            f"&symbol={symbol}"
            f"&apikey={API_KEY}"
        )

    elif data_type == "institutions":
        time.sleep(2)
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=INSTITUTIONAL_HOLDINGS"
            f"&symbol={symbol}"
            f"&apikey={API_KEY}"
        )

    elif data_type == "news":
        time.sleep(2)
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=NEWS_SENTIMENT"
            f"&tickers={symbol}"
            f"&limit=50"
            f"&apikey={API_KEY}"
        )

    refresh = False

    if not data:
        refresh = True
    elif not is_valid_api_response(data):
        refresh = True

    if refresh:
        try:
            response = requests.get(url, timeout=15)

            print(f"{data_type.upper()} STATUS:", response.status_code)
            print(f"{data_type.upper()} RAW:", response.text[:500])

            fresh_data = response.json()

            if is_valid_api_response(fresh_data):
                save_cache(folder, cache_key, fresh_data)
                data = fresh_data
            else:
                print(f"Invalid API response for {data_type}: {symbol}")

                if not data:
                    data = {}

        except Exception as e:
            print(f"API fetch error for {data_type}: {e}")

            if not data:
                data = {}

    return data

@app.route("/", methods=["GET", "POST"])
def home():
    data = {
        "symbol": "",
        "name": "",
        "transactions": [],
        "insider_transaction_chart": None,
        "institutional": [],
        "institutional_summary": {
            "total_holders": 0,
            "total_shares": 0,
            "increased_holders": 0,
            "increased_shares": 0,
            "decreased_holders": 0,
            "decreased_shares": 0,
            "unchanged_holders": 0,
            "ownership_pct": "0%"
        },
        "news": [],
        "news_summary": {
            "top_sentiment": None,
            "bullish_count": 0,
            "bearish_count": 0,
            "top_topics": []
        }
    }
    if request.method == "POST":
        notifier.success("Analysis complete")
        symbol = request.form.get("symbol")
        session["ticker"] = symbol
        company_name = request.form.get("company_name", "").strip()
        session["company_name"] = company_name

        # =========================
        # INSIDER DATA
        # ========================= news_data.get("feed", [])
        insider_data = edgar_insider_api_adapter.get_insider_transactions(symbol)

        transactions_raw = insider_data.get("data", [])

        transactions = []
        for t in transactions_raw:
            transactions.append({
                "date": t.get("transaction_date"),
                "executive": t.get("executive"),
                "title": t.get("executive_title"),
                "type": "Buy" if t.get("acquisition_or_disposal") == "A" else "Sell",
                "shares": t.get("shares"),
                "price": t.get("share_price"),
                "shares_value": t.get("share_value"),
                "security": t.get("security_type"),
                "sec_link": t.get("sec_link")
            })

        print("ALPHA key loaded:", bool(API_KEY))
        print("FINNHUB key loaded:", bool(FINNHUB_KEY))
        # =========================
        # INSTITUTIONAL DATA (FIXED)
        # =========================
        institutional = []
        institutional_data=fetch_market_data("institutions", symbol)
        holdings_raw = institutional_data.get("holdings", [])
        for h in holdings_raw:
            change_type = (h.get("change_type") or "").lower()
            if "increase" in change_type:
                status = "Increase"
                css_class = "buy"
            elif "decrease" in change_type:
                status = "Decrease"
                css_class = "sell"
            else:
                status = "Hold"
                css_class = "neutral"

            institutional.append({
                "holder": h.get("holder_name"),
                "shares": h.get("shares_held"),
                "change": h.get("shares_changed"),
                "change_pct": h.get("shares_changed_percentage"),
                "type": status,
                "css": css_class,
                "date": h.get("last_reported")
            })

        institutional_summary = {
            "total_holders": institutional_data.get("total_institutional_holders"),
            "total_shares": institutional_data.get("total_institutional_shares"),
            "increased_holders": institutional_data.get("holders_with_increased_holdings"),
            "increased_shares": institutional_data.get("shares_with_increased_holdings"),
            "decreased_holders": institutional_data.get("holders_with_decreased_holdings"),
            "decreased_shares": institutional_data.get("shares_with_decreased_holdings"),
            "unchanged_holders": institutional_data.get("holders_with_unchanged_holdings"),
            "unchanged_shares": institutional_data.get("shares_with_unchanged_holdings"),
            "ownership_pct": institutional_data.get("total_institutional_ownership_percentage")
        }

        # =========================
        # News and sentiments
        # =========================
        news_data=fetch_market_data("news", symbol)
        feed_raw = news_data.get("feed", [])[:20]
        bullish = 0
        bearish = 0
        neutral = 0
        total_score = 0
        topic_map: Dict[str, float] = {}
        for item in feed_raw:
            label = item.get("overall_sentiment_label")
            score = item.get("overall_sentiment_score") or 0
            total_score += score
            if label == "Bullish":
                bullish += 1
            elif label == "Bearish":
                bearish += 1
            else:
                neutral += 1
            for t in item.get("topics", []):
                topic = t.get("topic")
                relevance_score = float(t.get("relevance_score", 0))
                topic_map[t["topic"]] = topic_map.get(t["topic"], 0) + 1
        news = []
        top_topic = max(topic_map, key=topic_map.get) if topic_map else "N/A"
        summary = {
            "total_articles": len(feed_raw),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "avg_score": round(total_score / len(feed_raw), 3) if feed_raw else 0,
            "top_topic": top_topic
        }

        for item in feed_raw:
            news.append({
                "title": item.get("title"),
                "summary": item.get("summary"),
                "image": item.get("banner_image"),
                "source": item.get("source"),
                "url": item.get("url"),
                "time": item.get("time_published"),
                "sentiment_label": item.get("overall_sentiment_label"),
                "sentiment_score": item.get("overall_sentiment_score"),
                "topics": [t["topic"] for t in item.get("topics", [])],
                "tickers": [
                    {
                        "symbol": t["ticker"],
                        "label": t["ticker_sentiment_label"],
                        "score": t["ticker_sentiment_score"]
                    }
                    for t in item.get("ticker_sentiment", [])
                ]
            })
        # get logo of company
        image_bytes=None
        image_bytes = get_logo_of_company(symbol)
        if image_bytes:
            encoded_string = base64.b64encode(image_bytes).decode('utf-8')
            image_src = f"data:image/jpeg;base64,{encoded_string}"
        else:
            image_src = None

        print("News response:", news_data)
        print("Institution response:", institutional_data)

        data = {
            "symbol": symbol,
            "name": company_name,
            "transactions": transactions,
            "institutional": institutional,
            "institutional_summary": institutional_summary,
            "news": news,
            "news_summary": summary,
            "logo": image_src,
        }

    return render_template("index.html", data=data, companies=COMPANY_MAP)

@app.route("/chart/<symbol>/<int:months>")
def insider_chart(symbol, months):

    insider_data = fetch_market_data("insider",symbol)
    transactions_raw = insider_data.get("data", [])

    transactions = []

    for t in transactions_raw:
        transactions.append({
            "date": t.get("transaction_date"),
            "type": "Buy" if t.get("acquisition_or_disposal") == "A" else "Sell",
            "shares": t.get("shares")
        })

    chart = create_insider_chart(transactions, months)

    return jsonify({
        "chart": chart
    })

@app.route("/company-info/<symbol>")
def company_info_api(symbol):
    try:
        return jsonify({
            "success": True,
            "data": get_company_info(symbol)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

def get_company_info(symbol):
    ticker = yf.Ticker(symbol)

    info = ticker.get_info()
    fast = ticker.fast_info

    price = info.get("currentPrice") or info.get("regularMarketPrice") or safe_get(fast, "last_price")
    previous_close = info.get("previousClose") or safe_get(fast, "previous_close")
    open_price = info.get("open") or safe_get(fast, "open")

    day_low = info.get("dayLow") or safe_get(fast, "day_low")
    day_high = info.get("dayHigh") or safe_get(fast, "day_high")

    year_low = info.get("fiftyTwoWeekLow") or safe_get(fast, "year_low")
    year_high = info.get("fiftyTwoWeekHigh") or safe_get(fast, "year_high")

    volume = info.get("volume") or safe_get(fast, "last_volume")
    market_cap = info.get("marketCap") or safe_get(fast, "market_cap")

    data = {
        "snapshot": {
            "name": info.get("longName") or info.get("shortName") or symbol.upper(),
            "sector": info.get("sector") or "N/A",
            "website": info.get("website") or ""
        },

        "market": {
            "price": format_large_number(price),
            "previous_close": format_large_number(previous_close),
            "open": format_large_number(open_price),
            "day_range": f"{format_number(day_low)} - {format_number(day_high)}",
            "week_52_range": info.get("fiftyTwoWeekRange") or f"{format_number(year_low)} - {format_number(year_high)}",
            "volume": format_integer(volume),
            "market_cap": format_large_number(market_cap)
        },

        "valuation": {
            "forward_pe": format_number(info.get("forwardPE")),
            "price_to_book": format_number(info.get("priceToBook")),
            "price_to_sales": format_number(info.get("priceToSalesTrailing12Months")),
            "enterprise_value": format_large_number(info.get("enterpriseValue")),
            "beta": format_number(info.get("beta"))
        },

        "financial_health": {
            "revenue": format_large_number(info.get("totalRevenue")),
            "gross_margin": format_percent(info.get("grossMargins")),
            "operating_margin": format_percent(info.get("operatingMargins")),
            "profit_margin": format_percent(info.get("profitMargins")),
            "free_cashflow": format_large_number(info.get("freeCashflow")),
            "total_cash": format_large_number(info.get("totalCash")),
            "total_debt": format_large_number(info.get("totalDebt"))
        },

        "analyst": {
            "target_low": format_large_number(info.get("targetLowPrice")),
            "target_mean": format_large_number(info.get("targetMeanPrice")),
            "target_high": format_large_number(info.get("targetHighPrice")),
            "analyst_opinions": info.get("numberOfAnalystOpinions") or "N/A"
        }
    }

    return data

@app.route("/insider", methods=["GET"])
def insider_dashboard():

    ticker = session.get("ticker")

    if not ticker:
        return jsonify({
            "success": False,
            "message": "Ticker is required"
        }), 400

    company = edgar_client.find(ticker)

    if not company:
        return jsonify({
            "success": False,
            "message": "Company not found"
        }), 404

    entity = company.raw
    filings = entity.get_filings(form=["4"])

    parsed_filings = []

    for idx, filing in enumerate(filings):
        if idx >= 30:
            break

        try:
            parsed = filing_parser.parse(filing)
            if parsed:
                parsed_filings.append(parsed)
        except Exception as e:
            print(f"[INSIDER PARSE ERROR] {ticker}: {e}")

    summary = insider_service.analyze(parsed_filings, company.name)
    summary_dict = make_json_safe(asdict(summary))

    return jsonify({
        "success": True,
        "data": summary_dict
    })

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
    time.sleep(2)
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

@app.route("/smart-money-trend",methods=["GET"])
def smart_money_trend_page():
    return render_template("smartmoney_trend.html")

@app.route("/api/smart-money-trend",methods=["GET"])
def smart_money_trend_api():
    query=request.args.get("query")
    if not query:
        return jsonify({
            "success":False,
            "message":"Query is required"
        }),400
    try:
        result=manager_portfolio_service.analyze(query)
        time.sleep(3)
        result=make_json_safe(result)
        status=200 if result.get("success") else 404
        return jsonify(result),status
    except Exception as e:
        print(f"[SMART MONEY TREND ERROR] {query}: {e}")
        return jsonify({
            "success":False,
            "message":"Failed to load Smart Money Trend data"
        }),500


@app.route("/prediction")
def prediction():
    return render_template("prediction.html")

@app.route("/api/predict/<symbol>")
def predict_stock(symbol):
    symbol = symbol.upper().strip()
    try:
        result = build_prediction_response(symbol)
        return jsonify(result)

    except Exception as error:
        return jsonify({
            "error": True,
            "message": str(error)
        }), 400



@app.route("/search")
def search_symbols():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"success": True, "results": []})

    try:
        search = yf.Search(
            query,
            max_results=8,
            news_count=0,
            lists_count=0,
            include_research=False
        )

        quotes = search.quotes or []

        results = []

        for item in quotes:
            symbol = item.get("symbol")
            name = item.get("shortname") or item.get("longname") or item.get("name")
            exchange = item.get("exchange") or item.get("exchDisp")
            quote_type = item.get("quoteType")

            if symbol and name:
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "type": quote_type
                })

        return jsonify({
            "success": True,
            "results": results
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error),
            "results": []
        }), 400


def is_valid_api_response(data):
    if not isinstance(data, dict):
        return False

    # Alpha Vantage error cases
    if "Information" in data:
        return False
    if "Error Message" in data:
        return False
    if "Note" in data:
        return False

    return True

def make_json_safe(value):
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (np.ndarray,)):
        return value.tolist()

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()

    if pd.isna(value):
        return None

    return value

def format_large_number(value):
    if value is None:
        return "N/A"

    try:
        value = float(value)

        if abs(value) >= 1_000_000_000_000:
            return f"${value / 1_000_000_000_000:.2f}T"

        if abs(value) >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"

        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"

        if abs(value) >= 1_000:
            return f"${value / 1_000:.2f}K"

        return f"${value:.2f}"

    except Exception:
        return "N/A"

def format_number(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "N/A"


def format_integer(value):
    if value is None:
        return "N/A"

    try:
        return f"{int(value):,}"
    except Exception:
        return "N/A"


def format_percent(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "N/A"

def safe_get(source, key, default=None):
    try:
        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(key, default)

        return source.get(key, default)

    except Exception:
        try:
            return getattr(source, key, default)
        except Exception:
            return default

if __name__ == "__main__":

    threading.Thread(target=fetch_quotes, daemon=True).start()
    app.run(debug=True)
