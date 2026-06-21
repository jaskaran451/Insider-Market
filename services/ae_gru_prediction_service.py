import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from models.ae_gru_model import AEGRUModel
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
    actual = np.ravel(np.array(actual))
    predicted = np.ravel(np.array(predicted))

    mae = np.mean(np.abs(actual - predicted))
    mse = np.mean((actual - predicted) ** 2)
    rmse = math.sqrt(mse)

    denominator = np.where(actual == 0, 1e-8, actual)
    mape = np.mean(np.abs((actual - predicted) / denominator)) * 100

    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    actual_direction = np.sign(np.diff(actual))
    predicted_direction = np.sign(np.diff(predicted))

    if len(actual_direction) == 0:
        direction_accuracy = 0
    else:
        direction_accuracy = np.mean(actual_direction == predicted_direction) * 100

    return {
        "mae": round(float(mae), 2),
        "mse": round(float(mse), 2),
        "rmse": round(float(rmse), 2),
        "mape": round(float(mape), 2),
        "r_squared": round(float(r_squared), 4),
        "direction_accuracy": round(float(direction_accuracy), 1)
    }


def predict_with_ae_gru(price_rows, status_callback=None):
    """
    Train AE-GRU on historical adjusted-close prices and predict next close.

    Paper-inspired setup:
    - 120-day lookback window
    - Encoder GRU layers: 200 -> 100 -> 80
    - Decoder GRU layers: 80 -> 100 -> 200
    - Adam optimizer lr=0.001, betas=(0.9, 0.999)
    - MSE loss

    status_callback is optional.
    If provided, it sends live model progress messages to the frontend ledger.
    """

    def status(message, stage="running", extra=None):
        if status_callback:
            status_callback(message, stage, extra or {})

    if len(price_rows) < 180:
        raise ValueError(
            "Not enough price history for AE-GRU prediction. "
            "Need at least 180 daily candles."
        )

    # =========================
    # Model settings
    # =========================
    window_size = 120
    train_split_size = 0.75
    batch_size = 64

    # Start low for local testing. Increase later to 50 or 100.
    num_epochs = 20

    learning_rate = 0.001
    device, device_type, device_name = get_torch_device()

    status("Preparing adjusted-close price series...", "preparing")

    close_prices = [row["adjusted_close"] for row in price_rows]

    status(
        f"Building {window_size}-day lookback windows from {len(close_prices)} price points...",
        "preparing",
        {
            "window_size": window_size,
            "price_points": len(close_prices)
        }
    )
    status(
        f"Compute device selected: {device_type} ({device_name}).",
        "system",
        {
            "device": str(device),
            "device_type": device_type,
            "device_name": device_name
        }
    )

    data = build_train_validation_data(
        close_prices=close_prices,
        window_size=window_size,
        train_split_size=train_split_size
    )

    status(
        "Training and validation datasets prepared.",
        "success",
        {
            "window_size": window_size,
            "train_samples": len(data["dataset_train"]),
            "validation_samples": len(data["dataset_validation"])
        }
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

    model = AEGRUModel(
        input_size=1,
        output_size=1,
        dropout=0.2
    ).to(device)

    status(
        "AE-GRU architecture initialized: encoder 200→100→80, decoder 80→100→200.",
        "model_ready",
        {
            "architecture": "AE-GRU",
            "encoder": [200, 100, 80],
            "decoder": [80, 100, 200],
            "epochs": num_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate
        }
    )

    criterion = nn.MSELoss()

    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        betas=(0.9, 0.999),
        eps=1e-7
    )

    train_losses = []
    validation_losses = []

    status(
        f"Starting AE-GRU training for {num_epochs} epochs...",
        "training_start",
        {
            "total_epochs": num_epochs
        }
    )

    # =========================
    # Training loop
    # =========================
    for epoch in range(num_epochs):
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

        train_losses.append(round(train_loss, 6))
        validation_losses.append(round(validation_loss, 6))

        status(
            f"Epoch {epoch + 1}/{num_epochs} complete | "
            f"train_loss={train_loss:.6f} | "
            f"val_loss={validation_loss:.6f}",
            "training",
            {
                "epoch": epoch + 1,
                "total_epochs": num_epochs,
                "train_loss": round(train_loss, 6),
                "validation_loss": round(validation_loss, 6)
            }
        )

    model.eval()

    # =========================
    # Validation prediction pass
    # =========================
    status("Running validation prediction pass...", "validation")

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

    metrics = calculate_metrics(
        validation_actual_real,
        validation_predictions_real
    )

    status(
        "Validation metrics calculated.",
        "validation_complete",
        {
            "mae": metrics["mae"],
            "mse": metrics["mse"],
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "r_squared": metrics["r_squared"],
            "direction_accuracy": metrics["direction_accuracy"]
        }
    )

    # =========================
    # Next-day forecast
    # =========================
    status("Generating next-day AE-GRU forecast...", "predicting")

    unseen_tensor = tensor_for_unseen_window(data["validation_x_unseen"]).to(device)

    with torch.no_grad():
        next_prediction_normalized = model(unseen_tensor).cpu().numpy()

    next_prediction_real = data["scaler"].inverse_transform(next_prediction_normalized)

    latest_price = float(close_prices[-1])
    predicted_price = float(next_prediction_real[0])

    expected_move = ((predicted_price - latest_price) / latest_price) * 100

    # Safety guard so one bad training run does not create unrealistic output.
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

    confidence = int(
        84
        - metrics["mape"] * 3
        - volatility * 500
    )

    confidence = max(min(confidence, 92), 40)

    validation_predictions_real = np.ravel(validation_predictions_real)
    validation_actual_real = np.ravel(validation_actual_real)

    status(
        f"AE-GRU predicted ${predicted_price:.2f} with expected move {expected_move:.2f}%.",
        "prediction_complete",
        {
            "latest_price": round(latest_price, 2),
            "predicted_price": round(predicted_price, 2),
            "expected_move": round(expected_move, 2),
            "direction": direction,
            "confidence": confidence,
            "risk": risk,
            "volatility": round(volatility, 4)
        }
    )

    return {
        "current_price": round(latest_price, 2),
        "predicted_price": round(predicted_price, 2),
        "expected_move": round(expected_move, 2),
        "direction": direction,
        "confidence": confidence,
        "risk": risk,
        "volatility": round(volatility, 4),

        "mae": metrics["mae"],
        "mse": metrics["mse"],
        "rmse": metrics["rmse"],
        "mape": metrics["mape"],
        "r_squared": metrics["r_squared"],
        "direction_accuracy": metrics["direction_accuracy"],

        "train_losses": train_losses,
        "validation_losses": validation_losses,

        "validation_actual": [
            round(float(value), 2)
            for value in validation_actual_real
        ],
        "validation_predicted": [
            round(float(value), 2)
            for value in validation_predictions_real
        ],
        "compute_device": {
            "device": str(device),
            "type": device_type,
            "name": device_name
        }
    }

def get_torch_device():
    """
    Automatically chooses the best available PyTorch compute device.

    Priority:
    1. NVIDIA GPU through CUDA
    2. Apple Silicon GPU through MPS
    3. CPU fallback
    """

    if torch.cuda.is_available():
        return torch.device("cuda"), "GPU", torch.cuda.get_device_name(0)

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps"), "Apple GPU", "Apple Silicon MPS"

    return torch.device("cpu"), "CPU", "CPU"