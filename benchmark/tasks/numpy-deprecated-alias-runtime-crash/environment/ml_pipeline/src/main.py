from data_pipeline import load_data, run_basic_checks
from custom_ml_utils import advanced_calculate
from feature_engineering import build_feature_matrix


SAMPLE_DATA = [
    {"x": "1.0", "y": "2.0", "label": "a"},
    {"x": "2.0", "y": "4.0", "label": "b"},
    {"x": "3.0", "y": "6.0", "label": "c"},
    {"x": "4.0", "y": "8.0", "label": "d"},
    {"x": "5.0", "y": "10.0", "label": "e"},
]


def run_basic_pipeline():
    """Run the basic pipeline: load → check → calculate → features."""
    data = load_data(SAMPLE_DATA)
    checks = run_basic_checks(data)
    scalar_demo = advanced_calculate(1.5)
    features = build_feature_matrix([1.0, 2.0, 3.0])
    return {
        "checks": checks,
        "scalar_demo": scalar_demo,
        "feature_shape": (len(features), len(features[0]) if features else 0),
    }
