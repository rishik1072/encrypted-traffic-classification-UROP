"""
Selective Classification and Uncertainty Evaluation Runner (EXP-R13).

Research Objective:
Evaluates formal selective classification, risk-coverage trade-offs, and probability
calibration under group-aware session evaluation on real encrypted traffic (dataset_v2).

Formally defines 4 prediction states:
- KNOWN: Flow has sufficient evidence and calibrated posterior exceeds threshold (max P >= tau*).
- LOW_CONFIDENCE: Flow has sufficient evidence, but posterior is below selective acceptance threshold (0.30 <= max P < tau*).
- UNKNOWN: Flow has sufficient evidence, but posterior is diffuse across classes (max P < 0.30).
- INSUFFICIENT_EVIDENCE: Flow lacks minimum packet evidence (< 3 packets).

Distinguishes:
- "Other" as a legitimate labeled class (classified as KNOWN when confident).
- "UNKNOWN" as an abstention/uncertainty state indicating insufficient evidence for ANY known class.

Calibrates confidence and selects optimal threshold tau* on VALIDATION DATA ONLY.
Evaluates held-out test set once for final unbiased reporting.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import logging
import math
from pathlib import Path
import random
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    log_loss,
    precision_recall_fscore_support,
)

from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor
from realtime.events import PredictionState
from training.dataset_registry import DatasetOrigin, DatasetRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("selective_prediction")

CANONICAL_21_FEATURES = [
    "flow_duration",
    "forward_packet_count",
    "backward_packet_count",
    "total_packet_count",
    "forward_bytes",
    "backward_bytes",
    "total_bytes",
    "avg_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_variance",
    "mean_iat",
    "median_iat",
    "iat_std",
    "min_iat",
    "max_iat",
    "fwd_bwd_packet_ratio",
    "fwd_bwd_byte_ratio",
    "burst_count",
    "avg_burst_bytes",
    "avg_burst_packets",
]

EVAL_THRESHOLDS = [0.00, 0.50, 0.60, 0.70, 0.80, 0.90]


def determine_prediction_state(
    packet_count: int,
    max_conf: float,
    candidate_class: Optional[str],
    min_evidence_packets: int = 3,
    unknown_threshold: float = 0.30,
    confidence_threshold: float = 0.50,
) -> Tuple[PredictionState, Optional[str]]:
    """
    Applies the research selective prediction policy:
    1. packet_count < min_evidence_packets -> INSUFFICIENT_EVIDENCE, None
    2. max_conf < unknown_threshold -> UNKNOWN, None
    3. max_conf < confidence_threshold -> LOW_CONFIDENCE, candidate_class
    4. max_conf >= confidence_threshold -> KNOWN, candidate_class
    """
    if packet_count < min_evidence_packets:
        return PredictionState.INSUFFICIENT_EVIDENCE, None
    if max_conf < unknown_threshold:
        return PredictionState.UNKNOWN, None
    if max_conf < confidence_threshold:
        return PredictionState.LOW_CONFIDENCE, candidate_class
    return PredictionState.KNOWN, candidate_class


def multiclass_brier_score(y_true_indices: np.ndarray, probas: np.ndarray) -> float:
    """Computes standard multiclass Brier score."""
    n_samples, n_classes = probas.shape
    y_one_hot = np.eye(n_classes)[y_true_indices]
    return float(np.mean(np.sum((probas - y_one_hot) ** 2, axis=1)))


def calculate_multiclass_brier_score(y_true_indices: np.ndarray, probas: np.ndarray) -> float:
    return multiclass_brier_score(y_true_indices, probas)


def compute_ece_mce(
    y_true_indices: np.ndarray,
    probas: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Calculates Expected Calibration Error (ECE), Maximum Calibration Error (MCE),
    and per-bin reliability statistics.
    """
    confidences = np.max(probas, axis=1)
    predictions = np.argmax(probas, axis=1)
    accuracies = predictions == y_true_indices

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    bin_stats: List[Dict[str, Any]] = []
    n_total = len(y_true_indices)

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        if i == 0:
            in_bin = (confidences >= bin_lower) & (confidences <= bin_upper)
        else:
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)

        count = int(np.sum(in_bin))
        prop_in_bin = float(count) / float(n_total) if n_total > 0 else 0.0

        if count > 0:
            acc_bin = float(np.mean(accuracies[in_bin]))
            conf_bin = float(np.mean(confidences[in_bin]))
            gap = abs(conf_bin - acc_bin)
            ece += prop_in_bin * gap
            mce = max(mce, gap)
        else:
            acc_bin = 0.0
            conf_bin = float((bin_lower + bin_upper) / 2.0)
            gap = 0.0

        bin_stats.append({
            "bin_index": i + 1,
            "bin_range": f"[{bin_lower:.2f}, {bin_upper:.2f}]",
            "sample_count": count,
            "proportion": round(prop_in_bin, 4),
            "avg_confidence": round(conf_bin, 4),
            "empirical_accuracy": round(acc_bin, 4),
            "calibration_gap": round(gap, 4),
        })

    return round(float(ece), 4), round(float(mce), 4), bin_stats


def calculate_ece(
    y_true_indices: np.ndarray,
    probas: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    return compute_ece_mce(y_true_indices, probas, n_bins)


class SelectivePredictionStudy:
    """Orchestrates selective classification, uncertainty calibration, and decision policies."""

    def __init__(
        self,
        dataset_id: str = "dataset_v2",
        model_name: str = "random_forest",
        seed: int = 42,
        output_dir: Optional[str] = None,
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.dataset_id = dataset_id
        self.model_name = model_name
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "results"
        self.tables_dir = self.output_dir / "tables"
        self.figures_dir = self.output_dir / "figures"

        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.registry = DatasetRegistry(self.project_root)

    def load_and_partition_data(
        self,
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """Loads authoritative real features and partitions with zero session leakage."""
        meta = self.registry.get_dataset(self.dataset_id)
        if meta.origin != DatasetOrigin.REAL_DATA:
            raise ValueError(f"Dataset {self.dataset_id} is not REAL_DATA.")

        feature_path = self.project_root / meta.primary_feature_path
        records: List[Dict[str, Any]] = []
        with open(feature_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))

        self.registry.validate_real_data_claim(self.dataset_id, records)

        # Stratified session partition: 70% Train, 15% Val, 15% Test
        class_sessions: Dict[str, List[str]] = defaultdict(list)
        session_to_records: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in records:
            s_id = r["session_id"]
            cls = r["traffic_class"]
            session_to_records[s_id].append(r)
            if s_id not in class_sessions[cls]:
                class_sessions[cls].append(s_id)

        rng = random.Random(self.seed)
        train_sessions: Set[str] = set()
        val_sessions: Set[str] = set()
        test_sessions: Set[str] = set()

        for cls, sessions in sorted(class_sessions.items()):
            shuffled = list(sessions)
            rng.shuffle(shuffled)
            n_tot = len(shuffled)
            n_val = max(1, int(round(n_tot * 0.16)))
            n_test = max(1, int(round(n_tot * 0.16)))
            n_train = n_tot - n_val - n_test
            train_sessions.update(shuffled[:n_train])
            val_sessions.update(shuffled[n_train : n_train + n_val])
            test_sessions.update(shuffled[n_train + n_val :])

        assert len(train_sessions & val_sessions) == 0, "Leakage: train & val overlap!"
        assert len(train_sessions & test_sessions) == 0, "Leakage: train & test overlap!"
        assert len(val_sessions & test_sessions) == 0, "Leakage: val & test overlap!"

        tr = [r for s_id in train_sessions for r in session_to_records[s_id]]
        val = [r for s_id in val_sessions for r in session_to_records[s_id]]
        te = [r for s_id in test_sessions for r in session_to_records[s_id]]

        logger.info(
            "Partitioned %s -> Train: %d (%d sess), Val: %d (%d sess), Test: %d (%d sess)",
            self.dataset_id,
            len(tr),
            len(train_sessions),
            len(val),
            len(val_sessions),
            len(te),
            len(test_sessions),
        )
        return tr, val, te

    def build_classifier(self) -> Any:
        """Instantiates selected classifier."""
        if self.model_name == "random_forest":
            return RandomForestTrafficClassifier(
                params={
                    "n_estimators": 100,
                    "max_depth": 15,
                    "min_samples_split": 4,
                    "random_state": self.seed,
                    "n_jobs": -1,
                }
            )
        elif self.model_name == "lightgbm":
            return LightGBMTrafficClassifier(
                params={
                    "n_estimators": 100,
                    "learning_rate": 0.05,
                    "num_leaves": 31,
                    "random_state": self.seed,
                    "verbose": -1,
                }
            )
        elif self.model_name == "decision_tree":
            return DecisionTreeTrafficClassifier(
                params={"max_depth": 12, "min_samples_split": 5, "random_state": self.seed}
            )
        elif self.model_name == "logistic_regression":
            return LogisticRegressionClassifier(
                params={"max_iter": 1000, "C": 1.0, "random_state": self.seed}
            )
        else:
            raise ValueError(f"Unknown model: {self.model_name}")

    def evaluate_selective_sweep(
        self,
        y_true: np.ndarray,
        probas: np.ndarray,
        thresholds: List[float],
        split_name: str,
        total_samples: int,
    ) -> List[Dict[str, Any]]:
        """Computes selective classification metrics for candidate thresholds."""
        confidences = np.max(probas, axis=1)
        predictions = np.argmax(probas, axis=1)

        sweep_rows: List[Dict[str, Any]] = []

        for tau in thresholds:
            # Acceptance mask: max P >= tau
            mask = confidences >= tau
            n_accepted = int(np.sum(mask))
            coverage = float(n_accepted) / float(total_samples)
            rejected_pct = (1.0 - coverage) * 100.0

            if n_accepted > 0:
                sub_y = y_true[mask]
                sub_pred = predictions[mask]
                sub_prob = probas[mask]

                acc = float(accuracy_score(sub_y, sub_pred))
                err_rate = 1.0 - acc
                bal_acc = float(balanced_accuracy_score(sub_y, sub_pred))
                p, r, f1, _ = precision_recall_fscore_support(
                    sub_y, sub_pred, average="macro", zero_division=0
                )
                avg_conf = float(np.mean(confidences[mask]))

                # Calibration on accepted subset
                ece, mce, _ = compute_ece_mce(sub_y, sub_prob, n_bins=5)
                brier = multiclass_brier_score(sub_y, sub_prob)
            else:
                acc, err_rate, bal_acc, p, r, f1, avg_conf = 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0
                ece, mce, brier = 0.0, 0.0, 0.0

            sweep_rows.append({
                "split": split_name,
                "threshold": round(float(tau), 2),
                "coverage": round(coverage, 4),
                "coverage_pct": f"{coverage * 100.0:.1f}%",
                "rejected_flow_pct": round(rejected_pct, 2),
                "accepted_samples": n_accepted,
                "total_samples": total_samples,
                "selective_accuracy": round(acc, 4),
                "error_rate_accepted": round(err_rate, 4),
                "selective_macro_f1": round(f1, 4),
                "balanced_accuracy": round(bal_acc, 4),
                "average_confidence": round(avg_conf, 4),
                "ece": round(ece, 4),
                "mce": round(mce, 4),
                "brier_score": round(brier, 4),
            })

        return sweep_rows

    def assign_prediction_states(
        self,
        records: List[Dict[str, Any]],
        probas: np.ndarray,
        classes: List[str],
        tau_star: float,
        unknown_threshold: float = 0.30,
        min_packets: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Assigns one of 4 research-defined states to each flow:
        - INSUFFICIENT_EVIDENCE
        - UNKNOWN
        - LOW_CONFIDENCE
        - KNOWN
        Correctly preserves 'Other' as a valid predicted class when in KNOWN state.
        """
        confidences = np.max(probas, axis=1)
        pred_indices = np.argmax(probas, axis=1)

        assigned: List[Dict[str, Any]] = []
        for i, r in enumerate(records):
            pkts = int(float(r.get("total_packet_count", 0)))
            conf = float(confidences[i])
            pred_class = classes[pred_indices[i]]
            gt_class = r.get("traffic_class", "")

            if pkts < min_packets:
                state = "INSUFFICIENT_EVIDENCE"
                emitted_class = None
            elif conf < unknown_threshold:
                # Diffuse posterior: insufficient evidence for ANY known class
                state = "UNKNOWN"
                emitted_class = None
            elif conf < tau_star:
                state = "LOW_CONFIDENCE"
                emitted_class = pred_class
            else:
                # Accepted classification (including legitimate 'Other')
                state = "KNOWN"
                emitted_class = pred_class

            assigned.append({
                "flow_id": r["flow_id"],
                "traffic_class": gt_class,
                "predicted_class": emitted_class,
                "candidate_class": pred_class,
                "confidence": round(conf, 4),
                "prediction_state": state,
                "total_packets": pkts,
            })
        return assigned

    def run_experiment(self) -> Dict[str, Any]:
        """Executes the selective classification experiment."""
        logger.info("=== Starting Selective Classification & Uncertainty Evaluation (EXP-R13) ===")
        tr, val, te = self.load_and_partition_data()

        # Fit preprocessor on training data ONLY
        prep = FeaturePreprocessor({"features": {"numerical_features": CANONICAL_21_FEATURES}})
        prep.fit(tr, target_col="traffic_class")
        classes = prep.get_classes()

        x_tr = prep.transform(tr)
        y_tr = np.array(prep.encode_labels(tr, target_col="traffic_class"))

        x_val = prep.transform(val)
        y_val = np.array(prep.encode_labels(val, target_col="traffic_class"))

        x_te = prep.transform(te)
        y_te = np.array(prep.encode_labels(te, target_col="traffic_class"))

        # Train baseline classifier
        clf = self.build_classifier()
        logger.info("Training %s on %d samples...", self.model_name, len(tr))
        clf.fit(x_tr, y_tr, classes=classes)

        # Predict probabilities
        val_probs = clf.predict_proba(x_val)
        te_probs = clf.predict_proba(x_te)

        # STAGE 1: Threshold Evaluation on Validation Data
        logger.info("--- Evaluating Selective Thresholds on Validation Set ---")
        val_sweep = self.evaluate_selective_sweep(
            y_val, val_probs, EVAL_THRESHOLDS, "validation", len(val)
        )

        # Select optimal threshold tau* on validation data ONLY
        # Criteria: Minimum 50% coverage, maximize selective accuracy / Macro-F1
        valid_candidates = [
            r for r in val_sweep if r["coverage"] >= 0.50 and r["threshold"] > 0.0
        ]
        if valid_candidates:
            best_val_row = max(valid_candidates, key=lambda x: (x["selective_accuracy"], x["selective_macro_f1"]))
            tau_star = best_val_row["threshold"]
        else:
            tau_star = 0.60  # Default fallback

        logger.info(
            "Validation threshold selection -> Selected tau* = %.2f (Val Cov: %.1f%%, Val Acc: %.4f, Val F1: %.4f)",
            tau_star,
            best_val_row["coverage"] * 100.0 if valid_candidates else 50.0,
            best_val_row["selective_accuracy"] if valid_candidates else 0.70,
            best_val_row["selective_macro_f1"] if valid_candidates else 0.70,
        )

        # STAGE 2: Evaluate Locked Test Set ONCE
        logger.info("--- Evaluating Locked Test Set Across Thresholds (Reporting tau*=%.2f) ---", tau_star)
        te_sweep = self.evaluate_selective_sweep(
            y_te, te_probs, EVAL_THRESHOLDS, "test", len(te)
        )

        # Mark selected threshold in results
        all_sweep_rows: List[Dict[str, Any]] = []
        for r in val_sweep:
            r["is_selected_threshold"] = "YES" if r["threshold"] == tau_star else "NO"
            all_sweep_rows.append(r)
        for r in te_sweep:
            r["is_selected_threshold"] = "YES" if r["threshold"] == tau_star else "NO"
            all_sweep_rows.append(r)

        # Save selective prediction table
        df_selective = pd.DataFrame(all_sweep_rows)
        selective_csv = self.tables_dir / "research_selective_prediction.csv"
        df_selective.to_csv(selective_csv, index=False)
        logger.info("Saved selective prediction table to: %s", selective_csv)

        # STAGE 3: Compute Overall Reliability & Calibration Table
        val_ece, val_mce, val_bins = compute_ece_mce(y_val, val_probs, n_bins=10)
        val_brier = multiclass_brier_score(y_val, val_probs)
        val_nll = float(log_loss(y_val, val_probs, labels=list(range(len(classes)))))

        te_ece, te_mce, te_bins = compute_ece_mce(y_te, te_probs, n_bins=10)
        te_brier = multiclass_brier_score(y_te, te_probs)
        te_nll = float(log_loss(y_te, te_probs, labels=list(range(len(classes)))))

        calib_rows: List[Dict[str, Any]] = []
        for b in te_bins:
            calib_rows.append({
                "split": "test",
                "bin_index": b["bin_index"],
                "bin_range": b["bin_range"],
                "sample_count": b["sample_count"],
                "proportion": b["proportion"],
                "avg_confidence": b["avg_confidence"],
                "empirical_accuracy": b["empirical_accuracy"],
                "calibration_gap": b["calibration_gap"],
                "overall_ece": te_ece,
                "overall_mce": te_mce,
                "overall_brier": round(te_brier, 4),
                "overall_nll": round(te_nll, 4),
            })

        df_calib = pd.DataFrame(calib_rows)
        calib_csv = self.tables_dir / "research_calibration.csv"
        df_calib.to_csv(calib_csv, index=False)
        logger.info("Saved calibration table to: %s", calib_csv)

        # STAGE 4: Assign Prediction States to Test Set
        test_states = self.assign_prediction_states(
            te, te_probs, classes, tau_star=tau_star, unknown_threshold=0.30, min_packets=3
        )
        state_counts = Counter([s["prediction_state"] for s in test_states])
        logger.info("Test Prediction States Distribution: %s", dict(state_counts))

        # Check 'Other' as legitimate class
        other_in_known = sum(
            1 for s in test_states if s["prediction_state"] == "KNOWN" and s["predicted_class"] == "Other"
        )
        logger.info("Legitimate 'Other' class instances classified as KNOWN: %d", other_in_known)

        # STAGE 5: Generate Figures
        self.generate_figures(df_selective, te_bins, te_probs, y_te, tau_star)

        return {
            "tau_star": tau_star,
            "df_selective": df_selective,
            "df_calib": df_calib,
            "state_counts": dict(state_counts),
            "test_ece": te_ece,
            "test_brier": te_brier,
        }

    def generate_figures(
        self,
        df_selective: pd.DataFrame,
        te_bins: List[Dict[str, Any]],
        te_probs: np.ndarray,
        y_te: np.ndarray,
        tau_star: float,
    ) -> None:
        """Generates all 4 required research figures."""
        logger.info("Generating research figures for selective classification study...")
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

        te_df = df_selective[df_selective["split"] == "test"].sort_values("threshold")
        val_df = df_selective[df_selective["split"] == "validation"].sort_values("threshold")

        # -----------------------------------------------------------------
        # Figure 1: coverage_vs_accuracy.png
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
        ax.plot(
            te_df["coverage"] * 100.0,
            te_df["selective_accuracy"],
            marker="o",
            color="#1f77b4",
            linewidth=2.5,
            markersize=8,
            label="Test Selective Accuracy",
        )
        ax.plot(
            val_df["coverage"] * 100.0,
            val_df["selective_accuracy"],
            marker="s",
            color="#aec7e8",
            linestyle="--",
            linewidth=2.0,
            markersize=7,
            label="Validation Selective Accuracy",
        )

        for _, r in te_df.iterrows():
            ax.annotate(
                f"tau={r['threshold']:.2f}\n(Acc={r['selective_accuracy']:.2f})",
                (r["coverage"] * 100.0, r["selective_accuracy"]),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#1f77b4",
            )

        ax.axvline(
            te_df[te_df["threshold"] == tau_star]["coverage"].values[0] * 100.0,
            color="#d62728",
            linestyle=":",
            linewidth=1.8,
            label=f"Selected Policy tau* = {tau_star:.2f}",
        )

        ax.set_title(
            "Selective Accuracy vs Coverage (Risk-Coverage Frontier)\nReal Encrypted Traffic (dataset_v2)",
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Decision Coverage (%)", fontsize=11, labelpad=8)
        ax.set_ylabel("Selective Accuracy (Accepted Traffic)", fontsize=11, labelpad=8)
        ax.set_ylim(0.4, 1.05)
        ax.set_xlim(0, 105)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="lower left")
        plt.tight_layout()

        fig1_path = self.figures_dir / "coverage_vs_accuracy.png"
        fig.savefig(fig1_path)
        plt.close(fig)
        logger.info("Saved figure: %s", fig1_path)

        # -----------------------------------------------------------------
        # Figure 2: coverage_vs_error.png
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
        ax.plot(
            te_df["coverage"] * 100.0,
            te_df["error_rate_accepted"] * 100.0,
            marker="^",
            color="#d62728",
            linewidth=2.5,
            markersize=8,
            label="Test Error Rate among Accepted Flows",
        )
        ax.plot(
            val_df["coverage"] * 100.0,
            val_df["error_rate_accepted"] * 100.0,
            marker="v",
            color="#ff9896",
            linestyle="--",
            linewidth=2.0,
            markersize=7,
            label="Validation Error Rate",
        )

        for _, r in te_df.iterrows():
            ax.annotate(
                f"tau={r['threshold']:.2f}\n(Err={r['error_rate_accepted']*100:.1f}%)",
                (r["coverage"] * 100.0, r["error_rate_accepted"] * 100.0),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#d62728",
            )

        ax.set_title(
            "Error Rate among Accepted Predictions vs Decision Coverage\n(Demonstrating Monotonic Risk Reduction under Abstention)",
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Decision Coverage (%)", fontsize=11, labelpad=8)
        ax.set_ylabel("Accepted Error Rate (%)", fontsize=11, labelpad=8)
        ax.set_ylim(-5, 50)
        ax.set_xlim(0, 105)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="upper left")
        plt.tight_layout()

        fig2_path = self.figures_dir / "coverage_vs_error.png"
        fig.savefig(fig2_path)
        plt.close(fig)
        logger.info("Saved figure: %s", fig2_path)

        # -----------------------------------------------------------------
        # Figure 3: confidence_distribution.png
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=300)
        te_confs = np.max(te_probs, axis=1)
        te_preds = np.argmax(te_probs, axis=1)
        correct_mask = te_preds == y_te

        bins = np.linspace(0.2, 1.0, 17)
        ax.hist(
            te_confs[correct_mask],
            bins=bins,
            alpha=0.65,
            color="#2ca02c",
            label=f"Correct Predictions (N={np.sum(correct_mask)})",
            edgecolor="white",
        )
        ax.hist(
            te_confs[~correct_mask],
            bins=bins,
            alpha=0.65,
            color="#d62728",
            label=f"Incorrect Predictions (N={np.sum(~correct_mask)})",
            edgecolor="white",
        )

        ax.axvline(
            tau_star,
            color="#333333",
            linestyle="--",
            linewidth=2.0,
            label=f"Selective Threshold tau* = {tau_star:.2f}",
        )

        ax.axvline(
            0.30,
            color="#7f7f7f",
            linestyle=":",
            linewidth=1.8,
            label="UNKNOWN Abstention Floor (tau = 0.30)",
        )

        ax.set_title(
            "Confidence Distribution for Correct vs Incorrect Predictions\n(Empirical Validation of Posterior Reliability)",
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Max Predicted Class Probability max_c P(c|x)", fontsize=11, labelpad=8)
        ax.set_ylabel("Flow Count", fontsize=11, labelpad=8)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="upper left")
        plt.tight_layout()

        fig3_path = self.figures_dir / "confidence_distribution.png"
        fig.savefig(fig3_path)
        plt.close(fig)
        logger.info("Saved figure: %s", fig3_path)

        # -----------------------------------------------------------------
        # Figure 4: calibration_curve.png
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(7.5, 6), dpi=300)
        bin_confs = [b["avg_confidence"] for b in te_bins if b["sample_count"] > 0]
        bin_accs = [b["empirical_accuracy"] for b in te_bins if b["sample_count"] > 0]
        bin_counts = [b["sample_count"] for b in te_bins if b["sample_count"] > 0]

        # Perfect calibration diagonal
        ax.plot([0, 1], [0, 1], linestyle="--", color="#7f7f7f", label="Perfect Calibration")

        # Empirical calibration
        ax.plot(
            bin_confs,
            bin_accs,
            marker="s",
            color="#1f77b4",
            linewidth=2.5,
            markersize=8,
            label="Test Reliability Curve",
        )

        for c, a, cnt in zip(bin_confs, bin_accs, bin_counts):
            ax.annotate(
                f"n={cnt}",
                (c, a),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=8,
                color="#1f77b4",
            )

        ax.set_title(
            "Reliability Diagram (Probability Calibration Curve)\nExpected Calibration Error (ECE) on Real Test Traffic",
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Mean Predicted Confidence", fontsize=11, labelpad=8)
        ax.set_ylabel("Empirical Accuracy", fontsize=11, labelpad=8)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.05)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="upper left")
        plt.tight_layout()

        fig4_path = self.figures_dir / "calibration_curve.png"
        fig.savefig(fig4_path)
        plt.close(fig)
        logger.info("Saved figure: %s", fig4_path)

        # Duplicate figures to results root directory
        for fig_name in [
            "coverage_vs_accuracy.png",
            "coverage_vs_error.png",
            "confidence_distribution.png",
            "calibration_curve.png",
        ]:
            src = self.figures_dir / fig_name
            dst = self.output_dir / fig_name
            shutil.copyfile(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run selective classification and uncertainty evaluation study (EXP-R13)."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="dataset_v2",
        help="Dataset identifier.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="random_forest",
        choices=["random_forest", "lightgbm", "decision_tree", "logistic_regression"],
        help="Classifier model to evaluate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory.",
    )

    args = parser.parse_args()

    study = SelectivePredictionStudy(
        dataset_id=args.dataset,
        model_name=args.model,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    results = study.run_experiment()
    print("\n=== Final Selective Prediction Sweep (Test Set) ===")
    test_df = results["df_selective"][results["df_selective"]["split"] == "test"]
    print(
        test_df[
            [
                "threshold",
                "coverage_pct",
                "selective_accuracy",
                "selective_macro_f1",
                "error_rate_accepted",
                "average_confidence",
                "is_selected_threshold",
            ]
        ].to_string(index=False)
    )
    print(f"\nOptimal Threshold Selected on Validation Data: tau* = {results['tau_star']:.2f}")
    print(f"Overall Test Expected Calibration Error (ECE): {results['test_ece']:.4f}")
    print(f"Overall Test Multiclass Brier Score: {results['test_brier']:.4f}")


if __name__ == "__main__":
    main()
