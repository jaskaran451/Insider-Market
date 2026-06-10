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
from models import db, User,Traffic
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
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required
)
from werkzeug.security import (generate_password_hash,check_password_hash)
from utils.notifier import notifier
from services.manager_portfolio_service import manager_portfolio_service
from dataclasses import asdict


app = Flask(__name__)
app.secret_key = "my-secret-key"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "database", "users.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SECRET_KEY"] = "supersecretkey"
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
db.init_app(app)

CACHE_FOLDER_insider = "cache/insider"
os.makedirs(CACHE_FOLDER_insider, exist_ok=True)

CACHE_FOLDER_news = "cache/news"
os.makedirs(CACHE_FOLDER_news, exist_ok=True)

# API_KEY = "MWVQMX02ULG4MRQI"
# API_KEY="XN815F5G472K82LV"
API_KEY= "XN815F5G472K82LV"
FINNHUB_KEY = "d85n6lpr01qitd92s09gd85n6lpr01qitd92s0a0"

stock_cache = {ticker: {"price": "--", "change": 0} for ticker in TICKERS}

last_updated = 0
CACHE_INTERVAL = 120  # seconds (2 min)
CACHE_EXPIRY_HOURS = 24

login_manager = LoginManager()
login_manager.init_app(app)

# website traffic
page_views = defaultdict(int)
daily_visits = 0
last_reset = time.time()

@app.before_request
def track():
    if request.endpoint in ["static"]:
        return

    # avoid logging analytics endpoint itself
    if request.path.startswith("/api"):
        return
    page = request.path.split("?")[0]
    visit = Traffic(page=request.path)
    db.session.add(visit)
    db.session.commit()

@app.route("/api/analytics")
def analytics():
    total = Traffic.query.count()
    top_pages = db.session.query(
        Traffic.page,
        db.func.count(Traffic.id)
    ).group_by(Traffic.page).all()

    return {
        "total_visits": total,
        "top_pages": dict(top_pages)
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def fetch_market_data(folder, symbol):
    cache_key = symbol

    data = load_cache(folder,cache_key,max_age_seconds=24 * 3600)
    if folder == "insider":
        url = f"https://www.alphavantage.co/query?function=INSIDER_TRANSACTIONS&symbol={symbol}&apikey={API_KEY}"
    elif folder == "institutions":
        time.sleep(2)
        url = f"https://www.alphavantage.co/query?function=INSTITUTIONAL_HOLDINGS&symbol={symbol}&apikey={API_KEY}"
    elif folder == "news":
        time.sleep(2)
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&limit=50&apikey={API_KEY}"
    else:
        return {}

    # =========================
    # Decide if refresh needed
    # =========================
    refresh = False

    if not data:
        refresh = True
    elif not is_valid_api_response(data):
        refresh = True
    if refresh:
        try:
            response = requests.get(url, timeout=10)
            fresh_data = response.json()
            # ONLY cache valid data
            if is_valid_api_response(fresh_data):
                save_cache(folder, cache_key, fresh_data)
                data = fresh_data
            else:
                print(f"Invalid API response for {folder}: {symbol}")
                # keep old cache if possible
                if not data:
                    data = {}
        except Exception as e:
            print(f"API fetch error: {e}")

            # fallback if no cache exists
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
        company_name = COMPANY_MAP.get(symbol, "Unknown Company")

        # =========================
        # INSIDER DATA
        # =========================
        insider_data = fetch_market_data("insider", symbol)
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
                "security": t.get("security_type")
            })

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
        image_bytes = get_logo_of_company(symbol)
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')
        image_src = f"data:image/jpeg;base64,{encoded_string}"


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

    flash("Insider data loaded successfully", "success")
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

from flask import jsonify
from dataclasses import asdict


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





@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "Email already exists"

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            login_user(user)

            return redirect("/")

        return "Invalid credentials"

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect("/")
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    threading.Thread(target=fetch_quotes, daemon=True).start()
    app.run(debug=True)
