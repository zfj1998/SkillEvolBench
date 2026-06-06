import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data_pipeline import load_data, run_basic_checks
from custom_ml_utils import advanced_calculate
from main import run_basic_pipeline

def test_basic_load_data():
    data = load_data([{"a": "1.5", "b": "hello"}, {"a": "2.0", "b": "world"}])
    assert data[0]["a"] == 1.5
    assert data[0]["b"] == "hello"

def test_basic_calculate_scalar():
    r = advanced_calculate(1.5)
    assert r == 4.0  # 1.5 * 2.0 + 1.0

def test_basic_pipeline_smoke():
    r = run_basic_pipeline()
    assert r["checks"]["status"] == "ok"
    assert r["checks"]["count"] == 5
    assert r["scalar_demo"] == 4.0
    assert r["feature_shape"] == (3, 1)
