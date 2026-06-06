from src.main import run_alpha_feature, run_beta_feature, run_combined


def test_alpha_feature_returns_expected_shape():
    result = run_alpha_feature()
    assert result == "alpha:legacy:sample"


def test_beta_feature_returns_expected_shape():
    result = run_beta_feature()
    assert result == "beta:SAMPLE"


def test_combined_feature_uses_both_paths():
    result = run_combined()
    assert result == "alpha:legacy:sample | beta:SAMPLE"
