import logging
from tabulate import tabulate
from model.features import build_features
from model.train import train_and_save
from model.predict import predict_and_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-25s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train")

DB_PATH = "firerag.db"
MODELS_DIR = "models"


def main() -> None:
    logger.info("Phase 2: building features from %s", DB_PATH)
    X_train, y_train, X_test, y_test, _ = build_features(db_path=DB_PATH)
    logger.info(
        "Feature matrix: train=%s  test=%s", X_train.shape, X_test.shape
    )

    logger.info("Training models...")
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=MODELS_DIR)

    rows = [
        [name, f"{m['r2']:.4f}", f"{m['mae']:.4f}", f"{m['rmse']:.4f}"]
        for name, m in results.items()
    ]
    print("\n" + tabulate(rows, headers=["Model", "R²", "MAE", "RMSE"], tablefmt="rounded_outline"))

    logger.info("Generating predictions for today...")
    n = predict_and_save(db_path=DB_PATH, models_dir=MODELS_DIR)
    logger.info("Done — %d predictions written to fires_predictions", n)


if __name__ == "__main__":
    main()
