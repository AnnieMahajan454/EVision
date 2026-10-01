"""Tiny file-based model registry: one joblib artifact per model name."""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib


class ModelUnavailableError(RuntimeError):
    pass


@dataclass
class ModelArtifact:
    name: str
    version: str
    estimator: Any
    feature_names: list[str]
    metrics: dict[str, float]
    trained_at: datetime
    train_cutoff: date
    extra: dict[str, Any] = field(default_factory=dict)

    def predict(self, design_matrix) -> list[float]:
        return [float(v) for v in self.estimator.predict(design_matrix[self.feature_names])]


def artifact_path(models_dir: Path, name: str) -> Path:
    return Path(models_dir) / f"{name}.joblib"


def save_artifact(artifact: ModelArtifact, models_dir: Path) -> Path:
    path = artifact_path(models_dir, artifact.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    return path


def load_artifact(models_dir: Path, name: str) -> ModelArtifact:
    path = artifact_path(models_dir, name)
    if not path.exists():
        raise ModelUnavailableError(
            f"Model '{name}' has not been trained yet (expected {path}). See ml/README.md."
        )
    return joblib.load(path)
