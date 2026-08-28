"""Generate the compact-model fixtures the ``CompactPredictor`` tests read.

The ``.tmc`` files here are written by the **publisher of the format** —
``tempest_fastapi_sdk.modelops.export_sklearn_to_compact`` — so the reader in
``tempestweb.tabular.compact`` is measured against files it did not produce.
Alongside each model goes the answer **scikit-learn itself** gives for the same
rows, which is what turns a parity test into a fact instead of a self-agreement.

sklearn, numpy and the SDK never enter the runtime: run this in a throwaway
environment, from the repository root::

    uvx --with scikit-learn --with numpy --with tempest-fastapi-sdk \\
        --from tempestweb python -m tests.conformance._compact_models

It rewrites ``tests/fixtures/compact/*.tmc`` and
``tests/fixtures/compact_expectations.json``.

Every tree case carries one extra row on purpose: a **float32 boundary row**
(:func:`_float32_boundary_row`), the only kind of row where routing in float64
answers differently than scikit-learn does. Without it the parity matrix passed
with the reader's float32 narrowing removed, which is the one thing that matrix
is there to catch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODELS = FIXTURES / "compact"
EXPECTATIONS = FIXTURES / "compact_expectations.json"

ROW_COUNT = 6


def _fitted_trees(estimator: Any) -> list[Any]:
    """Collect every fitted ``sklearn.tree`` inside an estimator.

    Args:
        estimator: A fitted single tree or an ensemble of them.

    Returns:
        The ``tree_`` object of each tree, one entry for a single tree and one
        per member for an ensemble.
    """
    members = getattr(estimator, "estimators_", None)
    if members is None:
        return [estimator.tree_]
    return [member.tree_ for member in members]


def _float32_boundary_row(estimator: Any, base: Any) -> Any:
    """Build a row that sits exactly on the float32 side of a split threshold.

    This is the row the parity matrix was missing. ``sklearn.tree`` casts its
    input to **float32** before traversing, so a value just above a threshold in
    float64 compares *equal* to it once narrowed and goes **left**, where float64
    arithmetic would have gone right. Every other row in the matrix routes the
    same way in both precisions, which is why the whole suite stayed green with
    the reader's ``_as_float32`` replaced by the identity.

    So for each feature that any tree splits on, this picks the threshold used by
    the most nodes (ties resolved by the smaller value, so the choice is
    deterministic), keeps only thresholds that float32 represents exactly — a
    threshold that does not is a different question, about the *writer* narrowing
    it — and sets the feature to the next float64 above it. Narrowed, that value
    is the threshold again.

    Args:
        estimator: The fitted tree or ensemble.
        base: A real row of the dataset, whose values the boundary ones replace.

    Returns:
        The boundary row, as a float64 array.
    """
    import numpy

    counts: dict[int, dict[float, int]] = {}
    for tree in _fitted_trees(estimator):
        for node in range(tree.node_count):
            feature = int(tree.feature[node])
            threshold = float(tree.threshold[node])
            if feature < 0 or float(numpy.float32(threshold)) != threshold:
                continue
            per_feature = counts.setdefault(feature, {})
            per_feature[threshold] = per_feature.get(threshold, 0) + 1

    row = numpy.array(base, dtype="float64")
    for feature, thresholds in counts.items():
        chosen = max(sorted(thresholds), key=lambda value: thresholds[value])
        row[feature] = numpy.nextafter(chosen, numpy.inf)
    return row


def _cases() -> list[dict[str, Any]]:
    """Build the fitted estimators the fixtures cover.

    Returns:
        One entry per fixture: its name, the fitted estimator, the feature
        names, and the rows every expectation is computed on.
    """
    import numpy
    from sklearn.datasets import load_breast_cancer, load_iris
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeRegressor

    cancer = load_breast_cancer()
    iris = load_iris()

    binary_x = numpy.asarray(cancer.data[:, :6], dtype="float64")
    binary_y = numpy.asarray(cancer.target)
    binary_names = [str(name) for name in cancer.feature_names[:6]]

    iris_x = numpy.asarray(iris.data, dtype="float64")
    iris_y = numpy.asarray([iris.target_names[index] for index in iris.target])
    iris_names = [str(name) for name in iris.feature_names]

    return [
        {
            "name": "linear_binary_sigmoid",
            "estimator": LogisticRegression(max_iter=5000).fit(binary_x, binary_y),
            "features": binary_names,
            "rows": binary_x[:ROW_COUNT],
        },
        {
            "name": "linear_multiclass_softmax",
            "estimator": LogisticRegression(max_iter=5000).fit(iris_x, iris_y),
            "features": iris_names,
            "rows": iris_x[:: len(iris_x) // ROW_COUNT][:ROW_COUNT],
        },
        {
            "name": "linear_regression_identity",
            "estimator": LinearRegression().fit(binary_x, binary_y.astype("float64")),
            "features": binary_names,
            "rows": binary_x[:ROW_COUNT],
        },
        {
            "name": "forest_classifier_normalize",
            "estimator": RandomForestClassifier(
                n_estimators=12, max_depth=5, random_state=0
            ).fit(iris_x, iris_y),
            "features": iris_names,
            "rows": iris_x[:: len(iris_x) // ROW_COUNT][:ROW_COUNT],
            "boundary": True,
        },
        {
            "name": "tree_regressor_identity",
            "estimator": DecisionTreeRegressor(max_depth=4, random_state=0).fit(
                binary_x, binary_y.astype("float64")
            ),
            "features": binary_names,
            "rows": binary_x[:ROW_COUNT],
            "boundary": True,
        },
        {
            "name": "pipeline_scaler_linear",
            "estimator": Pipeline(
                [
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(max_iter=5000)),
                ]
            ).fit(binary_x, binary_y),
            "features": binary_names,
            "rows": binary_x[:ROW_COUNT],
        },
    ]


def main() -> None:
    """Write every ``.tmc`` fixture and the sklearn answers beside it."""
    from tempest_fastapi_sdk.modelops import export_sklearn_to_compact

    MODELS.mkdir(parents=True, exist_ok=True)
    expectations: dict[str, Any] = {}

    import numpy

    for case in _cases():
        name = str(case["name"])
        estimator = case["estimator"]
        rows = case["rows"]
        features = [str(feature) for feature in case["features"]]
        if case.get("boundary"):
            rows = numpy.vstack(
                [rows, _float32_boundary_row(estimator, rows[0])],
            )
        export = export_sklearn_to_compact(
            estimator,
            rows,
            MODELS / f"{name}.tmc",
            feature_names=features,
        )
        if not export.verified:
            raise RuntimeError(f"{name}: the SDK refused to verify its own export")

        predicted = [str(value) for value in estimator.predict(rows)]
        probabilities: list[list[float]] = []
        if hasattr(estimator, "predict_proba"):
            probabilities = [
                [float(value) for value in row] for row in estimator.predict_proba(rows)
            ]

        expectations[name] = {
            "estimator": export.estimator,
            "kind": str(export.kind),
            "task": str(export.task),
            "features": features,
            "classes": list(export.classes),
            "size_bytes": export.size_bytes,
            "max_abs_diff": export.max_abs_diff,
            "rows": [
                dict(zip(features, (float(value) for value in row), strict=True))
                for row in rows
            ],
            "labels": predicted,
            "probabilities": probabilities,
        }

    EXPECTATIONS.write_text(
        json.dumps(expectations, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
