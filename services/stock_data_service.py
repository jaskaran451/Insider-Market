import numpy as np
import yfinance as yf
from services.consensus_forecast_service import build_consensus_forecast

def fetch_ohlc_history(symbol, period="2y"):
    """
    Fetch historical OHLCV data using yfinance.
    Returns oldest-to-newest rows.
    """

    ticker = yf.Ticker(symbol.upper())

    df = ticker.history(
        period=period,
        interval="1d",
        auto_adjust=True
    )

    if df.empty:
        raise ValueError("No historical price data found for this symbol")

    df = df.reset_index()

    rows = []

    for _, row in df.iterrows():
        rows.append({
            "date": row["Date"].strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "adjusted_close": float(row["Close"]),
            "volume": int(row["Volume"])
        })

    return rows


def calculate_basic_forecast(price_rows):
    """
    Temporary forecast engine.
    Later we replace this with the PyTorch LSTM model.
    """

    if len(price_rows) < 30:
        raise ValueError("Not enough price history to generate forecast")

    latest_price = price_rows[-1]["adjusted_close"]

    last_5 = [row["adjusted_close"] for row in price_rows[-5:]]
    last_20 = [row["adjusted_close"] for row in price_rows[-20:]]

    avg_5 = sum(last_5) / len(last_5)
    avg_20 = sum(last_20) / len(last_20)

    trend_strength = (avg_5 - avg_20) / avg_20

    daily_returns = []

    for index in range(1, len(last_20)):
        previous_price = last_20[index - 1]
        current_price = last_20[index]

        daily_return = (current_price - previous_price) / previous_price
        daily_returns.append(daily_return)

    avg_return = sum(daily_returns) / len(daily_returns)

    variance = sum((value - avg_return) ** 2 for value in daily_returns) / len(daily_returns)
    volatility = variance ** 0.5

    forecast_move = (trend_strength * 0.55) + (avg_return * 0.45)
    forecast_move = max(min(forecast_move, 0.06), -0.06)

    predicted_price = latest_price * (1 + forecast_move)
    expected_move = ((predicted_price - latest_price) / latest_price) * 100

    if expected_move > 0.65:
        direction = "Bullish"
    elif expected_move < -0.65:
        direction = "Bearish"
    else:
        direction = "Neutral"

    if volatility > 0.035:
        risk = "High"
    elif volatility > 0.018:
        risk = "Medium"
    else:
        risk = "Low"

    confidence = int(78 - volatility * 700)
    confidence = max(min(confidence, 88), 45)

    return {
        "current_price": round(latest_price, 2),
        "predicted_price": round(predicted_price, 2),
        "expected_move": round(expected_move, 2),
        "direction": direction,
        "confidence": confidence,
        "risk": risk,
        "volatility": round(volatility, 4),
        "trend_strength": round(trend_strength, 4)
    }

from services.lstm_prediction_service import predict_with_lstm
def build_prediction_response(symbol):
    price_rows = fetch_ohlc_history(symbol, period="10y")

    try:
        lstm_forecast = predict_with_lstm(price_rows)
        forecast = build_consensus_forecast(price_rows, lstm_forecast)

        model_name = "InsiderAI Consensus Forecast"
        message = "LSTM, trend, momentum, and volatility signals combined."

    except Exception as error:
        forecast = calculate_basic_forecast(price_rows)
        model_name = "Fallback Trend Forecast"
        message = f"LSTM unavailable, using fallback forecast. Reason: {str(error)}"

    chart_rows = price_rows[-252:]

    labels = [row["date"] for row in chart_rows]
    actual_prices = [round(row["adjusted_close"], 2) for row in chart_rows]

    predicted_prices = [None for _ in chart_rows]
    upper_band = [None for _ in chart_rows]
    lower_band = [None for _ in chart_rows]

    validation_predicted = forecast.get("validation_predicted")

    if validation_predicted:
        values_to_plot = validation_predicted[-len(chart_rows):]

        start_index = len(chart_rows) - len(values_to_plot)

        for index, value in enumerate(values_to_plot):
            chart_index = start_index + index

            if 0 <= chart_index < len(predicted_prices):
                predicted_prices[chart_index] = round(float(value), 2)

                band_width = forecast["volatility"] * 2.2
                upper_band[chart_index] = round(float(value) * (1 + band_width), 2)
                lower_band[chart_index] = round(float(value) * (1 - band_width), 2)

    labels.append("Next Day")
    actual_prices.append(None)

    predicted_prices.append(forecast["predicted_price"])

    final_band_width = forecast["volatility"] * 2.2
    upper_band.append(round(forecast["predicted_price"] * (1 + final_band_width), 2))
    lower_band.append(round(forecast["predicted_price"] * (1 - final_band_width), 2))

    return {
        "symbol": symbol.upper(),
        "model": model_name,
        "message": message,

        "current_price": forecast["current_price"],
        "predicted_price": forecast["predicted_price"],
        "expected_move": forecast["expected_move"],
        "direction": forecast["direction"],
        "confidence": forecast["confidence"],
        "risk": forecast["risk"],
        "volatility": forecast["volatility"],

        "mae": forecast.get("mae"),
        "rmse": forecast.get("rmse"),
        "direction_accuracy": forecast.get("direction_accuracy"),
        "train_losses": forecast.get("train_losses"),
        "validation_losses": forecast.get("validation_losses"),

        "labels": labels,
        "actual": actual_prices,
        "predicted": predicted_prices,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "signal_breakdown": forecast.get("signal_breakdown"),
        "history_count": len(chart_rows)
    }