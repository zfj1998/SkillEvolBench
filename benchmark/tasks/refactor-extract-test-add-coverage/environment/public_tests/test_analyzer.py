from analyzer import analyze_data


def test_analyze_data_basic_mean():
    result = analyze_data([1, 2, 3, 4, 5])
    assert result["mean"] == 3.0


def test_analyze_data_basic_median():
    result = analyze_data([1, 2, 3, 4, 5])
    assert result["median"] == 3.0


def test_analyze_data_even_count():
    result = analyze_data([1, 2, 3, 4])
    assert result["median"] == 2.5


def test_analyze_data_outliers():
    result = analyze_data([1, 2, 3, 4, 100])
    assert result["count"] == 5


def test_analyze_data_numeric_only():
    result = analyze_data([10, 20, 30])
    assert result["stddev"] >= 0
