from flask import Response, request, redirect, url_for
import requests
from config import COMPANY_MAP
import time
import threading
from config import TICKERS
import os
import re
import secrets
from datetime import datetime, date
from typing import Dict
from utils.cache_utils import load_cache, save_cache
from collections import defaultdict, deque
from functools import wraps
from utils.charts import create_insider_chart
import base64
import hmac
from utils.edgar_wrapper import get_logo_of_company
from flask import render_template
from services.insider_service import insider_service
from utils.edgar_wrapper import edgar_client
from sec.parser import filing_parser
from flask import flash
import pandas as pd
import numpy as np
import traceback
from werkzeug.security import generate_password_hash, check_password_hash
from utils.notifier import notifier
from services.manager_portfolio_service import manager_portfolio_service
from dataclasses import asdict
from services.edgar_insider_api_adapter import edgar_insider_api_adapter
from services.stock_data_service import build_prediction_response
from services.ollama_analysis import (
    stream_dashboard_ai_analysis,
    stream_forecast_ai_analysis,
    stream_smart_money_ai_explanation,
    analyze_news_sentiment,
    stream_news_sentiment,
)
from services.google_news_service import google_news_service
import json
import queue
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from edgar import set_identity
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from database.db import get_db_connection
import yfinance as yf
from flask import jsonify

load_dotenv()


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    secret_key = secrets.token_urlsafe(32)
    app.logger.warning(
        "SECRET_KEY is not configured. Using a temporary key; "
        "sessions will reset when the application restarts."
    )

app.config["SECRET_KEY"] = secret_key

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
ROIC_API_KEY = os.getenv("ROIC_API_KEY")
CACHE_FOLDER_insider = "cache/insider"
CACHE_FOLDER_institutions = "cache/institutions"
CACHE_FOLDER_news = "cache/news"
CACHE_FOLDER_earnings = "cache/earnings"
EARNINGS_CACHE_SECONDS = 60 * 60
dashboard_ai_data_cache = {}
smart_money_ai_cache = {}
SMART_MONEY_CACHE_SECONDS = 6 * 60 * 60

os.makedirs(CACHE_FOLDER_insider, exist_ok=True)
os.makedirs(CACHE_FOLDER_institutions, exist_ok=True)
os.makedirs(CACHE_FOLDER_news, exist_ok=True)
os.makedirs(CACHE_FOLDER_earnings, exist_ok=True)


stock_cache = {ticker: {"price": "--", "change": 0, "percent": 0} for ticker in TICKERS}
last_updated = 0
CACHE_INTERVAL = 300

stock_cache_lock = threading.Lock()
stock_refreshing = False
CACHE_EXPIRY_HOURS = 24

# website traffic
page_views = defaultdict(int)
daily_visits = 0
last_reset = time.time()

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"
set_identity(os.getenv("SEC_IDENTITY", "Smart Money Flow jaskaran19942@gmail.com"))


def generate_csrf_token():
    token = session.get("_csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token

    return token


app.jinja_env.globals["csrf_token"] = generate_csrf_token

rate_limit_buckets = defaultdict(deque)
rate_limit_lock = threading.Lock()


def rate_limit(max_requests, window_seconds):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            client_ip = (
                forwarded_for.split(",", 1)[0].strip()
                or request.remote_addr
                or "unknown"
            )
            key = (view_function.__name__, client_ip)
            now = time.time()

            with rate_limit_lock:
                bucket = rate_limit_buckets[key]
                cutoff = now - window_seconds

                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()

                if len(bucket) >= max_requests:
                    retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
                    response = jsonify(
                        {
                            "success": False,
                            "message": "Too many requests. Please try again later.",
                        }
                    )
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    return response

                bucket.append(now)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


@app.before_request
def protect_form_posts():
    protected_endpoints = {"login", "signup", "contact", "home"}

    if request.method != "POST" or request.endpoint not in protected_endpoints:
        return None

    expected_token = session.get("_csrf_token", "")
    submitted_token = request.form.get("_csrf_token", "")

    if expected_token and hmac.compare_digest(expected_token, submitted_token):
        return None

    flash("Your session expired. Please refresh the page and try again.", "error")

    if request.endpoint == "contact":
        return redirect(url_for("landing") + "#contact")

    return redirect(url_for(request.endpoint))


class User(UserMixin):
    def __init__(self, id, full_name, email):
        self.id = str(id)
        self.full_name = full_name
        self.email = email
        self.initials = self.get_initials(full_name)

    @staticmethod
    def get_initials(full_name):
        parts = full_name.strip().split()

        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()

        if len(parts) == 1:
            return parts[0][:2].upper()

        return "U"


@login_manager.user_loader
def load_user(user_id):
    session_user_id = session.get("user_id")
    full_name = session.get("user_full_name")
    email = session.get("user_email")

    if session_user_id == str(user_id) and full_name and email:
        return User(session_user_id, full_name, email)

    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return redirect(url_for("login"))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, full_name, email, password_hash FROM users WHERE email = ?",
                email,
            )

            row = cursor.fetchone()
            conn.close()

        except Exception as e:
            print("Login database error:", e)
            flash("Database connection failed. Please try again later.", "error")
            return redirect(url_for("login"))

        if row and bcrypt.check_password_hash(row.password_hash, password):
            user = User(row.id, row.full_name, row.email)

            session["user_id"] = str(row.id)
            session["user_full_name"] = row.full_name
            session["user_email"] = row.email

            login_user(user)

            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html", auth_mode="login")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("signup"))

        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE email = ?", email)
            existing_user = cursor.fetchone()

            if existing_user:
                conn.close()
                flash("An account with this email already exists.", "error")
                return redirect(url_for("signup"))

            cursor.execute(
                """
                INSERT INTO users (full_name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                full_name,
                email,
                password_hash,
            )

            conn.commit()
            conn.close()

            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            print("Signup database error:", e)
            flash("Something went wrong while creating your account.", "error")
            return redirect(url_for("signup"))

    return render_template("login.html", auth_mode="signup")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account():
    return render_template("account.html")


app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USERNAME")

mail = Mail(app)


@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        flash("Please fill out all contact fields.", "error")
        return redirect(url_for("landing") + "#contact")

    try:
        receiver_email = os.getenv("CONTACT_RECEIVER_EMAIL")

        msg = Message(
            subject=f"New InsiderAI Contact Message from {name}",
            recipients=[receiver_email],
            reply_to=email,
        )

        msg.body = f"""
New contact message from InsiderAI website.
Name:
{name}
Email:
{email}
Message:
{message}
"""
        mail.send(msg)

        flash(
            "Message sent successfully. Thank you for contacting InsiderAI.", "success"
        )
        return redirect(url_for("landing") + "#contact")

    except Exception as e:
        print("Contact email error:", e)
        flash(
            "Something went wrong while sending your message. Please try again later.",
            "error",
        )
        return redirect(url_for("landing") + "#contact")


def build_empty_dashboard_data():
    return {
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
            "unchanged_shares": 0,
            "ownership_pct": "0%",
        },
        "news": [],
        "news_summary": {
            "total_articles": 0,
            "bullish": 0,
            "bearish": 0,
            "neutral": 0,
            "avg_score": 0,
            "top_topic": "N/A",
        },
        "earnings": {
            "available": False,
            "message": "Search a company to view earnings transcripts.",
            "items": [],
        },
        "logo": None,
    }


def process_insider_data(symbol):
    insider_data = edgar_insider_api_adapter.get_insider_transactions(symbol)
    transactions_raw = insider_data.get("data", [])

    transactions = []

    for item in transactions_raw:
        acquisition_or_disposal = item.get("acquisition_or_disposal")

        if acquisition_or_disposal == "A":
            transaction_type = "Buy"
        elif acquisition_or_disposal == "D":
            transaction_type = "Sell"
        else:
            transaction_type = "Other"

        transactions.append(
            {
                "date": item.get("transaction_date"),
                "executive": item.get("executive"),
                "title": item.get("executive_title"),
                "type": transaction_type,
                "shares": item.get("shares"),
                "price": item.get("share_price"),
                "shares_value": (
                    item.get("transaction_value") or item.get("share_value")
                ),
                "security": item.get("security_type"),
                "sec_link": (item.get("sec_filing_url") or item.get("sec_link")),
            }
        )

    return transactions


def process_institutional_data(symbol):
    institutional_data = fetch_market_data("institutions", symbol)

    holdings_raw = institutional_data.get("holdings", [])
    institutional = []

    for holding in holdings_raw:
        change_type = str(holding.get("change_type") or "").lower()

        if "increase" in change_type:
            status = "Increase"
            css_class = "buy"
        elif "decrease" in change_type:
            status = "Decrease"
            css_class = "sell"
        else:
            status = "Hold"
            css_class = "neutral"

        institutional.append(
            {
                "holder": holding.get("holder_name"),
                "shares": holding.get("shares_held"),
                "change": holding.get("shares_changed"),
                "change_pct": holding.get("shares_changed_percentage"),
                "type": status,
                "css": css_class,
                "date": holding.get("last_reported"),
            }
        )

    institutional_summary = {
        "total_holders": institutional_data.get("total_institutional_holders") or 0,
        "total_shares": institutional_data.get("total_institutional_shares") or 0,
        "increased_holders": institutional_data.get("holders_with_increased_holdings")
        or 0,
        "increased_shares": institutional_data.get("shares_with_increased_holdings")
        or 0,
        "decreased_holders": institutional_data.get("holders_with_decreased_holdings")
        or 0,
        "decreased_shares": institutional_data.get("shares_with_decreased_holdings")
        or 0,
        "unchanged_holders": institutional_data.get("holders_with_unchanged_holdings")
        or 0,
        "unchanged_shares": institutional_data.get("shares_with_unchanged_holdings")
        or 0,
        "ownership_pct": institutional_data.get(
            "total_institutional_ownership_percentage"
        )
        or "0%",
    }

    return institutional, institutional_summary


def build_news_ui_article(item, symbol):
    label = item.get("overall_sentiment_label") or "Neutral"

    try:
        score = float(item.get("overall_sentiment_score") or 0)
    except (TypeError, ValueError):
        score = 0.0

    ticker_items = item.get("ticker_sentiment") or []

    tickers = []

    for ticker_item in ticker_items:
        tickers.append(
            {
                "symbol": (ticker_item.get("ticker") or symbol),
                "label": label,
                "score": score,
            }
        )

    if not tickers:
        tickers = [{"symbol": symbol, "label": label, "score": score}]

    return {
        "id": item.get("news_id"),
        "title": item.get("title"),
        "summary": item.get("summary") or "",
        "image": item.get("banner_image"),
        "source": (item.get("source") or "Google News"),
        "url": item.get("url"),
        "time": item.get("time_published"),
        "sentiment_label": label,
        "sentiment_score": score,
        "sentiment_reason": (
            item.get("sentiment_reason")
            or ("No clear company-specific impact was identified.")
        ),
        "topics": [
            topic.get("topic") for topic in item.get("topics", []) if topic.get("topic")
        ],
        "tickers": tickers,
    }


def build_news_summary(news_items):
    bullish = 0
    bearish = 0
    neutral = 0
    total_score = 0.0
    topic_map = {}

    for item in news_items:
        label = item.get("sentiment_label") or "Neutral"

        try:
            score = float(item.get("sentiment_score") or 0)
        except (TypeError, ValueError):
            score = 0.0

        total_score += score

        if label == "Bullish":
            bullish += 1
        elif label == "Bearish":
            bearish += 1
        else:
            neutral += 1

        for topic in item.get("topics", []):
            if not topic:
                continue

            topic_map[topic] = topic_map.get(topic, 0) + 1

    top_topic = max(topic_map, key=topic_map.get) if topic_map else "N/A"

    return {
        "total_articles": len(news_items),
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "avg_score": (round(total_score / len(news_items), 3) if news_items else 0),
        "top_topic": top_topic,
    }


def process_news_data(symbol, company_name):
    news_data = get_google_news_cached(symbol, company_name)
    feed_raw = news_data.get("feed", [])[:20]

    feed_raw = analyze_news_sentiment(
        news_items=feed_raw, symbol=symbol, company_name=company_name
    )

    bullish = 0
    bearish = 0
    neutral = 0
    total_score = 0.0
    topic_map = {}

    for item in feed_raw:
        label = item.get("overall_sentiment_label") or "Neutral"

        try:
            score = float(item.get("overall_sentiment_score") or 0)
        except (TypeError, ValueError):
            score = 0.0

        total_score += score

        if label == "Bullish":
            bullish += 1
        elif label == "Bearish":
            bearish += 1
        else:
            neutral += 1

        for topic_item in item.get("topics", []):
            topic = topic_item.get("topic")

            if not topic:
                continue

            try:
                relevance = float(topic_item.get("relevance_score") or 1)
            except (TypeError, ValueError):
                relevance = 1.0

            topic_map[topic] = topic_map.get(topic, 0) + relevance

    top_topic = max(topic_map, key=topic_map.get) if topic_map else "N/A"

    summary = {
        "total_articles": len(feed_raw),
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "avg_score": round(total_score / len(feed_raw), 3) if feed_raw else 0,
        "top_topic": top_topic,
    }

    news = []

    for item in feed_raw:
        label = item.get("overall_sentiment_label") or "Neutral"

        try:
            score = float(item.get("overall_sentiment_score") or 0)
        except (TypeError, ValueError):
            score = 0.0

        ticker_items = item.get("ticker_sentiment", [])
        tickers = []

        for ticker_item in ticker_items:
            tickers.append(
                {
                    "symbol": ticker_item.get("ticker") or symbol,
                    "label": label,
                    "score": score,
                }
            )

        if not tickers:
            tickers = [{"symbol": symbol, "label": label, "score": score}]

        news.append(
            {
                "id": item.get("news_id"),
                "title": item.get("title"),
                "summary": item.get("summary") or "",
                "image": item.get("banner_image"),
                "source": item.get("source") or "Google News",
                "url": item.get("url"),
                "time": item.get("time_published"),
                "sentiment_label": label,
                "sentiment_score": score,
                "sentiment_reason": item.get("sentiment_reason")
                or "No clear company-specific impact was identified.",
                "topics": [
                    topic.get("topic")
                    for topic in item.get("topics", [])
                    if topic.get("topic")
                ],
                "tickers": tickers,
            }
        )

    return news, summary


def process_earnings_data(symbol):
    symbol = (symbol or "").upper().strip()

    try:
        # Version the key when transcript-source logic changes so an older,
        # valid-looking ROIC-only result cannot hide a newer transcript.
        cache_key = f"earnings_v2_{symbol}"
        cached = load_cache(
            CACHE_FOLDER_earnings,
            cache_key,
            max_age_seconds=EARNINGS_CACHE_SECONDS,
        )

        if cached:
            return cached

        earnings = fetch_earnings_transcripts(symbol)

        if earnings.get("available"):
            save_cache(CACHE_FOLDER_earnings, cache_key, earnings)

        return earnings

    except Exception as error:
        print(f"[EARNINGS PROCESSING ERROR] {symbol}:", error)

        return {
            "available": False,
            "message": ("Earnings transcript data is temporarily unavailable."),
            "items": [],
        }


def process_company_logo(symbol):
    try:
        image_bytes = get_logo_of_company(symbol)

        if not image_bytes:
            return None

        encoded_string = base64.b64encode(image_bytes).decode("utf-8")

        return f"data:image/jpeg;base64,{encoded_string}"

    except Exception as error:
        print(f"[COMPANY LOGO ERROR] {symbol}:", error)

        return None


def cache_dashboard_ai_data(data):
    symbol = data.get("symbol")

    if not symbol:
        return

    dashboard_ai_data_cache[symbol] = {
        "symbol": symbol,
        "name": data.get("name"),
        "transactions": data.get("transactions", []),
        "institutional": data.get("institutional", []),
        "institutional_summary": data.get("institutional_summary", {}),
        "news": data.get("news", []),
        "news_summary": data.get("news_summary", {}),
        "earnings": data.get("earnings", {}),
    }


def get_google_news_cached(symbol, company_name=None):
    symbol = (symbol or "").upper().strip()
    cache_key = f"google_news_{symbol}"
    cached = load_cache(CACHE_FOLDER_news, cache_key, max_age_seconds=6 * 3600)

    if cached and cached.get("feed"):
        return cached

    fresh = google_news_service.get_company_news(
        symbol=symbol, company_name=company_name, limit=30, when="7d"
    )

    if fresh.get("feed"):
        save_cache(CACHE_FOLDER_news, cache_key, fresh)
        return fresh

    if cached:
        cached["_using_cached_fallback"] = True
        return cached

    return fresh


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


def get_cached_smart_money_result(symbol):
    symbol = symbol.upper().strip()

    cached = smart_money_ai_cache.get(symbol)

    if not cached:
        return None

    created_at = cached.get("created_at", 0)

    if time.time() - created_at > SMART_MONEY_CACHE_SECONDS:
        smart_money_ai_cache.pop(symbol, None)
        return None

    return cached


def build_smart_money_result(symbol):
    """
    Generates Smart Money Intelligence once and stores the result.

    Both the Smart Money panel and the AI explanation reuse
    this same calculated result.
    """

    symbol = symbol.upper().strip()

    company = edgar_client.find(symbol)

    if not company:
        raise ValueError("Company not found")

    entity = company.raw
    filings = entity.get_filings(form=["4"])

    parsed_filings = []

    for index, filing in enumerate(filings):
        if index >= 30:
            break

        try:
            parsed = filing_parser.parse(filing)

            if parsed:
                parsed_filings.append(parsed)

        except Exception as error:
            print(f"[INSIDER PARSE ERROR] {symbol}:", error)

    summary = insider_service.analyze(parsed_filings, company.name)

    summary_dict = make_json_safe(asdict(summary))

    result = {
        "symbol": symbol,
        "company": company.name,
        "summary": summary_dict,
        "created_at": time.time(),
    }

    smart_money_ai_cache[symbol] = result

    return result


@app.route("/")
def landing():
    return render_template("main.html")


@app.route("/api/smart-money/<symbol>/prepare", methods=["POST"])
@rate_limit(30, 3600)
def prepare_smart_money_intelligence(symbol):
    symbol = symbol.upper().strip()

    try:
        result = get_cached_smart_money_result(symbol)

        if not result:
            result = build_smart_money_result(symbol)

        return jsonify({"success": True, "smart_money": result["summary"]})

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 404

    except Exception as error:
        print(f"[SMART MONEY PREPARE ERROR] {symbol}: {error}")

        traceback.print_exc()

        return jsonify(
            {
                "success": False,
                "message": "Unable to prepare insider intelligence.",
            }
        ), 500


@app.route("/dashboard", methods=["GET", "POST"])
def home():
    data = build_empty_dashboard_data()
    if request.method != "POST":
        return render_template("index.html", data=data, companies=COMPANY_MAP)

    symbol = (request.form.get("symbol") or "").upper().strip()
    company_name = (request.form.get("company_name") or "").strip()

    if not symbol:
        flash("Please select a valid company.", "warning")
        return render_template("index.html", data=data, companies=COMPANY_MAP)

    if not company_name:
        company_name = COMPANY_MAP.get(symbol) or symbol

    session["ticker"] = symbol
    session["company_name"] = company_name

    data["symbol"] = symbol
    data["name"] = company_name
    dashboard_ai_data_cache[symbol] = {
        "symbol": symbol,
        "name": company_name,
        "transactions": [],
        "institutional": [],
        "institutional_summary": data["institutional_summary"],
        "news": [],
        "news_summary": data["news_summary"],
        "earnings": data["earnings"],
    }

    return render_template("index.html", data=data, companies=COMPANY_MAP)


def update_dashboard_ai_section(
    symbol,
    section,
    value,
    summary_key=None,
    summary_value=None,
    company_name=None,
):
    """Update cached dashboard data without requiring a request context."""

    symbol = symbol.upper().strip()
    resolved_company_name = company_name or COMPANY_MAP.get(symbol) or symbol

    empty_data = build_empty_dashboard_data()

    cached = dashboard_ai_data_cache.setdefault(
        symbol,
        {
            "symbol": symbol,
            "name": resolved_company_name,
            "transactions": [],
            "institutional": [],
            "institutional_summary": empty_data["institutional_summary"],
            "news": [],
            "news_summary": empty_data["news_summary"],
            "earnings": empty_data["earnings"],
        },
    )

    cached["name"] = resolved_company_name
    cached[section] = value

    if summary_key:
        cached[summary_key] = summary_value


@app.route("/api/dashboard/<symbol>/insiders")
def dashboard_insiders_api(symbol):
    symbol = symbol.upper().strip()
    try:
        transactions = process_insider_data(symbol)
        update_dashboard_ai_section(symbol, "transactions", transactions)
        return jsonify({"success": True, "transactions": make_json_safe(transactions)})
    except Exception as error:
        print(f"[INSIDER API ERROR] {symbol}:", error)
        return jsonify(
            {
                "success": False,
                "message": "Unable to load insider transactions right now.",
            }
        ), 500


@app.route("/api/dashboard/<symbol>/institutions")
def dashboard_institutions_api(symbol):
    symbol = symbol.upper().strip()
    try:
        institutional, summary = process_institutional_data(symbol)
        update_dashboard_ai_section(
            symbol, "institutional", institutional, "institutional_summary", summary
        )
        return jsonify(
            {
                "success": True,
                "institutional": make_json_safe(institutional),
                "summary": make_json_safe(summary),
            }
        )
    except Exception as error:
        print(f"[INSTITUTION API ERROR] {symbol}:", error)
        return jsonify(
            {
                "success": False,
                "message": "Unable to load institutional holdings right now.",
            }
        ), 500


@app.route("/api/dashboard/<symbol>/news")
def dashboard_news_api(symbol):
    symbol = symbol.upper().strip()
    company_name = (
        request.args.get("company_name")
        or session.get("company_name")
        or COMPANY_MAP.get(symbol)
        or symbol
    ).strip()
    try:
        news, summary = process_news_data(symbol, company_name)
        update_dashboard_ai_section(symbol, "news", news, "news_summary", summary)
        return jsonify(
            {
                "success": True,
                "news": make_json_safe(news),
                "summary": make_json_safe(summary),
            }
        )
    except Exception as error:
        print(f"[NEWS API ERROR] {symbol}:", error)
        return jsonify(
            {"success": False, "message": "Unable to load company news right now."}
        ), 500


@app.route("/api/dashboard/<symbol>/news-stream")
@rate_limit(20, 3600)
def dashboard_news_stream_api(symbol):
    symbol = symbol.upper().strip()

    company_name = (
        request.args.get("company_name")
        or session.get("company_name")
        or COMPANY_MAP.get(symbol)
        or symbol
    ).strip()

    def generate():
        completed_news = []

        try:
            yield (
                json.dumps(
                    {
                        "type": "status",
                        "stage": "collecting",
                        "message": ("Collecting recent company news..."),
                    }
                )
                + "\n"
            )

            news_data = get_google_news_cached(symbol, company_name)

            feed_raw = (news_data.get("feed", []) or [])[:20]

            yield (
                json.dumps(
                    {
                        "type": "start",
                        "total": len(feed_raw),
                        "symbol": symbol,
                        "company_name": company_name,
                    }
                )
                + "\n"
            )

            if not feed_raw:
                empty_summary = {
                    "total_articles": 0,
                    "bullish": 0,
                    "bearish": 0,
                    "neutral": 0,
                    "avg_score": 0,
                    "top_topic": "N/A",
                }

                yield json.dumps({"type": "summary", "summary": empty_summary}) + "\n"

                yield json.dumps({"type": "done", "total": 0}) + "\n"

                return

            yield (
                json.dumps(
                    {
                        "type": "status",
                        "stage": "analyzing",
                        "message": ("Analyzing company-specific news sentiment..."),
                    }
                )
                + "\n"
            )

            for analyzed_item in stream_news_sentiment(
                news_items=feed_raw, symbol=symbol, company_name=company_name
            ):
                ui_article = build_news_ui_article(analyzed_item, symbol)

                completed_news.append(ui_article)

                yield (
                    json.dumps(
                        {
                            "type": "article",
                            "index": len(completed_news),
                            "total": len(feed_raw),
                            "article": make_json_safe(ui_article),
                        },
                        default=str,
                    )
                    + "\n"
                )

            try:
                summary = build_news_summary(completed_news)

            except Exception as error:
                print(f"[NEWS SUMMARY ERROR] {symbol}:", error)

                summary = {
                    "total_articles": len(completed_news),
                    "bullish": 0,
                    "bearish": 0,
                    "neutral": len(completed_news),
                    "avg_score": 0,
                    "top_topic": "N/A",
                }

            try:
                update_dashboard_ai_section(
                    symbol=symbol,
                    section="news",
                    value=completed_news,
                    summary_key="news_summary",
                    summary_value=summary,
                    company_name=company_name,
                )

            except Exception as error:
                print(f"[NEWS CACHE UPDATE ERROR] {symbol}:", error)

            yield (
                json.dumps(
                    {"type": "summary", "summary": make_json_safe(summary)}, default=str
                )
                + "\n"
            )

            yield (
                json.dumps(
                    {"type": "done", "total": len(completed_news), "partial": False}
                )
                + "\n"
            )

        except GeneratorExit:
            print(f"[NEWS STREAM CLOSED] {symbol}")

        except Exception as error:
            print(f"[NEWS STREAM API ERROR] {symbol}:", error)

            if completed_news:
                try:
                    partial_summary = build_news_summary(completed_news)

                    yield (
                        json.dumps(
                            {
                                "type": "summary",
                                "summary": make_json_safe(partial_summary),
                            },
                            default=str,
                        )
                        + "\n"
                    )

                except Exception as summary_error:
                    print(f"[PARTIAL NEWS SUMMARY ERROR] {symbol}:", summary_error)

                yield (
                    json.dumps(
                        {
                            "type": "warning",
                            "message": (
                                "Some final news processing could not be completed."
                            ),
                            "loaded": len(completed_news),
                        }
                    )
                    + "\n"
                )

                yield (
                    json.dumps(
                        {"type": "done", "total": len(completed_news), "partial": True}
                    )
                    + "\n"
                )

            else:
                yield (
                    json.dumps(
                        {
                            "type": "error",
                            "message": ("Unable to load company news right now."),
                        }
                    )
                    + "\n"
                )

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": ("no-cache, no-store, must-revalidate"),
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/dashboard/<symbol>/earnings")
def dashboard_earnings_api(symbol):
    symbol = symbol.upper().strip()
    try:
        earnings = process_earnings_data(symbol)
        update_dashboard_ai_section(symbol, "earnings", earnings)
        return jsonify({"success": True, "earnings": make_json_safe(earnings)})
    except Exception as error:
        print(f"[EARNINGS API ERROR] {symbol}:", error)
        return jsonify(
            {
                "success": False,
                "message": "Unable to load earnings transcripts right now.",
            }
        ), 500


@app.route("/chart/<symbol>/<int:months>")
def insider_chart(symbol, months):

    insider_data = edgar_insider_api_adapter.get_insider_transactions(symbol)
    transactions_raw = insider_data.get("data", [])

    transactions = []

    for t in transactions_raw:
        transactions.append(
            {
                "date": t.get("transaction_date"),
                "type": "Buy" if t.get("acquisition_or_disposal") == "A" else "Sell",
                "shares": t.get("shares"),
            }
        )

    chart = create_insider_chart(transactions, months)

    return jsonify({"chart": chart})


@app.route("/company-info/<symbol>")
def company_info_api(symbol):
    try:
        return jsonify({"success": True, "data": get_company_info(symbol)})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


def get_company_info(symbol):
    ticker = yf.Ticker(symbol)

    info = ticker.get_info()
    fast = ticker.fast_info

    price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or safe_get(fast, "last_price")
    )
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
            "website": info.get("website") or "",
        },
        "market": {
            "price": format_large_number(price),
            "previous_close": format_large_number(previous_close),
            "open": format_large_number(open_price),
            "day_range": f"{format_number(day_low)} - {format_number(day_high)}",
            "week_52_range": info.get("fiftyTwoWeekRange")
            or f"{format_number(year_low)} - {format_number(year_high)}",
            "volume": format_integer(volume),
            "market_cap": format_large_number(market_cap),
        },
        "valuation": {
            "forward_pe": format_number(info.get("forwardPE")),
            "price_to_book": format_number(info.get("priceToBook")),
            "price_to_sales": format_number(info.get("priceToSalesTrailing12Months")),
            "enterprise_value": format_large_number(info.get("enterpriseValue")),
            "beta": format_number(info.get("beta")),
        },
        "financial_health": {
            "revenue": format_large_number(info.get("totalRevenue")),
            "gross_margin": format_percent(info.get("grossMargins")),
            "operating_margin": format_percent(info.get("operatingMargins")),
            "profit_margin": format_percent(info.get("profitMargins")),
            "free_cashflow": format_large_number(info.get("freeCashflow")),
            "total_cash": format_large_number(info.get("totalCash")),
            "total_debt": format_large_number(info.get("totalDebt")),
        },
        "analyst": {
            "target_low": format_large_number(info.get("targetLowPrice")),
            "target_mean": format_large_number(info.get("targetMeanPrice")),
            "target_high": format_large_number(info.get("targetHighPrice")),
            "analyst_opinions": info.get("numberOfAnalystOpinions") or "N/A",
        },
    }

    return data


@app.route("/insider", methods=["GET"])
def insider_dashboard():
    ticker = (request.args.get("ticker") or session.get("ticker") or "").upper().strip()

    if not ticker:
        return jsonify({"success": False, "message": "Ticker is required"}), 400

    try:
        result = get_cached_smart_money_result(ticker)

        if not result:
            result = build_smart_money_result(ticker)

        return jsonify({"success": True, "data": result["summary"]})

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 404

    except Exception as error:
        print(f"[SMART MONEY ERROR] {ticker}:", error)

        return jsonify(
            {
                "success": False,
                "message": ("Unable to generate Smart Money Intelligence right now."),
            }
        ), 500


@app.route("/api/smart-money/<symbol>/ai-explanation-stream", methods=["POST"])
@rate_limit(20, 3600)
def smart_money_ai_explanation_stream(symbol):
    symbol = symbol.upper().strip()

    def generate():
        try:
            smart_money_result = get_cached_smart_money_result(symbol)

            # The user does not need to open Smart Money first.
            if not smart_money_result:
                smart_money_result = build_smart_money_result(symbol)

            for chunk in stream_smart_money_ai_explanation(smart_money_result):
                yield chunk

        except ValueError as error:
            yield str(error)

        except Exception as error:
            print(f"[SMART MONEY AI ROUTE ERROR] {symbol}:", error)

            yield ("Smart Money AI explanation could not be generated right now.")

    return Response(
        generate(),
        mimetype="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/ticker-list")
def ticker_list():
    return jsonify(TICKERS)


@app.route("/api/stocks")
def get_stocks():
    global stock_refreshing

    now = time.time()
    cache_is_fresh = stock_cache and now - last_updated < CACHE_INTERVAL

    # If cache is fresh, return immediately
    if cache_is_fresh:
        quotes = stock_cache

    else:
        # If no refresh is running, start one in background
        with stock_cache_lock:
            if not stock_refreshing:
                stock_refreshing = True
                threading.Thread(target=refresh_quotes_background, daemon=True).start()

        # Return current cache immediately while refresh happens
        quotes = stock_cache

    ordered_data = []
    PRIORITY = ["AAPL", "MSFT", "NVDA", "TSLA"]

    for ticker in PRIORITY + [t for t in TICKERS if t not in PRIORITY]:
        item = quotes.get(ticker, {"price": "--", "change": 0, "percent": 0})

        ordered_data.append({"symbol": ticker, **item})

    return jsonify(
        {"data": ordered_data, "updated": last_updated, "refreshing": stock_refreshing}
    )


def refresh_quotes_background():
    global stock_cache, last_updated, stock_refreshing

    try:
        updated_cache = fetch_quotes()

        with stock_cache_lock:
            stock_cache = updated_cache
            last_updated = time.time()

    except Exception as error:
        print("[BACKGROUND QUOTE REFRESH ERROR]", error)

    finally:
        with stock_cache_lock:
            stock_refreshing = False


def fetch_quotes():
    global stock_cache, last_updated

    now = time.time()

    # Return cache if still fresh
    if stock_cache and now - last_updated < CACHE_INTERVAL:
        return stock_cache

    updated_cache = (
        stock_cache.copy()
        if stock_cache
        else {ticker: {"price": "--", "change": 0} for ticker in TICKERS}
    )

    for ticker in TICKERS:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"

            response = requests.get(url, timeout=8)
            response.raise_for_status()

            data = response.json()

            price = data.get("c")
            previous_close = data.get("pc")

            if price and previous_close:
                change = ((price - previous_close) / previous_close) * 100

                updated_cache[ticker] = {
                    "price": round(price, 2),
                    "change": round(change, 2),
                }

        except requests.exceptions.Timeout:
            print(f"Finnhub timeout for {ticker}. Keeping old cached value.")

        except requests.exceptions.RequestException as e:
            print(f"Finnhub request error for {ticker}: {e}. Keeping old cached value.")

        except Exception as e:
            print(
                f"Unexpected quote error for {ticker}: {e}. Keeping old cached value."
            )

        # Small delay helps avoid hammering Finnhub
        time.sleep(0.15)

    stock_cache = updated_cache
    last_updated = now

    return stock_cache


@app.route("/smart-money-trend", methods=["GET"])
def smart_money_trend_page():
    return render_template("smartmoney_trend.html")


@app.route("/api/smart-money-trend", methods=["GET"])
@rate_limit(30, 3600)
def smart_money_trend_api():
    query = request.args.get("query")
    if not query:
        return jsonify({"success": False, "message": "Query is required"}), 400
    try:
        result = manager_portfolio_service.analyze(
            query, limit=6, bubble_limit_per_report=75
        )
        result = make_json_safe(result)
        status = 200 if result.get("success") else 404
        return jsonify(make_json_safe(result)), status
    except Exception as e:
        print(f"[SMART MONEY TREND ERROR] {query}: {e}")
        return jsonify(
            {"success": False, "message": "Failed to load Smart Money Trend data"}
        ), 500


@app.route("/api/company-dashboard/<symbol>/ai-analysis-stream", methods=["POST"])
@rate_limit(20, 3600)
def company_dashboard_ai_analysis_stream(symbol):
    symbol = symbol.upper().strip()

    dashboard_data = dashboard_ai_data_cache.get(symbol)

    if not dashboard_data:

        def missing_data_stream():
            yield "Dashboard data was not found. Please search the company again, then run AI analysis."

        return Response(missing_data_stream(), mimetype="text/plain")

    def generate():
        for chunk in stream_dashboard_ai_analysis(dashboard_data):
            yield chunk

    return Response(generate(), mimetype="text/plain")


@app.route("/api/predict/<symbol>/ai-analysis-stream", methods=["POST"])
@rate_limit(20, 3600)
def predict_stock_ai_analysis_stream(symbol):
    symbol = symbol.upper().strip()

    try:
        payload = request.get_json(silent=True) or {}
        forecast_data = payload.get("forecast_data")

        if not forecast_data:
            forecast_data = build_prediction_response(symbol)

        forecast_data["symbol"] = symbol

        def generate():
            for chunk in stream_forecast_ai_analysis(forecast_data):
                yield chunk

        return Response(generate(), mimetype="text/plain")

    except Exception as error:
        print("[FORECAST AI STREAM ERROR]", error)

        def error_stream():
            yield "Forecast AI analysis failed. Please try again later."

        return Response(error_stream(), mimetype="text/plain")


@app.route("/api/predict/<symbol>/stream")
@rate_limit(8, 3600)
def predict_stock_stream(symbol):
    symbol = symbol.upper().strip()

    event_queue = queue.Queue()

    def status_callback(message, stage="running", extra=None):
        event_queue.put(
            {"type": "status", "stage": stage, "message": message, "extra": extra or {}}
        )

    def worker():
        try:
            status_callback(f"Request received for {symbol}.", "start")
            result = build_prediction_response(symbol, status_callback=status_callback)

            event_queue.put({"type": "result", "data": result})

        except Exception as error:
            print("[PREDICTION STREAM ERROR]", error)

            event_queue.put({"type": "error", "message": str(error)})

        finally:
            event_queue.put({"type": "done"})

    threading.Thread(target=worker, daemon=True).start()

    def generate():
        while True:
            event = event_queue.get()

            yield json.dumps(event, default=str) + "\n"

            if event.get("type") in ["done", "error"]:
                break

    return Response(generate(), mimetype="application/x-ndjson")


@app.route("/prediction")
def prediction():
    return render_template("prediction.html")


@app.route("/api/predict/<symbol>")
@rate_limit(8, 3600)
def predict_stock(symbol):
    symbol = symbol.upper().strip()

    try:
        result = build_prediction_response(symbol)
        return jsonify(result)

    except Exception as error:
        return jsonify({"error": True, "message": str(error)}), 400


@app.route("/search")
def search_symbols():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"success": True, "results": []})

    try:
        search = yf.Search(
            query, max_results=8, news_count=0, lists_count=0, include_research=False
        )

        quotes = search.quotes or []

        results = []

        for item in quotes:
            symbol = item.get("symbol")
            name = item.get("shortname") or item.get("longname") or item.get("name")
            exchange = item.get("exchange") or item.get("exchDisp")
            quote_type = item.get("quoteType")

            if symbol and name:
                results.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "exchange": exchange,
                        "type": quote_type,
                    }
                )

        return jsonify({"success": True, "results": results})

    except Exception as error:
        return jsonify({"success": False, "message": str(error), "results": []}), 400


def clean_transcript_text(text):
    if not text:
        return ""

    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def make_transcript_preview(text, max_chars=900):
    if not text:
        return "Transcript is not available."

    clean_text = clean_transcript_text(text)

    if len(clean_text) <= max_chars:
        return clean_text

    return clean_text[:max_chars].rsplit(" ", 1)[0] + "..."


def get_previous_quarter(year, quarter):
    year = int(year)
    quarter = int(quarter)

    if quarter == 1:
        return year - 1, 4

    return year, quarter - 1


def get_roic_period(item):
    if not isinstance(item, dict):
        return None

    year = item.get("year") or item.get("fiscal_year")
    quarter = item.get("quarter") or item.get("fiscal_quarter")

    # Alpha Vantage identifies a period as one value such as "2026Q2".
    # ROIC normally returns separate integer year and quarter values.
    quarter_match = re.fullmatch(r"(\d{4})Q([1-4])", str(quarter).upper())

    if quarter_match:
        return int(quarter_match.group(1)), int(quarter_match.group(2))

    if isinstance(quarter, str):
        quarter = quarter.upper().removeprefix("Q")

    try:
        year = int(year)
        quarter = int(quarter)
    except (TypeError, ValueError):
        return None

    if quarter not in (1, 2, 3, 4):
        return None

    return year, quarter


def extract_roic_periods(payload):
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []

        for key in (
            "data",
            "items",
            "earnings_calls",
            "earningsCalls",
            "calls",
            "transcripts",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                rows = value
                break

            if isinstance(value, dict):
                rows = list(value.values())
                break
    else:
        rows = []

    periods = []
    seen = set()

    for row in rows:
        period = get_roic_period(row)

        if period and period not in seen:
            periods.append(period)
            seen.add(period)

    return sorted(periods, reverse=True)


def get_roic_transcript_text(data):
    if not isinstance(data, dict):
        return ""

    transcript = data.get("content") or data.get("transcript") or ""

    if isinstance(transcript, str):
        return clean_transcript_text(transcript)

    if not isinstance(transcript, list):
        return ""

    sections = []

    for section in transcript:
        if isinstance(section, str):
            text = section.strip()

            if text:
                sections.append(text)

            continue

        if not isinstance(section, dict):
            continue

        speaker = str(section.get("speaker") or "").strip()
        text = str(section.get("text") or section.get("content") or "").strip()

        if not text:
            continue

        sections.append(f"{speaker}: {text}" if speaker else text)

    return clean_transcript_text("\n\n".join(sections))


def build_earnings_item(symbol, transcript_data, fallback_year=None, fallback_quarter=None):
    if not isinstance(transcript_data, dict):
        return None

    transcript_text = get_roic_transcript_text(transcript_data)

    if not transcript_text:
        return None

    period = get_roic_period(transcript_data)

    if period:
        year, quarter = period
    else:
        try:
            year = int(fallback_year)
            quarter = int(fallback_quarter)
        except (TypeError, ValueError):
            return None

    return {
        "symbol": transcript_data.get("symbol", symbol),
        "year": year,
        "quarter": quarter,
        "date": transcript_data.get("date", ""),
        "title": f"{symbol} Q{quarter} {year} Earnings Call Transcript",
        "preview": make_transcript_preview(transcript_text),
        "transcript": transcript_text,
    }


def fetch_roic_json(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            print("[ROIC API ERROR]", response.status_code, response.text[:300])
            return None

        return response.json()

    except (requests.RequestException, ValueError) as error:
        print("[ROIC REQUEST ERROR]", error)
        return None


def fetch_alpha_vantage_transcript(symbol, year, quarter):
    """Fetch one specific transcript as a freshness fallback for ROIC."""

    if not API_KEY:
        return None

    try:
        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "EARNINGS_CALL_TRANSCRIPT",
                "symbol": symbol,
                "quarter": f"{year}Q{quarter}",
                "apikey": API_KEY,
            },
            timeout=15,
        )

        if response.status_code != 200:
            print(
                "[ALPHA VANTAGE TRANSCRIPT ERROR]",
                response.status_code,
                response.text[:300],
            )
            return None

        transcript_data = response.json()

        if not is_valid_api_response(transcript_data):
            print(
                "[ALPHA VANTAGE TRANSCRIPT UNAVAILABLE]",
                symbol,
                f"{year}Q{quarter}",
            )
            return None

        return build_earnings_item(
            symbol,
            transcript_data,
            fallback_year=year,
            fallback_quarter=quarter,
        )

    except (requests.RequestException, ValueError) as error:
        print("[ALPHA VANTAGE TRANSCRIPT REQUEST ERROR]", error)
        return None


def get_recent_periods_newer_than(period, max_periods=4):
    """Return recent fiscal-quarter candidates newer than ``period``."""

    now = datetime.utcnow()
    year = now.year
    quarter = ((now.month - 1) // 3) + 1
    periods = []

    while len(periods) < max_periods:
        candidate = (year, quarter)

        if period and candidate <= period:
            break

        periods.append(candidate)
        year, quarter = get_previous_quarter(year, quarter)

    return periods


def fetch_earnings_transcripts(symbol):
    """
    Fetch the three most recent available transcripts.

    ROIC remains the primary source. Alpha Vantage checks only quarters newer
    than ROIC's newest result so a provider delay does not hide a newly released
    call and the Alpha Vantage request count stays small.
    """

    symbol = (symbol or "").upper().strip()

    if not symbol:
        return {"available": False, "message": "A ticker symbol is required.", "items": []}

    if not ROIC_API_KEY and not API_KEY:
        return {
            "available": False,
            "message": "Earnings transcript API keys are missing.",
            "items": [],
        }

    api_params = {"apikey": ROIC_API_KEY}
    latest_url = f"https://api.roic.ai/v2/company/earnings-calls/latest/{symbol}"
    list_url = f"https://api.roic.ai/v2/company/earnings-calls/list/{symbol}"

    latest_data = (
        fetch_roic_json(latest_url, params=api_params) if ROIC_API_KEY else None
    )
    list_data = fetch_roic_json(list_url, params=api_params) if ROIC_API_KEY else None

    earnings_items = []
    loaded_periods = set()
    attempted_periods = set()

    latest_item = build_earnings_item(symbol, latest_data)

    if latest_item:
        latest_period = (latest_item["year"], latest_item["quarter"])
        earnings_items.append(latest_item)
        loaded_periods.add(latest_period)

    periods = extract_roic_periods(list_data)
    latest_period = get_roic_period(latest_data)

    if latest_period and latest_period not in periods:
        periods.insert(0, latest_period)

    for year, quarter in periods:
        if len(earnings_items) >= 3:
            break

        period = (year, quarter)

        if period in loaded_periods:
            continue

        attempted_periods.add(period)
        transcript_url = (
            f"https://api.roic.ai/v2/company/earnings-calls/transcript/{symbol}"
        )
        transcript_data = fetch_roic_json(
            transcript_url,
            params={
                "apikey": ROIC_API_KEY,
                "year": year,
                "quarter": quarter,
            },
        )
        item = build_earnings_item(
            symbol,
            transcript_data,
            fallback_year=year,
            fallback_quarter=quarter,
        )

        if item:
            earnings_items.append(item)
            loaded_periods.add(period)

    # If the list endpoint is incomplete or unavailable, search older periods
    # until three real transcripts are found. This also tolerates missing calls.
    if len(earnings_items) < 3:
        if periods:
            year, quarter = periods[-1]
        elif latest_period:
            year, quarter = latest_period
        else:
            year, quarter = datetime.utcnow().year, 4

        year, quarter = get_previous_quarter(year, quarter)

        for _ in range(12):
            if len(earnings_items) >= 3:
                break

            period = (year, quarter)

            if period not in loaded_periods and period not in attempted_periods:
                attempted_periods.add(period)
                transcript_url = (
                    f"https://api.roic.ai/v2/company/earnings-calls/transcript/{symbol}"
                )
                transcript_data = fetch_roic_json(
                    transcript_url,
                    params={
                        "apikey": ROIC_API_KEY,
                        "year": year,
                        "quarter": quarter,
                    },
                )
                item = build_earnings_item(
                    symbol,
                    transcript_data,
                    fallback_year=year,
                    fallback_quarter=quarter,
                )

                if item:
                    earnings_items.append(item)
                    loaded_periods.add(period)

            year, quarter = get_previous_quarter(year, quarter)

    newest_roic_period = latest_period or (periods[0] if periods else None)

    # ROIC can lag a newly published call. Ask Alpha Vantage only for periods
    # that could be newer, merge any real transcript, then sort all sources.
    for year, quarter in get_recent_periods_newer_than(newest_roic_period):
        period = (year, quarter)

        if period in loaded_periods:
            continue

        item = fetch_alpha_vantage_transcript(symbol, year, quarter)

        if item:
            earnings_items.append(item)
            loaded_periods.add(period)

    earnings_items.sort(
        key=lambda item: (int(item["year"]), int(item["quarter"])),
        reverse=True,
    )

    return {
        "available": bool(earnings_items),
        "message": (
            "Earnings transcripts loaded."
            if earnings_items
            else "No earnings transcripts found."
        ),
        "items": earnings_items[:3],
    }


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
    app.run(debug=True)
