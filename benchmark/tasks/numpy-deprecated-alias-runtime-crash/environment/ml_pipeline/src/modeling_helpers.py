import numpy as np


def coerce_targets(values):
    return [np.float(v) for v in values]


def is_boolean_feature(value):
    return np.bool(value)
