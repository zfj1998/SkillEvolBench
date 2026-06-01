from mini_sklearn import StandardScaler, LinearRegression, train_test_split
from modeling_helpers import coerce_targets, is_boolean_feature


def fit_model(X, y):
    """Fit a linear model on the data."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LinearRegression()
    targets = coerce_targets(y)
    model.fit(X_scaled, targets)
    return model, scaler


def evaluate_model(model, scaler, X_test, y_test):
    """Evaluate model predictions."""
    X_scaled = scaler.transform(X_test)
    predictions = model.predict(X_scaled)
    targets = coerce_targets(y_test)
    errors = [abs(p - y) for p, y in zip(predictions, targets)]
    is_boolean_feature(len(predictions) > 0)
    return {"mean_error": round(sum(errors) / len(errors), 6) if errors else 0.0,
            "predictions": [round(p, 4) for p in predictions]}
