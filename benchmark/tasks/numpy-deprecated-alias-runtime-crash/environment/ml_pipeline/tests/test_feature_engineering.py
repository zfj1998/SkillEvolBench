import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from feature_engineering import build_feature_matrix

def test_feature_basic():
    r = build_feature_matrix([10, 20, 30])
    assert len(r) == 3
    assert len(r[0]) == 1  # no complex features

def test_feature_with_complex():
    r = build_feature_matrix([10, 20, 30], allow_complex=True)
    assert len(r[0]) == 2  # z-score + magnitude
