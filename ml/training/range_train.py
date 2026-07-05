import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score

from ml.utils.range_feature_engineering import prepare_features, TARGET_COLUMN


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_path = os.path.join(repo_root, "ml", "datasets", "sample_driving_range_telemetry.csv")
    df = pd.read_csv(data_path)

    X = prepare_features(df)
    y = df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestRegressor(n_estimators=100, random_state=42)),
    ])

    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print({"mae": mae, "r2": r2})

    models_dir = os.path.join(repo_root, "ml", "models")
    os.makedirs(models_dir, exist_ok=True)
    artifact_path = os.path.join(models_dir, "range_model.joblib")
    joblib.dump(pipeline, artifact_path)
    print("Saved range model to", artifact_path)


if __name__ == "__main__":
    main()
