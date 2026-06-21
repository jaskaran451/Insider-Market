import torch
import torch.nn as nn


class AEGRUModel(nn.Module):
    """
    Encoder-decoder GRU model inspired by the AE-GRU paper.

    Architecture:
    Encoder: GRU 200 -> GRU 100 -> GRU 80
    Decoder: GRU 80 -> GRU 100 -> GRU 200
    Output: Dense layer for next-price prediction
    """

    def __init__(
        self,
        input_size=1,
        output_size=1,
        dropout=0.2
    ):
        super().__init__()

        # Encoder
        self.encoder_gru_1 = nn.GRU(
            input_size=input_size,
            hidden_size=200,
            num_layers=1,
            batch_first=True
        )

        self.encoder_gru_2 = nn.GRU(
            input_size=200,
            hidden_size=100,
            num_layers=1,
            batch_first=True
        )

        self.encoder_gru_3 = nn.GRU(
            input_size=100,
            hidden_size=80,
            num_layers=1,
            batch_first=True
        )

        # Decoder
        self.decoder_gru_1 = nn.GRU(
            input_size=80,
            hidden_size=80,
            num_layers=1,
            batch_first=True
        )

        self.decoder_gru_2 = nn.GRU(
            input_size=80,
            hidden_size=100,
            num_layers=1,
            batch_first=True
        )

        self.decoder_gru_3 = nn.GRU(
            input_size=100,
            hidden_size=200,
            num_layers=1,
            batch_first=True
        )

        self.dropout = nn.Dropout(dropout)
        self.output_layer = nn.Linear(200, output_size)

        self.init_weights()

    def init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.GRU):
                for name, param in module.named_parameters():
                    if "bias" in name:
                        nn.init.constant_(param, 0.0)
                    elif "weight_ih" in name:
                        nn.init.kaiming_normal_(param)
                    elif "weight_hh" in name:
                        nn.init.orthogonal_(param)

    def forward(self, x):
        # Encoder
        x, _ = self.encoder_gru_1(x)
        x, _ = self.encoder_gru_2(x)
        x, _ = self.encoder_gru_3(x)

        # Decoder
        x, _ = self.decoder_gru_1(x)
        x, _ = self.decoder_gru_2(x)
        x, _ = self.decoder_gru_3(x)

        # Use last decoded time step for next close prediction
        x = x[:, -1, :]

        x = self.dropout(x)
        prediction = self.output_layer(x)

        return prediction