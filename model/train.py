import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def train_and_save(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    models_dir: str = "models",
) -> dict[str, dict[str, float]]:
    Path(models_dir).mkdir(exist_ok=True, parents=True)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logger.info("Training Ridge regression...")
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train_scaled, y_train)

    logger.info("Training Random Forest (100 trees)...")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    lr_pred = ridge.predict(X_test_scaled)
    rf_pred = rf.predict(X_test)
    ens_pred = np.clip(0.5 * lr_pred + 0.5 * rf_pred, 0.0, 1.0)

    results: dict[str, dict[str, float]] = {}
    for name, pred in [("LR", lr_pred), ("RF", rf_pred), ("Ensemble", ens_pred)]:
        results[name] = {
            "r2": float(r2_score(y_test, pred)),
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
        }

    joblib.dump(ridge, Path(models_dir) / "lr_model.pkl")
    joblib.dump(scaler, Path(models_dir) / "lr_scaler.pkl")
    joblib.dump(rf, Path(models_dir) / "rf_model.pkl")
    logger.info("Models saved to %s/", models_dir)

    return results
