import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from models.lstm_model import LSTMModel
from services.feature_engineering import (
    build_train_validation_data,
    tensor_for_unseen_window
)


def train_one_epoch(model, dataloader, criterion, optimizer, device, is_training=False):
    epoch_loss = 0

    if is_training:
        model.train()
    else:
        model.eval()

    for x, y in dataloader:
        x = x.to(device)
        y = y.to(device)

        if is_training:
            optimizer.zero_grad()

        prediction = model(x)
        y = y.view(-1, 1)
        loss = criterion(prediction.contiguous(), y.contiguous())

        if is_training:
            loss.backward()
            optimizer.step()

        epoch_loss += loss.detach().item()

    return epoch_loss / max(len(dataloader), 1)


def calculate_metrics(actual, predicted):
    actual = np.array(actual)
    predicted = np.array(predicted)

    mae = np.mean(np.abs(actual - predicted))
    rmse = math.sqrt(np.mean((actual - predicted) ** 2))

    actual_direction = np.sign(np.diff(actual))
    predicted_direction = np.sign(np.diff(predicted))

    if len(actual_direction) == 0:
        direction_accuracy = 0
    else:
        direction_accuracy = np.mean(actual_direction == predicted_direction) * 100

    return {
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "direction_accuracy": round(float(direction_accuracy), 1)
    }


def predict_with_lstm(price_rows):
    """
    Train a lightweight LSTM on recent historical prices and predict next close.
    This is version 1. Later we can save/cache models instead of training on every request.
    """

    if len(price_rows) < 120:
        raise ValueError("Not enough price history for LSTM prediction. Need at least 120 daily candles.")

    close_prices = [row["adjusted_close"] for row in price_rows]

    window_size = 60
    train_split_size = 0.75
    batch_size = 64
    num_epochs = 20
    learning_rate = 0.003
    device = "cpu"

    data = build_train_validation_data(
        close_prices=close_prices,
        window_size=window_size,
        train_split_size=train_split_size
    )

    train_loader = DataLoader(
        data["dataset_train"],
        batch_size=batch_size,
        shuffle=True
    )

    validation_loader = DataLoader(
        data["dataset_validation"],
        batch_size=batch_size,
        shuffle=False
    )

    model = LSTMModel(
        input_size=1,
        hidden_layer_size=32,
        num_layers=2,
        output_size=1,
        dropout=0.2
    ).to(device)

    criterion = nn.MSELoss()
    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        betas=(0.9, 0.98),
        eps=1e-9
    )

    scheduler = optim.lr_scheduler.StepLR(
        optimizer,
        step_size=15,
        gamma=0.5
    )

    train_losses = []
    validation_losses = []

    for _ in range(num_epochs):
        train_loss = train_one_epoch(
            model=model,
            dataloader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=device,
            is_training=True
        )

        validation_loss = train_one_epoch(
            model=model,
            dataloader=validation_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=device,
            is_training=False
        )

        scheduler.step()

        train_losses.append(round(train_loss, 6))
        validation_losses.append(round(validation_loss, 6))

    model.eval()

    validation_predictions = []

    with torch.no_grad():
        for x, _ in validation_loader:
            x = x.to(device)
            output = model(x)
            validation_predictions.extend(output.cpu().numpy())

    validation_predictions = np.array(validation_predictions)
    validation_actual = np.array(data["validation_y"])

    validation_predictions_real = data["scaler"].inverse_transform(validation_predictions)
    validation_actual_real = data["scaler"].inverse_transform(validation_actual)

    unseen_tensor = tensor_for_unseen_window(data["validation_x_unseen"]).to(device)

    with torch.no_grad():
        next_prediction_normalized = model(unseen_tensor).cpu().numpy()

    next_prediction_real = data["scaler"].inverse_transform(next_prediction_normalized)

    latest_price = float(close_prices[-1])
    predicted_price = float(next_prediction_real[0])

    expected_move = ((predicted_price - latest_price) / latest_price) * 100
    max_daily_move = 5.0

    if expected_move > max_daily_move:
        expected_move = max_daily_move
        predicted_price = latest_price * (1 + expected_move / 100)

    elif expected_move < -max_daily_move:
        expected_move = -max_daily_move
        predicted_price = latest_price * (1 + expected_move / 100)

    if expected_move > 0.65:
        direction = "Bullish"
    elif expected_move < -0.65:
        direction = "Bearish"
    else:
        direction = "Neutral"

    returns = np.diff(close_prices[-20:]) / np.array(close_prices[-20:-1])
    volatility = float(np.std(returns))

    if volatility > 0.035:
        risk = "High"
    elif volatility > 0.018:
        risk = "Medium"
    else:
        risk = "Low"

    metrics = calculate_metrics(
        validation_actual_real,
        validation_predictions_real
    )

    confidence = int(82 - metrics["mae"] / latest_price * 1000 - volatility * 500)
    confidence = max(min(confidence, 90), 40)

    validation_predictions_real = np.ravel(validation_predictions_real)
    validation_actual_real = np.ravel(validation_actual_real)

    return {
        "current_price": round(latest_price, 2),
        "predicted_price": round(predicted_price, 2),
        "expected_move": round(expected_move, 2),
        "direction": direction,
        "confidence": confidence,
        "risk": risk,
        "volatility": round(volatility, 4),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "direction_accuracy": metrics["direction_accuracy"],
        "train_losses": train_losses,
        "validation_losses": validation_losses,

        "validation_actual": [round(float(value), 2) for value in validation_actual_real],
        "validation_predicted": [round(float(value), 2) for value in validation_predictions_real]
    }