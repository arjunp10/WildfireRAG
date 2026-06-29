# WildfireRAG Phase 2 Design — Fire Risk Forecasting Model

**Date:** 2026-06-29
**Status:** Approved

## Overview

Phase 2 trains a fire risk scoring model on 2.3M historical US wildfire records (1992–2020) combined with current NOAA weather data. The output is a 0–1 fire risk score for every 0.5° grid cell across CONUS, written to the `fires_predictions` table for use in Phase 3 (dashboard) and Phase 4 (RAG).

The model is a **blended ensemble** of logistic regression (interpretable, Phase 4 RAG-friendly) and random forest (captures non-linear weather × history interactions), weighted equally.

## Project Structure

```
WildfireRAG/
├── model/
│   ├── __init__.py
│   ├── features.py      # grid aggregation + feature engineering from SQLite
│   ├── train.py         # train LR + RF, evaluate, save models
│   └── predict.py       # load models, score all grid cells, write fires_predictions
├── models/              # saved model files (gitignored)
│   ├── lr_model.pkl
│   ├── lr_scaler.pkl
│   └── rf_model.pkl
├── train.py             # CLI entrypoint: python3 train.py
└── tests/
    ├── test_features.py
    └── test_predict.py
```

## Feature Engineering

Each training row = one **0.5° grid cell × calendar month**.

### Grid binning
Latitude and longitude are rounded to the nearest 0.5° to assign each fire to a cell:
```
cell_lat = round(latitude * 2) / 2
cell_lon = round(longitude * 2) / 2
```

### Historical features (from `fires_historical`, train set 1992–2018 only)
| Feature | Description |
|---|---|
| `hist_fire_count` | Total fires in this cell in this month across all years |
| `hist_avg_size_acres` | Mean fire size (frp field, acres) in this cell+month |
| `hist_fire_density` | Fires per year: `hist_fire_count / 27` |

### Weather features (from `weather` table, joined by nearest 0.5° cell using same binning: `round(lat * 2) / 2`)
| Feature | Description |
|---|---|
| `temperature` | °F |
| `humidity` | % relative humidity |
| `wind_speed` | mph |
| `wind_dir` | degrees (0–360) |

### Engineered features
| Feature | Formula |
|---|---|
| `month_sin` | `sin(2π × month / 12)` |
| `month_cos` | `cos(2π × month / 12)` |
| `heat_drought_index` | `temperature × (100 - humidity) / 100` |

### Target variable
`fire_risk` = `hist_fire_density` normalized to 0–1 via min-max scaling across all grid cells.

## Train/Test Split

- **Train:** `acq_date < 2019-01-01` (1992–2018, 27 years)
- **Test:** `acq_date >= 2019-01-01` (2019–2020, 2 years)

Split is temporal (not random) to prevent data leakage.

## Models

### Ridge Regression
- `sklearn.linear_model.Ridge(alpha=1.0)` — linear regression with L2 regularization, outputs continuous 0–1 scores, fully interpretable coefficients for Phase 4 RAG explanations
- Features scaled with `StandardScaler` (fitted on train set only)
- Scaler saved to `models/lr_scaler.pkl`
- Model saved to `models/lr_model.pkl`

### Random Forest
- `sklearn.ensemble.RandomForestRegressor(n_estimators=100, random_state=42)`
- No feature scaling needed
- Model saved to `models/rf_model.pkl`

### Ensemble
```python
fire_probability = 0.5 * lr_score + 0.5 * rf_score
```

## Evaluation

Regression metrics printed to console after training:

```
Model          R²      MAE     RMSE
LR             x.xx    x.xx    x.xx
RF             x.xx    x.xx    x.xx
Ensemble       x.xx    x.xx    x.xx
```

Metrics computed on test set (2019–2020 grid cell × month rows).

## Prediction Output

`model/predict.py` scores every 0.5° CONUS cell (~6,400 cells) for today's date using current NOAA weather from `weather` table:

```sql
INSERT INTO fires_predictions
    (latitude, longitude, fire_probability, prediction_date, model_version, ingested_at)
```

`model_version = "ensemble-v1"`. Running `train.py` again with a new model increments the version.

## Dependencies

```
pandas
scikit-learn
joblib
numpy
```

## Out of Scope for Phase 2

- Hyperparameter tuning (grid search / Bayesian optimization)
- Deep learning models
- Real-time retraining
- Vegetation type features (NDVI, land cover)
- Days-since-last-fire feature (requires spatial join across years)
- Streamlit dashboard (Phase 3)
- RAG layer (Phase 4)
