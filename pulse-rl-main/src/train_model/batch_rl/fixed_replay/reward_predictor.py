import os
import torch
import torch.nn as nn
import math
import numpy as np
import tensorflow as tf
import pandas as pd


class RunningMeanStd(object):
    def __init__(self, epsilon=1e-4, shape=()):
        """
        calulates the running mean and std of a data stream
        https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Parallel_algorithm

        :param epsilon: (float) helps with arithmetic issues
        :param shape: (tuple) the shape of the data stream's output
        """
        self.mean = np.zeros(shape, "float64")
        self.var = np.ones(shape, "float64")
        self.count = epsilon

    def update(self, arr):
        batch_mean = np.mean(arr, axis=0)
        batch_var = np.var(arr, axis=0)
        batch_count = arr.shape[0]
        self.update_from_moments(batch_mean, batch_var, batch_count)

    def update_from_moments(self, batch_mean, batch_var, batch_count):
        delta = batch_mean - self.mean
        tot_count = self.count + batch_count

        new_mean = self.mean + delta * batch_count / tot_count
        m_a = self.var * self.count
        m_b = batch_var * batch_count
        m_2 = (
            m_a
            + m_b
            + np.square(delta) * self.count * batch_count / (self.count + batch_count)
        )
        new_var = m_2 / (self.count + batch_count)

        new_count = batch_count + self.count

        self.mean = new_mean
        self.var = new_var
        self.count = new_count

    def state_dict(self):
        return dict(mean=self.mean, var=self.var, count=self.count)

    def load_dict(self, d):
        self.mean = d["mean"]
        self.var = d["var"]
        self.count = d["count"]


class NN(nn.Module):
    def __init__(self, input_size):
        super(NN, self).__init__()
        self.fc1 = nn.Linear(input_size, 512, bias=True)
        self.fc2 = nn.Linear(512, 256, bias=True)
        self.fc3 = nn.Linear(256, 128, bias=True)
        self.fc4 = nn.Linear(128, 1, bias=True)
        self.tanh = torch.nn.Tanh()
        self.softp = torch.nn.Softplus()

    def forward(self, x):
        x = self.fc1(x)
        x = self.tanh(x)
        x = self.fc2(x)
        x = self.tanh(x)
        x = self.fc3(x)
        x = self.tanh(x)
        x = self.fc4(x)
        return x


class RewardPredictor:
    def __init__(self, input_size, checkpoint_dir):

        self.model = NN(input_size + 1)

        self.running_stats = RunningMeanStd()

        device = "cuda" if torch.cuda.is_available() else "cpu"

        checkpoint = os.path.join(checkpoint_dir, "checkpoint")
        model_state, optimizer_state, scheduler_state, running_stats_state = torch.load(
            checkpoint, map_location=torch.device(device)
        )
        self.model.load_state_dict(model_state)
        self.running_stats.load_dict(running_stats_state)

    def predict(self, x):
        scores = self.model(x)
        scores_raw = (torch.exp(scores) - 1 + 0.003) * math.sqrt(
            (self.running_stats.var)
        )  # just the inverse transofrmation for the predicted rewards
        return scores_raw
