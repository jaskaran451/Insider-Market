import os
import json
import time
import hashlib
import requests
from pathlib import Path


AI_SUMMARY_ENABLED = os.getenv("AI_SUMMARY_ENABLED", "true").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "45"))

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
        yield "AI Analyst Summary is not available because Ollama is not running on this machine."

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

