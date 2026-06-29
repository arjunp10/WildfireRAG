import numpy as np
import pytest
from pathlib import Path
from model.train import train_and_save


@pytest.fixture
def synthetic_data():
    rng = np.random.default_rng(42)
    X_train = rng.random((200, 10))
    y_train = rng.random(200)
    X_test = rng.random((50, 10))
    y_test = rng.random(50)
    return X_train, y_train, X_test, y_test


def test_train_returns_metrics_for_all_models(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    assert set(results.keys()) == {"LR", "RF", "Ensemble"}
    for model_name in results:
        assert set(results[model_name].keys()) == {"r2", "mae", "rmse"}


def test_train_saves_model_files(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    assert (tmp_path / "lr_model.pkl").exists()
    assert (tmp_path / "lr_scaler.pkl").exists()
    assert (tmp_path / "rf_model.pkl").exists()


def test_metrics_are_floats(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    for model_name, metrics in results.items():
        for metric_name, value in metrics.items():
            assert isinstance(value, float), f"{model_name}.{metric_name} is not float"


def test_rmse_is_non_negative(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    for model_name in results:
        assert results[model_name]["rmse"] >= 0.0
