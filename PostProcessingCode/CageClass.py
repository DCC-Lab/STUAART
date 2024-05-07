import numpy as np
import matplotlib.pyplot as plt
import exceptions


class Cage(np.ndarray):
    def __new__(cls, data_list: list, time: np.ndarray):
        array = np.array(data_list)
        cage_array = np.sum(array, axis=0)
        obj = np.asarray(cage_array).view(cls)
        return obj

    def __init__(self, data_list: list, time: np.ndarray):
        super().__init__()
        self.time = time