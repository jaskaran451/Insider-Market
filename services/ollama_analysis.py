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


def _ollama_request(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 900
            }
        },
        timeout=OLLAMA_TIMEOUT
    )

    response.raise_for_status()
    result = response.json()

    return result.get("response", "").strip()


def generate_ai_analysis(page_type, symbol_or_query, data, custom_instruction=None):
    """
    Generic AI analysis function.
    It never crashes the app.
    It always returns a safe dictionary for frontend display.
    """

    if not AI_SUMMARY_ENABLED:
        return {
            "available": False,
            "status": "disabled",
            "model": None,
            "summary": None,
            "message": "AI Analyst Summary is disabled on this server."
        }

    cleaned_data = _clean_data_for_ai(data)
    cache_key = _make_cache_key(page_type, symbol_or_query, cleaned_data)

    cached = _load_ai_cache(cache_key)

    if cached:
        return cached

    default_instruction = """
You are InsiderAI's internal AI analyst.

Your job:
- Read the provided financial dashboard data.
- Explain what the data suggests.
- Do not give buy, sell, or hold advice.
- Do not make guarantees.
- Do not invent numbers.
- Use only the data provided.
- Be detailed but clear.
- Mention uncertainty and risk.
- Write for a retail investor who understands basic stock market terms.

Format your answer with these sections:

1. Executive Summary
2. Key Findings
3. Bullish Signals
4. Bearish / Risk Signals
5. Confidence Explanation
6. What To Monitor Next
7. Final Interpretation

Important:
- Do not say "I cannot provide financial advice" repeatedly.
- Do not recommend buying or selling.
- If data is weak or conflicting, say that clearly.
"""

    final_instruction = custom_instruction or default_instruction

    prompt = f"""
{final_instruction}

Dashboard Type:
{page_type}

Symbol or Query:
{symbol_or_query}

Dashboard Data:
{json.dumps(cleaned_data, indent=2, default=str)}
"""

    try:
        summary = _ollama_request(prompt)

        if not summary:
            raise ValueError("Ollama returned empty response.")

        result = {
            "available": True,
            "status": "success",
            "model": OLLAMA_MODEL,
            "summary": summary,
            "message": "AI Analyst Summary generated successfully."
        }

        _save_ai_cache(cache_key, result)

        return result

    except requests.exceptions.ConnectionError:
        return {
            "available": False,
            "status": "offline",
            "model": OLLAMA_MODEL,
            "summary": None,
            "message": "AI Analyst Summary is not available because Ollama is not running on this machine."
        }

    except requests.exceptions.Timeout:
        return {
            "available": False,
            "status": "timeout",
            "model": OLLAMA_MODEL,
            "summary": None,
            "message": "AI Analyst Summary timed out. The model may be too slow for this server."
        }

    except requests.exceptions.HTTPError as error:
        return {
            "available": False,
            "status": "model_error",
            "model": OLLAMA_MODEL,
            "summary": None,
            "message": f"AI Analyst Summary is unavailable. Ollama returned an error: {str(error)}"
        }

    except Exception as error:
        print("[AI ANALYSIS ERROR]", error)

        return {
            "available": False,
            "status": "error",
            "model": OLLAMA_MODEL,
            "summary": None,
            "message": "AI Analyst Summary is unavailable right now."
        }


def generate_forecast_ai_analysis(forecast_data):
    symbol = forecast_data.get("symbol", "UNKNOWN")

    instruction = """
You are InsiderAI's Forecast Analyst.

Analyze the stock forecast dashboard data.
The numeric forecast is already created by the app's LSTM/consensus model.
Your job is to explain the forecast, not create a new prediction.

Rules:
- Do not give buy/sell/hold advice.
- Do not invent prices or percentages.
- Explain the current price, predicted price, expected move, direction, confidence, risk, and signal breakdown.
- If LSTM, trend, momentum, and volatility conflict, explain that.
- If confidence is low, explain why.
- If risk is high, explain what causes it.
- Write like a professional AI analyst.

Use this format:

1. Executive Summary
2. Forecast Reading
3. Signal Breakdown
4. Bullish Evidence
5. Bearish / Risk Evidence
6. Confidence And Reliability
7. What To Monitor Next
8. Final Interpretation
"""

    return generate_ai_analysis(
        page_type="forecast",
        symbol_or_query=symbol,
        data=forecast_data,
        custom_instruction=instruction
    )