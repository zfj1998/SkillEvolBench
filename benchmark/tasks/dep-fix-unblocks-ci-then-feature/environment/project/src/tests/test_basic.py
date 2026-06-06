from analytics import compute_statistics, normalize_series, find_outliers

def test_statistics():
    r = compute_statistics([10, 20, 30, 40, 50])
    assert r["count"] == 5

def test_normalize():
    r = normalize_series([10, 20, 30])
    assert r[0] == 0.0 and r[-1] == 1.0

def test_no_outliers():
    assert find_outliers([10, 11, 12, 13, 14]) == []
