import numpy
from custom_ml_utils import normalize, detect_outliers

def normalize_series(values):
    return [round(v, 4) for v in normalize(values)]

def find_outliers(values, threshold=2.0):
    return detect_outliers(values, threshold)
