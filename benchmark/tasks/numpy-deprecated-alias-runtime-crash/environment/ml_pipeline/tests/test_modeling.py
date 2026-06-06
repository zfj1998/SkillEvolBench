import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modeling import fit_model, evaluate_model

def test_fit_and_predict():
    X = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    model, scaler = fit_model(X, y)
    result = evaluate_model(model, scaler, [6, 7], [12, 14])
    assert result["mean_error"] < 1.0
    assert len(result["predictions"]) == 2
