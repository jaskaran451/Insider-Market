import numpy as np


def calculate_returns(close_prices):
    close_prices = np.array(close_prices, dtype=float)
    return np.diff(close_prices) / close_prices[:-1]


def trend_forecast(close_prices):
    close_prices = np.array(close_prices, dtype=float)

    ma_20 = np.mean(close_prices[-20:])
    ma_60 = np.mean(close_prices[-60:])

    trend_return = (ma_20 - ma_60) / ma_60
    return float(np.clip(trend_return, -0.06, 0.06))


def momentum_forecast(close_prices):
    close_prices = np.array(close_prices, dtype=float)

    return_5 = (close_prices[-1] - close_prices[-5]) / close_prices[-5]
    return_20 = (close_prices[-1] - close_prices[-20]) / close_prices[-20]

    momentum_return = (return_5 * 0.6) + (return_20 * 0.4)
    return float(np.clip(momentum_return, -0.06, 0.06))


def volatility_adjustment(close_prices):
    returns = calculate_returns(close_prices[-60:])
    volatility = float(np.std(returns))

    if volatility > 0.04:
        adjustment = -0.015
    elif volatility > 0.025:
        adjustment = -0.0075
    else:
        adjustment = 0.0025

    return adjustment, volatility


def build_consensus_forecast(price_rows, model_forecast):
    close_prices = [row["adjusted_close"] for row in price_rows]
    latest_price = close_prices[-1]

    model_return = (
        (model_forecast["predicted_price"] - latest_price) / latest_price
    )

    trend_return = trend_forecast(close_prices)
    momentum_return = momentum_forecast(close_prices)
    volatility_return, volatility = volatility_adjustment(close_prices)

    consensus_return = (
        model_return * 0.35 +
        trend_return * 0.25 +
        momentum_return * 0.25 +
        volatility_return * 0.15
    )

    max_dynamic_move = max(0.02, min(0.15, volatility * 3))
    consensus_return = float(np.clip(consensus_return, -max_dynamic_move, max_dynamic_move))

    predicted_price = latest_price * (1 + consensus_return)
    expected_move = consensus_return * 100

    if expected_move > 0.65:
        direction = "Bullish"
    elif expected_move < -0.65:
        direction = "Bearish"
    else:
        direction = "Neutral"

    confidence = int(
        model_forecast.get("confidence", 60) * 0.45 +
        max(40, 90 - volatility * 1000) * 0.35 +
        65 * 0.20
    )

    confidence = max(min(confidence, 90), 40)

    if volatility > 0.035:
        risk = "High"
    elif volatility > 0.018:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        **model_forecast,
        "model": "InsiderAI Consensus Forecast",
        "current_price": round(latest_price, 2),
        "predicted_price": round(predicted_price, 2),
        "expected_move": round(expected_move, 2),
        "direction": direction,
        "confidence": confidence,
        "risk": risk,
        "volatility": round(volatility, 4),
        "signal_breakdown": {
            "ae_gru": round(model_return * 100, 2),
            "trend": round(trend_return * 100, 2),
            "momentum": round(momentum_return * 100, 2),
            "volatility_adjustment": round(volatility_return * 100, 2),
            "consensus": round(expected_move, 2)
        }
    }