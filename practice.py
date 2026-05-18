import torch
import numpy as np
import torch.nn as nn
import matplotlib.pyplot as pyplot
import torch.optim as optim
import torch.nn.functional as functional
import torch.utils.data as dataloader
import torchvision.datasets as datasets
import torchvision.transforms as transforms


def plot_prediction(train_data_x, train_data_y,test_data_x,test_data_y,prediction=None):
    pyplot.figure(figsize=(5,5))
    pyplot.scatter(train_data_x,train_data_y,c='b', s=4,label="Train Data")

    pyplot.scatter(test_data_x,test_data_y,c='g', s=4,label="Test Data")
    # if prediction is not None:
    #     pyplot.scatter(test_data,prediction,c='r', s=4,label="Prediction")
    #
    pyplot.legend(prop={"size": 10})
    pyplot.show()




# neural network practice
def neuralnetwork():
    weight,bias = 0.7,0.3
    start = 0
    end = 1
    step = 0.02
    # data
    x = torch.arange(start, end, step).unsqueeze(dim=1)
    y = (weight * x) + bias
    print(len(y))

    # splitting the data for training
    x_train=int(0.8*len(x))
    y_train=int(0.8*len(y))
    x_train_data,y_train_data=x[0:x_train],y[0:y_train]
    x_test_data,y_test_data=x[x_train:],y[y_train:]
    print(x_test_data)
    print(y_test_data)
    plot_prediction(x_train_data,y_train_data,x_test_data,y_test_data)


class LinearRegression(nn.Module):
    def __init__(self):
        super().__init__()
        self.weight=nn.Parameter(torch.randn(1))
        self.bias=nn.Parameter(torch.randn(1))

def forward(self, x:torch.Tensor) -> torch.Tensor:
    return null

def main(name):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    neuralnetwork()
if __name__ == '__main__':
    main('PyCharm')
