"""Simple evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BinaryMetrics:
    tp: int
    tn: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def binary_metrics(y_true: list[int], y_pred: list[int]) -> BinaryMetrics:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return BinaryMetrics(tp, tn, fp, fn, precision, recall, f1)
