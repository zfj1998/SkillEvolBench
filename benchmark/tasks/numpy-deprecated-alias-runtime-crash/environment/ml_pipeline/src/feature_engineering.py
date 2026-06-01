import numpy as np


def build_feature_matrix(values, allow_complex=False):
    """Build a feature matrix from raw values."""
    features = []
    m = np.mean(values)
    s = np.std(values) or 1.0
    for v in values:
        row = [round((v - m) / s, 6)]
        if allow_complex:
            z = np.complex(v, m)
            magnitude = round((z.real ** 2 + z.imag ** 2) ** 0.5, 6)
            row.append(magnitude)
        features.append(row)
    return features
