import numpy as np

class Data(np.ndarray):

    def __init__(self, data):
        print('init')
        super().__init__()
        self.outliers_threshold = 0
    
    def __new__(cls, a):
        obj = np.asarray(a).view(cls)
        return obj

    def center_data_on_zero(self):
        baseline = np.mean(self[1])
        centered_data = self - baseline
        self[:] = centered_data
        return self

    def remove_outliers(self) -> np.array:
        self[:] = np.where(np.abs(self) > self.outliers_threshold, 0, self)
        return self

    def set_outliers_threshold(self, threshold: float):
        self.outliers_threshold = threshold
    
    def get_outliers_threshold(self):
        return self.get_outliers_threshold