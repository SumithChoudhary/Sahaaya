from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

FEATURE_NAMES = [
    "population_affected", "severity", "emergency_requests", "injured_people",
    "trapped_people", "accessibility", "distance_to_resource_center",
]
CLASS_NAMES = ["Low", "Medium", "High", "Critical"]


def _priority_model():
    """Train a reproducible demo classifier against synthetic rule-generated labels.

    This is a UI/service demonstration. The generated labels encode prototype
    heuristics and are not validated disaster outcome labels.
    """
    rng = np.random.default_rng(32017)
    row_count = 2400
    frame = pd.DataFrame({
        "population_affected": rng.integers(0, 18000, row_count),
        "severity": rng.integers(1, 6, row_count),
        "emergency_requests": rng.integers(0, 100, row_count),
        "injured_people": rng.integers(0, 260, row_count),
        "trapped_people": rng.integers(0, 120, row_count),
        "accessibility": rng.integers(1, 6, row_count),
        "distance_to_resource_center": rng.uniform(0, 35, row_count),
    })
    severity = (frame.severity - 1) / 4
    score = (
        0.20 * np.log1p(frame.population_affected) / np.log1p(18000)
        + 0.23 * severity
        + 0.16 * np.log1p(frame.emergency_requests) / np.log1p(100)
        + 0.15 * np.log1p(frame.injured_people) / np.log1p(260)
        + 0.14 * np.log1p(frame.trapped_people) / np.log1p(120)
        + 0.06 * (6 - frame.accessibility) / 5
        + 0.06 * frame.distance_to_resource_center / 35
    )
    jitter = rng.normal(0, 0.035, row_count)
    labels = pd.cut(score + jitter, [-np.inf, 0.28, 0.45, 0.64, np.inf], labels=CLASS_NAMES).astype(str)
    x_train, x_test, y_train, y_test = train_test_split(frame, labels, test_size=0.2, random_state=17, stratify=labels)
    model = RandomForestClassifier(n_estimators=120, max_depth=9, min_samples_leaf=2, class_weight="balanced", random_state=17, n_jobs=1)
    model.fit(x_train, y_train)
    return model, accuracy_score(y_test, model.predict(x_test)), len(x_test)


@lru_cache(maxsize=1)
def _cached_model():
    return _priority_model()


def predict_priority(payload: dict) -> dict:
    model, demo_accuracy, validation_rows = _cached_model()
    row = pd.DataFrame([{key: payload[key] for key in FEATURE_NAMES}], columns=FEATURE_NAMES)
    class_probabilities = model.predict_proba(row)[0]
    classes = list(model.classes_)
    predicted_class = classes[int(np.argmax(class_probabilities))]
    probabilities = dict(zip(classes, class_probabilities.tolist()))
    risk_score = round(sum(probabilities.get(name, 0) * (index / (len(CLASS_NAMES) - 1) * 100) for index, name in enumerate(CLASS_NAMES)))

    # Keep the explanation tied to this input and the synthetic model's importances.
    scales = {
        "population_affected": 18000, "severity": 5, "emergency_requests": 100,
        "injured_people": 260, "trapped_people": 120, "accessibility": 5,
        "distance_to_resource_center": 35,
    }
    contributions = []
    for name, importance in zip(FEATURE_NAMES, model.feature_importances_):
        value = float(payload[name])
        normalized = (6 - value) / 5 if name == "accessibility" else min(value / scales[name], 1)
        contributions.append({"feature": name, "value": value, "importance": round(float(importance), 4), "signal": round(float(importance * normalized), 4)})
    contributions.sort(key=lambda feature: feature["signal"], reverse=True)
    top = [entry for entry in contributions if entry["signal"] > 0][:3]
    explanation = "Higher " + ", ".join(item["feature"].replace("_", " ") for item in top) + " contributed most among the available sample features."
    if not top:
        explanation = "The demo model returned a class from the supplied values; feature contribution is low for this sample."

    return {
        "priority_score": risk_score,
        "priority_class": predicted_class,
        "probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "feature_importance": [{"feature": name, "importance": round(float(value), 4)} for name, value in zip(FEATURE_NAMES, model.feature_importances_)],
        "contributions": contributions,
        "explanation": explanation,
        "model_status": "Synthetic demo model · not validated on real disaster outcomes",
        "performance": {"metric": "accuracy", "value": round(float(demo_accuracy), 3), "evaluation": "Held-out rows from synthetic rule-generated labels", "sample_size": validation_rows},
    }
