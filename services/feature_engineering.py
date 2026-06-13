import numpy as np
import torch
from torch.utils.data import Dataset


class Normalizer:
    def __init__(self):
        self.mu = None
        self.sd = None

    def fit(self, x):
        self.mu = np.mean(x, axis=0, keepdims=True)
        self.sd = np.std(x, axis=0, keepdims=True)

        if self.sd == 0:
            self.sd = 1

    def transform(self, x):
        return (x - self.mu) / self.sd

    def fit_transform(self, x):
        self.fit(x)
        return self.transform(x)

    def inverse_transform(self, x):
        return (x * self.sd) + self.mu


class TimeSeriesDataset(Dataset):
    def __init__(self, x, y):
        x = np.expand_dims(x, axis=2)

        self.x = x.astype(np.float32)
        self.y = y.astype(np.float32)

    def __len__(self):
        return len(self.x)

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]


def prepare_data_x(x, window_size):
    n_row = x.shape[0] - window_size + 1

    output = np.lib.stride_tricks.as_strided(
        x,
        shape=(n_row, window_size),
        strides=(x.strides[0], x.strides[0])
    )

    return output[:-1], output[-1]


def prepare_data_y(x, window_size):
    return x[window_size:]


def build_train_validation_data(close_prices, window_size=20, train_split_size=0.80):
    close_prices = np.array(close_prices, dtype=np.float32)

    split_index_raw = int(len(close_prices) * train_split_size)

    train_prices_raw = close_prices[:split_index_raw]
    validation_prices_raw = close_prices[split_index_raw - window_size:]

    scaler = Normalizer()

    train_prices_normalized = scaler.fit_transform(train_prices_raw)
    validation_prices_normalized = scaler.transform(validation_prices_raw)

    train_x, _ = prepare_data_x(train_prices_normalized, window_size)
    train_y = prepare_data_y(train_prices_normalized, window_size)

    validation_x, validation_x_unseen = prepare_data_x(validation_prices_normalized, window_size)
    validation_y = prepare_data_y(validation_prices_normalized, window_size)

    dataset_train = TimeSeriesDataset(train_x, train_y)
    dataset_validation = TimeSeriesDataset(validation_x, validation_y)

    return {
        "dataset_train": dataset_train,
        "dataset_validation": dataset_validation,
        "validation_x": validation_x,
        "validation_y": validation_y,
        "validation_x_unseen": validation_x_unseen,
        "scaler": scaler,
        "close_prices": close_prices
    }


def tensor_for_unseen_window(unseen_window):
    return torch.tensor(unseen_window).float().unsqueeze(0).unsqueeze(2)