import os
import json
import time
import hashlib
import requests
from pathlib import Path
import re

AI_SUMMARY_ENABLED = os.getenv("AI_SUMMARY_ENABLED", "true").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:latest"
)
OLLAMA_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "600")
)
NEWS_SENTIMENT_BATCH_SIZE = int(
    os.getenv("NEWS_SENTIMENT_BATCH_SIZE", "2")
)
OLLAMA_CONNECT_TIMEOUT = int(
    os.getenv("OLLAMA_CONNECT_TIMEOUT", "10")
)
OLLAMA_READ_TIMEOUT = int(
    os.getenv("OLLAMA_READ_TIMEOUT", "240")
)
CACHE_DIR = Path("cache/ai_summaries")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_MAX_AGE_SECONDS = 6 * 60 * 60


def _make_cache_key(page_type, symbol_or_query, data):
    raw = json.dumps(
        {
            "page_type": page_type,
            "symbol_or_query": symbol_or_query,
            "data": data
        },
        sort_keys=True,
        default=str
    )

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{page_type}_{symbol_or_query}_{digest}.json".replace("/", "_").replace(" ", "_")


def _load_ai_cache(cache_key):
    path = CACHE_DIR / cache_key

    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as file:
            cached = json.load(file)

        created_at = cached.get("created_at", 0)

        if time.time() - created_at > CACHE_MAX_AGE_SECONDS:
            return None

        return cached.get("result")

    except Exception as error:
        print("[AI CACHE READ ERROR]", error)
        return None


def _save_ai_cache(cache_key, result):
    path = CACHE_DIR / cache_key

    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "created_at": time.time(),
                    "result": result
                },
                file,
                indent=2
            )

    except Exception as error:
        print("[AI CACHE WRITE ERROR]", error)


def _clean_data_for_ai(data, max_items=15):
    """
    Keeps the AI input small so Ollama does not get overloaded.
    Large chart arrays are trimmed.
    """

    if isinstance(data, dict):
        cleaned = {}

        for key, value in data.items():
            if key in ["labels", "actual", "predicted", "upper_band", "lower_band", "upperBand", "lowerBand"]:
                if isinstance(value, list):
                    cleaned[key] = value[-max_items:]
                else:
                    cleaned[key] = value

            elif isinstance(value, list):
                cleaned[key] = value[:max_items]

            elif isinstance(value, dict):
                cleaned[key] = _clean_data_for_ai(value, max_items=max_items)

            else:
                cleaned[key] = value

        return cleaned

    if isinstance(data, list):
        return data[:max_items]

    return data

def _prepare_smart_money_ai_payload(data):
    """
    Creates a compact AI input from the already-calculated
    Smart Money Intelligence result.

    No scores, signals or transaction classifications
    are recalculated here.
    """

    summary = data.get("summary") or {}

    signals = summary.get("signals") or []
    transactions = (
        summary.get("recent_transactions")
        or []
    )

    compact_signals = []

    for signal in signals:
        compact_signals.append({
            "signal": signal.get("signal"),
            "score": signal.get("score"),
            "description": signal.get(
                "description"
            )
        })

    compact_transactions = []

    for transaction in transactions[:30]:
        compact_transactions.append({
            "date": transaction.get("date"),
            "insider": transaction.get("insider"),
            "role": transaction.get("role"),
            "type": transaction.get("type"),
            "code": transaction.get("code"),
            "shares": transaction.get("shares"),
            "value": transaction.get("value"),
            "price": transaction.get("price"),
            "net_change": transaction.get(
                "net_change"
            ),
            "net_value": transaction.get(
                "net_value"
            ),
            "remaining_shares": transaction.get(
                "remaining_shares"
            )
        })

    return {
        "company": {
            "symbol": data.get("symbol"),
            "name": (
                data.get("company")
                or summary.get("company")
            )
        },

        "scores": {
            "insider_score": summary.get(
                "insider_score"
            ),
            "smart_money_score": summary.get(
                "smart_money_score"
            ),
            "insider_momentum": summary.get(
                "insider_momentum"
            ),
            "bullish": summary.get("bullish"),
            "bearish": summary.get("bearish"),
            "cluster_buying": summary.get(
                "cluster_buying"
            )
        },

        "activity_counts": {
            "buys": summary.get("total_buys"),
            "sells": summary.get("total_sells"),
            "taxes": summary.get("total_taxes"),
            "grants": summary.get("total_grants"),
            "net_activity": summary.get(
                "net_activity"
            )
        },

        "summary_stats": (
            summary.get("summary_stats")
            or {}
        ),

        "signals": compact_signals,

        "signal_groups": (
            summary.get("signal_groups")
            or {}
        ),

        "recent_transactions": (
            compact_transactions
        )
    }

def stream_smart_money_ai_explanation(smart_money_data):
    """Stream a narrative explanation of Smart Money Intelligence results."""

    if not AI_SUMMARY_ENABLED:
        yield "AI Smart Money explanation is disabled on this server."
        return

    payload = _prepare_smart_money_ai_payload(smart_money_data)

    system_instruction = """
You are InsiderAI, a professional SEC Form 4 insider-activity analyst.

You receive a pre-calculated Smart Money Intelligence result.

Your task is to interpret the supplied result for an investor.

Write a concise narrative analysis using normal prose.

Use exactly these headings:

SMART MONEY INTERPRETATION

WHAT IS DRIVING THE SCORE

IMPORTANT INSIDER PATTERNS

INTENTIONAL VS ADMINISTRATIVE ACTIVITY

CONFIRMING AND CONFLICTING SIGNALS

WHAT THE DASHBOARD MAY OVERSTATE OR UNDERSTATE

LIMITATIONS

WHAT TO MONITOR NEXT

Interpretation requirements:
- Explain the Smart Money Score and insider momentum together.
- Explain what activity is primarily driving the score.
- Separate BUY and SELL activity from Tax and Grant activity.
- Discuss repeated insider behavior and transaction-date clusters.
- Give greater weight to CEO, CFO, president, COO, chairman,
  and other senior operating roles.
- Use remaining ownership information when available.
- Explain whether the evidence behind the score is strong or weak.
- Mention specific people, dates, shares, and values only when useful.
- Keep the total response under 650 words.
"""

    user_prompt = f"""
Analyze the following pre-calculated Smart Money Intelligence result.

Do not repeat or reformat the data.
Begin immediately with the heading SMART MONEY INTERPRETATION.

SMART MONEY DATA:
{json.dumps(payload, separators=(",", ":"), default=str)}
"""

    request_payload = {
        "model": OLLAMA_MODEL,
        "system": system_instruction,
        "prompt": user_prompt,
        "stream": True,
        "keep_alive": "15m",
        "options": {
            "temperature": 0.15,
            "num_ctx": 4096,
            "num_predict": 450,
            "repeat_penalty": 1.1,
        },
    }

    request_started_at = time.perf_counter()

    print(
        "[SMART MONEY AI REQUEST START] "
        f"model={OLLAMA_MODEL} url={OLLAMA_URL}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json=request_payload,
            stream=True,
            timeout=(
                OLLAMA_CONNECT_TIMEOUT,
                OLLAMA_READ_TIMEOUT,
            ),
        )
        response.raise_for_status()

        response_time = time.perf_counter() - request_started_at

        print(
            "[SMART MONEY AI HTTP RESPONSE] "
            f"{response_time:.2f} seconds"
        )

        first_chunk_received = False
        started_output = False

        unwanted_openings = (
            "here is the json",
            "here's the json",
            "the json data",
            "```json",
        )

        for line in response.iter_lines():
            if not line:
                continue

            try:
                result = json.loads(
                    line.decode("utf-8")
                )
            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
            ) as error:
                print(
                    "[SMART MONEY AI PARSE ERROR]",
                    error,
                )
                continue

            chunk = result.get("response", "")

            if chunk and not first_chunk_received:
                first_chunk_received = True
                first_chunk_time = (
                    time.perf_counter()
                    - request_started_at
                )

                print(
                    "[SMART MONEY AI FIRST CHUNK] "
                    f"{first_chunk_time:.2f} seconds"
                )

            if chunk and not started_output:
                normalized_chunk = chunk.strip().lower()

                if normalized_chunk.startswith(
                    unwanted_openings
                ):
                    continue

                started_output = True

            if chunk:
                yield chunk

            if result.get("done"):
                total_time = (
                    time.perf_counter()
                    - request_started_at
                )

                print(
                    "[SMART MONEY AI COMPLETE] "
                    f"{total_time:.2f} seconds"
                )
                break

        if not first_chunk_received:
            print(
                "[SMART MONEY AI EMPTY RESPONSE] "
                "Ollama completed without returning text."
            )

            yield (
                "The AI model completed the request but "
                "did not return an explanation."
            )

    except requests.exceptions.ConnectionError as error:
        print(
            "[SMART MONEY AI CONNECTION ERROR]",
            error,
        )

        yield (
            "Smart Money AI explanation is unavailable because "
            "the Ollama service could not be reached."
        )

    except requests.exceptions.Timeout as error:
        elapsed_time = (
            time.perf_counter()
            - request_started_at
        )

        print(
            "[SMART MONEY AI TIMEOUT] "
            f"after {elapsed_time:.2f} seconds:",
            error,
        )

        yield (
            "Smart Money AI explanation timed out before "
            "the model completed its response."
        )

    except requests.exceptions.RequestException as error:
        print(
            "[SMART MONEY AI REQUEST ERROR]",
            error,
        )

        yield (
            "Smart Money AI explanation could not be completed "
            "because the model request failed."
        )

    except GeneratorExit:
        elapsed_time = (
            time.perf_counter()
            - request_started_at
        )

        print(
            "[SMART MONEY AI STREAM CLOSED] "
            f"after {elapsed_time:.2f} seconds"
        )

        raise

    except Exception as error:
        print(
            "[SMART MONEY AI ERROR]",
            error,
        )

        yield (
            "Smart Money AI explanation is unavailable "
            "right now."
        )

def stream_dashboard_ai_analysis(company_data):
    """
    Streams Ollama response chunks for Dashboard 1 AI analysis.
    Used by Flask Response/event-stream.
    """

    if not AI_SUMMARY_ENABLED:
        yield "AI Analyst Summary is disabled on this server."
        return

    symbol = company_data.get("symbol", "UNKNOWN")
    name = company_data.get("name", symbol)

    cleaned_data = _clean_data_for_ai(company_data)

    instruction = """
You are InsiderAI's Company Intelligence Analyst.

Analyze:
- Insider transactions
- Institutional holdings
- News and sentiment
- Earnings call transcripts

Your goal:
Identify the company's current situation, future pipeline, management priorities,
growth areas, early business signals, and risk factors.

Rules:
- Do not give buy, sell, or hold advice.
- Do not guarantee future performance.
- Do not invent facts.
- Use only the provided data.
- Be detailed, clear, and professional.
- Focus strongly on news and earnings transcript clues.
- Explain what the company is developing, what management is emphasizing,
  and what investors should monitor next.

Return in this structure:

1. Executive Summary
2. Insider Activity Reading
3. Institutional Ownership Reading
4. News And Sentiment Reading
5. Earnings Call / Pipeline Reading
6. Future Development Signals
7. Bullish Evidence
8. Bearish / Risk Evidence
9. Conflicting Signals
10. What To Monitor Next
11. Final Interpretation
"""

    prompt = f"""
{instruction}

Company:
{name} ({symbol})

Dashboard Data:
{json.dumps(cleaned_data, indent=2, default=str)}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1200
                }
            },
            stream=True,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            try:
                payload = json.loads(line.decode("utf-8"))
                chunk = payload.get("response", "")

                if chunk:
                    yield chunk

                if payload.get("done"):
                    break

            except Exception as error:
                print("[OLLAMA STREAM PARSE ERROR]", error)
                continue

    except requests.exceptions.ConnectionError:
        yield "AI Analyst Summary is unavailable because the Ollama service could not be reached."

    except requests.exceptions.Timeout:
        yield "AI Analyst Summary timed out. The model may be too slow for this server."

    except Exception as error:
        print("[OLLAMA STREAM ERROR]", error)
        yield "AI Analyst Summary is unavailable right now."

def stream_forecast_ai_analysis(forecast_data):
    if not AI_SUMMARY_ENABLED:
        yield "AI Analyst Summary is disabled on this server."
        return

    symbol = forecast_data.get("symbol", "UNKNOWN")
    cleaned_data = _clean_data_for_ai(forecast_data)

    instruction = """
You are InsiderAI's Forecast Analyst.

Analyze the stock forecast dashboard data.
The numeric forecast is already created by the app's LSTM/consensus model.
Your job is to explain the forecast, not create a new prediction.

Rules:
- Do not give buy, sell, or hold advice.
- Do not invent prices or percentages.
- Use only the provided forecast data.
- Explain the current price, predicted price, expected move, direction, confidence, risk, and signal breakdown.
- If LSTM, trend, momentum, and volatility conflict, explain that.
- If confidence is low, explain why.
- If risk is high, explain what causes it.
- Explain the forecast range and what the user should monitor next.
- Write like a professional AI analyst.

Return in this structure:

1. Executive Summary
2. Forecast Reading
3. Signal Breakdown
4. Bullish Evidence
5. Bearish / Risk Evidence
6. Confidence And Reliability
7. Forecast Range Interpretation
8. What To Monitor Next
9. Final Interpretation
"""

    prompt = f"""
{instruction}

Symbol:
{symbol}

Forecast Data:
{json.dumps(cleaned_data, indent=2, default=str)}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1000
                }
            },
            stream=True,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            try:
                payload = json.loads(line.decode("utf-8"))
                chunk = payload.get("response", "")

                if chunk:
                    yield chunk

                if payload.get("done"):
                    break

            except Exception as error:
                print("[FORECAST OLLAMA STREAM PARSE ERROR]", error)
                continue

    except requests.exceptions.ConnectionError:
        yield "AI Analyst Summary is not available because Ollama is not running on this machine."

    except requests.exceptions.Timeout:
        yield "AI Analyst Summary timed out. The model may be too slow for this server."

    except Exception as error:
        print("[FORECAST OLLAMA STREAM ERROR]", error)
        yield "AI Analyst Summary is unavailable right now."

def stream_news_sentiment(
    news_items,
    symbol,
    company_name=None
):
    """
    Analyzes news in small batches and yields each completed
    article immediately.

    Each yielded value is a fully merged article dictionary.
    """

    symbol = str(
        symbol or ""
    ).upper().strip()

    company_name = str(
        company_name or symbol
    ).strip()

    if not news_items:
        return

    prepared_articles = []
    article_lookup = {}

    for article in news_items:
        article_copy = dict(article)

        title = str(
            article_copy.get("title") or ""
        ).strip()

        summary = str(
            article_copy.get("summary") or ""
        ).strip()

        source = str(
            article_copy.get("source") or ""
        ).strip()

        url = str(
            article_copy.get("url") or ""
        ).strip()

        raw_identifier = (
            f"{symbol}|{url}|{title}"
        )

        article_id = hashlib.sha256(
            raw_identifier.encode("utf-8")
        ).hexdigest()[:16]

        article_copy["news_id"] = article_id

        article_lookup[article_id] = article_copy

        prepared_articles.append({
            "id": article_id,
            "title": title[:500],
            "summary": summary[:1200],
            "source": source[:200]
        })

    if not AI_SUMMARY_ENABLED:
        for article in article_lookup.values():
            article["overall_sentiment_label"] = (
                "Neutral"
            )

            article["overall_sentiment_score"] = 0.0

            article["sentiment_reason"] = (
                "AI sentiment analysis is disabled."
            )

            yield article

        return

    for start in range(
        0,
        len(prepared_articles),
        NEWS_SENTIMENT_BATCH_SIZE
    ):
        batch = prepared_articles[
            start:
            start + NEWS_SENTIMENT_BATCH_SIZE
        ]

        batch_ids = {
            item["id"]
            for item in batch
        }

        try:
            batch_result = (
                _analyze_news_sentiment_batch(
                    articles=batch,
                    symbol=symbol,
                    company_name=company_name
                )
            )

            result_map = {
                result.get("id"): result
                for result in batch_result.get(
                    "results",
                    []
                )
                if result.get("id")
            }

            for article_id in batch_ids:
                article = dict(
                    article_lookup[article_id]
                )

                sentiment = result_map.get(
                    article_id
                )

                if sentiment:
                    article[
                        "overall_sentiment_label"
                    ] = (
                        sentiment.get(
                            "overall_sentiment_label"
                        )
                        or "Neutral"
                    )

                    try:
                        article[
                            "overall_sentiment_score"
                        ] = float(
                            sentiment.get(
                                "overall_sentiment_score"
                            )
                            or 0
                        )

                    except (
                        TypeError,
                        ValueError
                    ):
                        article[
                            "overall_sentiment_score"
                        ] = 0.0

                    article["sentiment_reason"] = (
                        sentiment.get("reason")
                        or (
                            "No clear company-specific "
                            "impact was identified."
                        )
                    )

                else:
                    article[
                        "overall_sentiment_label"
                    ] = "Neutral"

                    article[
                        "overall_sentiment_score"
                    ] = 0.0

                    article["sentiment_reason"] = (
                        "This article could not be "
                        "analyzed by the AI model."
                    )

                yield article

        except requests.exceptions.ConnectionError as error:
            print(
                "[NEWS STREAM CONNECTION ERROR]",
                symbol,
                start,
                error
            )

            for article_id in batch_ids:
                article = dict(
                    article_lookup[article_id]
                )

                article[
                    "overall_sentiment_label"
                ] = "Neutral"

                article[
                    "overall_sentiment_score"
                ] = 0.0

                article["sentiment_reason"] = (
                    "AI sentiment analysis was "
                    "temporarily unavailable."
                )

                yield article

        except requests.exceptions.Timeout as error:
            print(
                "[NEWS STREAM TIMEOUT]",
                symbol,
                start,
                error
            )

            for article_id in batch_ids:
                article = dict(
                    article_lookup[article_id]
                )

                article[
                    "overall_sentiment_label"
                ] = "Neutral"

                article[
                    "overall_sentiment_score"
                ] = 0.0

                article["sentiment_reason"] = (
                    "AI sentiment analysis timed out "
                    "for this article."
                )

                yield article

        except Exception as error:
            print(
                "[NEWS STREAM BATCH ERROR]",
                symbol,
                start,
                error
            )

            for article_id in batch_ids:
                article = dict(
                    article_lookup[article_id]
                )

                article[
                    "overall_sentiment_label"
                ] = "Neutral"

                article[
                    "overall_sentiment_score"
                ] = 0.0

                article["sentiment_reason"] = (
                    "This article could not be "
                    "analyzed."
                )

                yield article

def analyze_news_sentiment(news_items,symbol,company_name=None):
    symbol=str(symbol or "").upper().strip()
    company_name=str(company_name or symbol).strip()

    if not news_items:
        return []

    prepared_articles=[]

    for article in news_items:
        title=str(article.get("title") or "").strip()
        summary=str(article.get("summary") or "").strip()
        source=str(article.get("source") or "").strip()
        url=str(article.get("url") or "").strip()

        raw_identifier=f"{symbol}|{url}|{title}"
        article_id=hashlib.sha256(
            raw_identifier.encode("utf-8")
        ).hexdigest()[:16]

        article["news_id"]=article_id

        prepared_articles.append({
            "id":article_id,
            "title":title[:500],
            "summary":summary[:1200],
            "source":source[:200]
        })

    if not AI_SUMMARY_ENABLED:
        return _apply_default_news_sentiment(
            news_items,
            reason="AI sentiment analysis is disabled."
        )

    all_results=[]

    for start in range(0,len(prepared_articles),NEWS_SENTIMENT_BATCH_SIZE):
        batch=prepared_articles[
            start:start+NEWS_SENTIMENT_BATCH_SIZE
        ]

        try:
            batch_result=_analyze_news_sentiment_batch(
                articles=batch,
                symbol=symbol,
                company_name=company_name
            )

            all_results.extend(
                batch_result.get("results",[])
            )

        except requests.exceptions.ConnectionError as error:
            print(
                f"[NEWS SENTIMENT CONNECTION ERROR] "
                f"{symbol} batch {start}: {error}"
            )

        except requests.exceptions.Timeout as error:
            print(
                f"[NEWS SENTIMENT TIMEOUT] "
                f"{symbol} batch {start}: {error}"
            )

        except Exception as error:
            print(
                f"[NEWS SENTIMENT BATCH ERROR] "
                f"{symbol} batch {start}: {error}"
            )

    if not all_results:
        return _apply_default_news_sentiment(
            news_items,
            reason="AI sentiment analysis was unavailable."
        )

    return _merge_news_sentiment_results(
        news_items,
        {
            "results":all_results
        }
    )

def _analyze_news_sentiment_batch(articles,symbol,company_name):
    cache_key=_make_cache_key(
        "news_sentiment_batch",
        symbol,
        articles
    )

    cached_result=_load_ai_cache(cache_key)

    if cached_result:
        return cached_result

    instruction="""
You are InsiderAI's financial-news sentiment classifier.

Analyze each article from the perspective of the selected company.

Rules:
- Judge the likely effect on the selected company.
- Do not judge only the emotional tone of the headline.
- Do not invent missing facts.
- Return exactly one result for every article ID.
- Return valid JSON only.
- Do not return markdown or code fences.

Allowed labels:
- Bullish
- Bearish
- Neutral

Score:
- -1.0 strongly bearish
- 0.0 neutral
- 1.0 strongly bullish

Return exactly:

{
  "results":[
    {
      "id":"article-id",
      "overall_sentiment_label":"Bullish",
      "overall_sentiment_score":0.65,
      "reason":"One short sentence explaining the company-specific impact."
    }
  ]
}
"""

    prompt=f"""
{instruction}

Selected company:
{company_name}

Selected ticker:
{symbol}

Articles:
{json.dumps(articles,indent=2,ensure_ascii=False)}
"""

    response=requests.post(
        OLLAMA_URL,
        json={
            "model":OLLAMA_MODEL,
            "prompt":prompt,
            "stream":False,
            "format":"json",
            "options":{
                "temperature":0.1,
                "num_predict":900
            }
        },
        timeout=OLLAMA_TIMEOUT
    )

    response.raise_for_status()

    payload=response.json()
    raw_response=payload.get("response","")

    if not raw_response:
        raise ValueError("Ollama returned an empty response.")

    parsed_result=_parse_news_sentiment_response(
        raw_response
    )

    returned_ids={
        item.get("id")
        for item in parsed_result.get("results",[])
    }

    expected_ids={
        article.get("id")
        for article in articles
    }

    missing_ids=expected_ids-returned_ids

    if missing_ids:
        print(
            f"[NEWS SENTIMENT MISSING IDS] {symbol}:",
            missing_ids
        )

    _save_ai_cache(
        cache_key,
        parsed_result
    )

    return parsed_result

def _parse_news_sentiment_response(raw_response):
    if isinstance(raw_response, dict):
        parsed = raw_response
    else:
        text = str(raw_response or "").strip()

        if text.startswith("```"):
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                text,
                flags=re.I
            ).strip()

        parsed = json.loads(text)

    results = parsed.get("results", [])

    if not isinstance(results, list):
        raise ValueError("Ollama sentiment results must be a list.")

    validated = []

    for item in results:
        if not isinstance(item, dict):
            continue

        article_id = str(item.get("id") or "").strip()

        if not article_id:
            continue

        label = str(
            item.get("overall_sentiment_label") or "Neutral"
        ).strip().title()

        if label not in {"Bullish", "Bearish", "Neutral"}:
            label = "Neutral"

        try:
            score = float(
                item.get("overall_sentiment_score", 0)
            )
        except (TypeError, ValueError):
            score = 0.0

        score = round(max(-1.0, min(1.0, score)), 3)

        reason = str(
            item.get("reason")
            or "No clear company-specific impact was identified."
        ).strip()

        validated.append({
            "id": article_id,
            "overall_sentiment_label": label,
            "overall_sentiment_score": score,
            "reason": reason[:500]
        })

    return {
        "results": validated
    }


def _merge_news_sentiment_results(news_items,sentiment_payload):
    result_map={
        item.get("id"):item
        for item in sentiment_payload.get("results",[])
        if item.get("id")
    }

    merged=[]

    for article in news_items:
        article_copy=dict(article)
        article_id=article_copy.get("news_id")
        sentiment=result_map.get(article_id)

        if sentiment:
            article_copy["overall_sentiment_label"]=(
                sentiment.get("overall_sentiment_label")
                or "Neutral"
            )

            try:
                article_copy["overall_sentiment_score"]=float(
                    sentiment.get("overall_sentiment_score") or 0
                )
            except (TypeError,ValueError):
                article_copy["overall_sentiment_score"]=0.0

            article_copy["sentiment_reason"]=(
                sentiment.get("reason")
                or "No clear company-specific impact was identified."
            )
        else:
            article_copy["overall_sentiment_label"]="Neutral"
            article_copy["overall_sentiment_score"]=0.0
            article_copy["sentiment_reason"]=(
                "This article could not be analyzed by the AI model."
            )

        merged.append(article_copy)

    return merged


def _apply_default_news_sentiment(news_items, reason):
    output = []

    for article in news_items:
        article_copy = dict(article)

        if not article_copy.get("news_id"):
            raw_identifier = (
                f"{article_copy.get('url', '')}|"
                f"{article_copy.get('title', '')}"
            )

            article_copy["news_id"] = hashlib.sha256(
                raw_identifier.encode("utf-8")
            ).hexdigest()[:16]

        article_copy["overall_sentiment_label"] = "Neutral"
        article_copy["overall_sentiment_score"] = 0.0
        article_copy["sentiment_reason"] = reason

        output.append(article_copy)

    return output

