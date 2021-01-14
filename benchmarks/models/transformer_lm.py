# Copyright (c) Facebook, Inc. and its affiliates. All rights reserved.

import math

import torch
import torch.nn as nn

from fairscale.optim import GradScaler


# TODO(anj-s): Identify if we need this initialization logic for the below wrapped layers.
class EmbeddingLayer(nn.Embedding):
    """Wrapped nn.Embedding layer to allow for weight initialization."""

    def __init__(self, ntoken, ninp, initrange):
        super().__init__(ntoken, ninp)
        self.ninp_sqrt = math.sqrt(ninp)
        self.weight.data.uniform_(-initrange, initrange)

    def forward(self, src):
        return super().forward(src) * self.ninp_sqrt


class PositionalEncodingLayer(nn.Module):
    """PositionalEncoding layer for a given Transformer model."""

    def __init__(self, d_model, dropout=0.1, max_len=5000):
        super(PositionalEncodingLayer, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer("pe", pe)

    def forward(self, x):
        x = x + self.pe[: x.size(0), :]
        return self.dropout(x)


class TransformerDecoderLayer(nn.TransformerEncoderLayer):
    """TransformerDecoder layer which inherits from nn.TransformerEncoderLayer."""

    def __init__(self, ninp, nhead, nhid, dropout):
        super().__init__(ninp, nhead, nhid, dropout)
        self.src_mask = None

    def _generate_square_subsequent_mask(self, sz):
        mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float("-inf")).masked_fill(mask == 1, float(0.0))
        return mask

    def forward(self, src):
        # TODO(anj-s): Fix the data format so that we have [seq_len, batch_size, embedding dim].
        # Currently real data has seq_len as the second dimension and batch_size as the first dimension.
        # We need to mask the sequence length dimension and not the batch size.
        if self.src_mask is None or self.src_mask.size(0) != len(src):
            device = src.device
            mask = self._generate_square_subsequent_mask(len(src)).to(device)
            self.src_mask = mask

        return super().forward(src, self.src_mask)


class LinearLayer(nn.Linear):
    """Wrapped nn.Linear layer to allow for weight initialization."""

    def __init__(self, ninp, ntoken, initrange):
        super().__init__(ninp, ntoken)
        self.bias.data.zero_()
        self.weight.data.uniform_(-initrange, initrange)


class TransformerLM(nn.Sequential):
    """A GPT-2 based nn.Sequential language model."""

    def __init__(self, ntokens, ninp, nhead, nhid, dropout, initrange, ndecoder):
        layers = [
            EmbeddingLayer(ntokens, ninp, initrange),
            PositionalEncodingLayer(ninp, dropout),
        ]
        for _ in range(ndecoder):
            layers.append(TransformerDecoderLayer(ninp, nhead, nhid, dropout))

        layers.append(LinearLayer(ninp, ntokens, initrange))
        super(TransformerLM, self).__init__(*layers)


class GoldenData:
    def get_benchmark_config():
        return {
            "epochs": 1,
            "vocab_size": 10000,
            "ninp": 2048,  # embedding dimension
            "nhid": 2048,  # the dimension of the feedforward network model in nn.TransformerEncoder
            "nhead": 32,  # the number of heads in the multiheadattention models
            "dropout": 0,
            "initrange": 0.1,
            "criterion": nn.CrossEntropyLoss(),
            "lr": 0.001,  # learning rate
            "scaler": GradScaler(),
            "clip_value": 0.05,
            "batch_size": 8,
            "seq_len": 32,
        }

    def get_golden_real_stats():
        return {
            "avg_wps": 703.778,
            "std_dev_wps": 5.732,
            "peak_mem_usage": [2320996352, 1396742144, 1396742144, 2340010496],
        }

    def get_golden_synthetic_stats():
        pass
