"""
Early Encrypted-Traffic Classification Study (EXP-R12).

Research Question:
"How early can the system make a useful prediction using only the first portion of an encrypted flow?"

Evaluates observation points:
- 3 packets
- 5 packets
- 10 packets
- 20 packets
- 30 packets
- 50 packets
- full flow

Strictly respects flow packet boundaries: incomplete flows are NOT forced into invalid calculations.
Computes true end-to-end latency: Observation Delay + Extraction Delay + Inference Delay.
Calibrates decision confidence thresholds on group-aware validation data prior to locked test evaluation.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import logging
import math
import os
from pathlib import Path
import random
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
    precision_recall_fscore_support,
)

from flows.flow_generator import Direction, Flow, FlowKey
from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.feature_extractor import FeatureExtractor
from preprocessing.preprocessing import FeaturePreprocessor
from training.dataset_registry import DatasetOrigin, DatasetRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_early_prediction")

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

OBSERVATION_POINTS: List[Union[int, str]] = [3, 5, 10, 20, 30, 50, "full"]


def get_git_revision(project_root: Path) -> str:
    """Discovers git commit SHA if available."""
    head_file = project_root / ".git" / "HEAD"
    if head_file.exists():
        try:
            head_content = head_file.read_text(encoding="utf-8").strip()
            if head_content.startswith("ref:"):
                ref_path = head_content.split(" ", 1)[1]
                ref_file = project_root / ".git" / ref_path
                if ref_file.exists():
                    return ref_file.read_text(encoding="utf-8").strip()[:10]
            return head_content[:10]
        except Exception:
            return "unknown"
    return "unknown"


class EarlyPredictionStudy:
    """Orchestrates the empirical early traffic prediction study."""

    def __init__(
        self,
        flows_path: Optional[str] = None,
        splits_dir: Optional[str] = None,
        model_name: str = "random_forest",
        seed: int = 42,
        output_dir: Optional[str] = None,
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.flows_path = (
            Path(flows_path)
            if flows_path
            else self.project_root / "data" / "processed" / "flows" / "flows_real_clean.csv"
        )
        self.splits_dir = (
            Path(splits_dir)
            if splits_dir
            else self.project_root / "data" / "processed" / "splits" / "real_clean"
        )
        self.model_name = model_name
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "results"
        self.tables_dir = self.output_dir / "tables"
        self.figures_dir = self.output_dir / "figures"

        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.git_rev = get_git_revision(self.project_root)
        self.extractor = FeatureExtractor()

    def load_flows_and_splits(
        self,
    ) -> Tuple[
        pd.DataFrame,
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """Loads clean flows and partitions them with group-aware session isolation."""
        if not self.flows_path.exists():
            raise FileNotFoundError(f"Flows file not found at: {self.flows_path}")

        df_flows = pd.read_csv(self.flows_path)
        logger.info("Loaded %d flows from %s", len(df_flows), self.flows_path)

        train_path = self.splits_dir / "train.csv"
        val_path = self.splits_dir / "validation.csv"
        test_path = self.splits_dir / "test.csv"

        if train_path.exists() and val_path.exists() and test_path.exists():
            logger.info("Using pre-existing group-aware splits from %s", self.splits_dir)
            tr_df = pd.read_csv(train_path)
            val_df = pd.read_csv(val_path)
            te_df = pd.read_csv(test_path)

            tr_ids = set(tr_df["flow_id"])
            val_ids = set(val_df["flow_id"])
            te_ids = set(te_df["flow_id"])

            tr_flows = df_flows[df_flows["flow_id"].isin(tr_ids)].to_dict("records")
            val_flows = df_flows[df_flows["flow_id"].isin(val_ids)].to_dict("records")
            te_flows = df_flows[df_flows["flow_id"].isin(te_ids)].to_dict("records")
        else:
            logger.info("Generating group-aware session stratified splits (70/15/15)...")
            tr_flows, val_flows, te_flows = self._split_group_aware(df_flows)

        # Invariant checks
        tr_sess = {r["session_id"] for r in tr_flows}
        val_sess = {r["session_id"] for r in val_flows}
        te_sess = {r["session_id"] for r in te_flows}

        assert len(tr_sess & val_sess) == 0, "Leakage: train & val share session!"
        assert len(tr_sess & te_sess) == 0, "Leakage: train & test share session!"
        assert len(val_sess & te_sess) == 0, "Leakage: val & test share session!"

        logger.info(
            "Split counts -> Train: %d flows (%d sessions), Val: %d flows (%d sessions), Test: %d flows (%d sessions)",
            len(tr_flows),
            len(tr_sess),
            len(val_flows),
            len(val_sess),
            len(te_flows),
            len(te_sess),
        )
        return df_flows, tr_flows, val_flows, te_flows

    def _split_group_aware(
        self, df_flows: pd.DataFrame
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Creates session-stratified splits without data leakage."""
        class_sessions: Dict[str, List[str]] = defaultdict(list)
        records = df_flows.to_dict("records")
        for r in records:
            s_id = r["session_id"]
            cls = r["traffic_class"]
            if s_id not in class_sessions[cls]:
                class_sessions[cls].append(s_id)

        rng = random.Random(self.seed)
        tr_sessions: Set[str] = set()
        val_sessions: Set[str] = set()
        te_sessions: Set[str] = set()

        for cls, s_list in sorted(class_sessions.items()):
            shuffled = list(s_list)
            rng.shuffle(shuffled)
            n_tot = len(shuffled)
            n_val = max(1, int(round(n_tot * 0.16)))
            n_te = max(1, int(round(n_tot * 0.16)))
            n_tr = n_tot - n_val - n_te
            tr_sessions.update(shuffled[:n_tr])
            val_sessions.update(shuffled[n_tr : n_tr + n_val])
            te_sessions.update(shuffled[n_tr + n_val :])

        tr = [r for r in records if r["session_id"] in tr_sessions]
        val = [r for r in records if r["session_id"] in val_sessions]
        te = [r for r in records if r["session_id"] in te_sessions]
        return tr, val, te

    def extract_prefix_features(
        self,
        flow_records: List[Dict[str, Any]],
        horizon: Union[int, str],
    ) -> Tuple[List[Dict[str, Any]], List[str], List[float], List[float]]:
        """
        Extracts zero-payload features for the given observation point.
        Returns:
            - feature_records: extracted feature dicts for flows that satisfy the horizon.
            - labels: ground truth traffic class labels.
            - obs_delays_ms: observation delay in milliseconds (t_N - t_0).
            - extract_delays_ms: time taken to extract features in milliseconds.
        Flows with fewer packets than the horizon are strictly excluded (no forced/invalid padding).
        """
        feats_list: List[Dict[str, Any]] = []
        labels: List[str] = []
        obs_delays_ms: List[float] = []
        extract_delays_ms: List[float] = []

        is_full = horizon == "full"

        for row in flow_records:
            ts_str = row.get("packet_timestamps_json")
            lens_str = row.get("packet_lengths_json")
            dirs_str = row.get("packet_directions_json")

            if not ts_str or not lens_str or not dirs_str or pd.isna(ts_str):
                continue

            timestamps: List[float] = json.loads(ts_str)
            lengths: List[int] = json.loads(lens_str)
            raw_dirs: List[str] = json.loads(dirs_str)
            directions: List[Direction] = [
                Direction.FORWARD if d == "FORWARD" else Direction.BACKWARD for d in raw_dirs
            ]

            total_pkts = len(lengths)
            limit = total_pkts if is_full else int(horizon)

            # Strictly verify the flow has enough packets to reach this observation point
            if total_pkts < limit:
                continue

            sub_ts = timestamps[:limit]
            sub_lens = lengths[:limit]
            sub_dirs = directions[:limit]

            # Observation delay in ms: physical time required for first N packets to arrive
            obs_delay_s = max(0.0001, sub_ts[-1] - sub_ts[0]) if len(sub_ts) > 1 else 0.0001
            obs_delay_ms = obs_delay_s * 1000.0

            # Construct partial Flow object
            flow_obj = Flow(
                key=FlowKey(
                    ip_a="10.0.0.1",
                    port_a=int(row.get("initiator_port", 443)),
                    ip_b="10.0.0.2",
                    port_b=int(row.get("port_b", 443)),
                    protocol=str(row.get("protocol", "TCP")),
                ),
                initiator_ip="10.0.0.1",
                initiator_port=int(row.get("initiator_port", 443)),
                start_time=sub_ts[0],
                last_seen=sub_ts[-1],
            )
            for i in range(limit):
                flow_obj.packet_records.append((sub_ts[i], sub_lens[i], sub_dirs[i]))

            # Measure feature extraction delay
            t_ext0 = time.perf_counter()
            features = self.extractor.extract_features(flow_obj)
            t_ext1 = time.perf_counter()
            ext_delay_ms = (t_ext1 - t_ext0) * 1000.0

            features["traffic_class"] = row["traffic_class"]
            features["flow_id"] = row["flow_id"]

            feats_list.append(features)
            labels.append(row["traffic_class"])
            obs_delays_ms.append(obs_delay_ms)
            extract_delays_ms.append(ext_delay_ms)

        return feats_list, labels, obs_delays_ms, extract_delays_ms

    def _create_model(self) -> Any:
        """Instantiates configured classifier."""
        if self.model_name == "random_forest":
            return RandomForestTrafficClassifier(
                params={"n_estimators": 100, "max_depth": 10, "random_state": self.seed}
            )
        elif self.model_name == "lightgbm":
            return LightGBMTrafficClassifier(
                params={
                    "n_estimators": 80,
                    "num_leaves": 15,
                    "learning_rate": 0.05,
                    "random_state": self.seed,
                    "verbose": -1,
                }
            )
        elif self.model_name == "decision_tree":
            return DecisionTreeTrafficClassifier(
                params={"max_depth": 8, "random_state": self.seed}
            )
        elif self.model_name == "logistic_regression":
            return LogisticRegressionClassifier(
                params={"max_iter": 1000, "random_state": self.seed}
            )
        else:
            raise ValueError(f"Unknown model name: {self.model_name}")

    def calibrate_threshold_on_val(
        self,
        clf: Any,
        prep: FeaturePreprocessor,
        val_records: List[Dict[str, Any]],
        val_labels: List[str],
        candidate_thresholds: Optional[List[float]] = None,
        min_coverage_pct: float = 0.50,
    ) -> Tuple[float, float, float]:
        """
        Sweeps confidence thresholds tau on the validation set.
        Selects tau* that maximizes validation Macro-F1 subject to maintaining min_coverage_pct.
        Returns (best_tau, best_val_f1, val_coverage).
        """
        if not val_records:
            return 0.0, 0.0, 0.0

        if candidate_thresholds is None:
            candidate_thresholds = [0.0, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]

        x_val = prep.transform(val_records)
        y_val_enc = prep.encode_labels(val_records, target_col="traffic_class")

        val_proba = clf.predict_proba(x_val)
        val_confs = np.max(val_proba, axis=1)
        val_preds_enc = np.argmax(val_proba, axis=1)

        best_tau = 0.0
        best_f1 = -1.0
        best_cov = 1.0

        n_val = len(val_records)
        for tau in candidate_thresholds:
            mask = val_confs >= tau
            cov = float(np.sum(mask)) / float(n_val)

            if cov < min_coverage_pct or np.sum(mask) == 0:
                continue

            sub_y = np.array(y_val_enc)[mask]
            sub_pred = val_preds_enc[mask]

            p, r, f1, _ = precision_recall_fscore_support(
                sub_y, sub_pred, average="macro", zero_division=0
            )

            if f1 > best_f1:
                best_f1 = f1
                best_tau = tau
                best_cov = cov

        logger.info(
            "Validation threshold tuning -> selected tau*=%.2f (Val F1=%.4f, Coverage=%.1f%%)",
            best_tau,
            best_f1 if best_f1 >= 0 else 0.0,
            best_cov * 100.0,
        )
        return best_tau, max(0.0, best_f1), best_cov

    def run_study(self) -> pd.DataFrame:
        """Executes the full early classification experiment across all observation points."""
        logger.info("=== Starting Early Encrypted-Traffic Classification Study (EXP-R12) ===")
        df_flows, tr_flows, val_flows, te_flows = self.load_flows_and_splits()

        total_test_flows = len(te_flows)
        results: List[Dict[str, Any]] = []

        for horizon in OBSERVATION_POINTS:
            obs_name = f"{horizon} packets" if horizon != "full" else "full flow"
            is_full = horizon == "full"
            logger.info("--- Evaluating Observation Point: %s ---", obs_name)

            # 1. Extract prefix features on Train, Val, Test
            tr_feats, tr_y, tr_obs_d, tr_ext_d = self.extract_prefix_features(tr_flows, horizon)
            val_feats, val_y, val_obs_d, val_ext_d = self.extract_prefix_features(val_flows, horizon)
            te_feats, te_y, te_obs_d, te_ext_d = self.extract_prefix_features(te_flows, horizon)

            if not tr_feats or not te_feats:
                logger.warning("Insufficient flow data for horizon: %s. Skipping.", obs_name)
                continue

            # 2. Fit preprocessor on training prefix data ONLY
            prep = FeaturePreprocessor(
                {
                    "features": {
                        "numerical_features": CANONICAL_21_FEATURES,
                        "categorical_features": [],
                        "tls_features": [],
                    }
                }
            )
            prep.fit(tr_feats, target_col="traffic_class")

            x_tr = prep.transform(tr_feats)
            y_tr_enc = prep.encode_labels(tr_feats, target_col="traffic_class")

            # 3. Train model on prefix training data
            clf = self._create_model()
            clf.fit(x_tr, y_tr_enc, classes=prep.get_classes())

            # 4. Calibrate decision threshold on validation prefix data
            tau_star, val_f1, val_cov = self.calibrate_threshold_on_val(
                clf, prep, val_feats, val_y, min_coverage_pct=0.50
            )

            # 5. Measure test inference latency and predictions
            x_te = prep.transform(te_feats)
            y_te_enc = prep.encode_labels(te_feats, target_col="traffic_class")

            # Warmup inference
            for _ in range(5):
                _ = clf.predict_proba(x_te[:1])

            infer_latencies_ms: List[float] = []
            test_probas = []
            for i in range(len(te_feats)):
                sample = x_te[i : i + 1]
                t_inf0 = time.perf_counter()
                prob = clf.predict_proba(sample)[0]
                t_inf1 = time.perf_counter()
                infer_latencies_ms.append((t_inf1 - t_inf0) * 1000.0)
                test_probas.append(prob)

            test_probas_arr = np.array(test_probas)
            test_confs = np.max(test_probas_arr, axis=1)
            test_preds_enc = np.argmax(test_probas_arr, axis=1)

            # 6. Apply calibrated decision threshold tau*
            threshold_mask = test_confs >= tau_star
            n_covered = int(np.sum(threshold_mask))

            # Coverage is fraction of total test flows that had enough packets AND met threshold
            coverage = float(n_covered) / float(total_test_flows)

            if n_covered > 0:
                covered_y_true = np.array(y_te_enc)[threshold_mask]
                covered_y_pred = test_preds_enc[threshold_mask]
                covered_confs = test_confs[threshold_mask]

                acc = float(accuracy_score(covered_y_true, covered_y_pred))
                bal_acc = float(balanced_accuracy_score(covered_y_true, covered_y_pred))
                prec, rec, f1, _ = precision_recall_fscore_support(
                    covered_y_true, covered_y_pred, average="macro", zero_division=0
                )
                avg_conf = float(np.mean(covered_confs))
            else:
                acc, bal_acc, prec, rec, f1, avg_conf = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            # 7. Total End-to-End Latency = Observation Delay + Extraction Delay + Inference Delay
            total_latencies_ms = [
                te_obs_d[i] + te_ext_d[i] + infer_latencies_ms[i]
                for i in range(len(te_feats))
            ]

            median_tot_lat = float(np.median(total_latencies_ms))
            p95_tot_lat = float(np.percentile(total_latencies_ms, 95))
            median_obs_lat = float(np.median(te_obs_d))
            p95_obs_lat = float(np.percentile(te_obs_d, 95))
            mean_ext_lat = float(np.mean(te_ext_d))
            mean_inf_lat = float(np.mean(infer_latencies_ms))

            row_data = {
                "observation_point": obs_name,
                "packet_horizon": str(horizon),
                "is_full_flow": is_full,
                "coverage": round(coverage, 4),
                "accuracy": round(acc, 4),
                "macro_precision": round(prec, 4),
                "macro_recall": round(rec, 4),
                "macro_f1": round(f1, 4),
                "balanced_accuracy": round(bal_acc, 4),
                "average_confidence": round(avg_conf, 4),
                "median_latency_ms": round(median_tot_lat, 2),
                "p95_latency_ms": round(p95_tot_lat, 2),
                "median_observation_delay_ms": round(median_obs_lat, 2),
                "p95_observation_delay_ms": round(p95_obs_lat, 2),
                "feature_extraction_latency_ms": round(mean_ext_lat, 4),
                "inference_latency_ms": round(mean_inf_lat, 4),
                "decision_threshold": round(tau_star, 2),
                "val_macro_f1": round(val_f1, 4),
                "val_coverage": round(val_cov, 4),
                "total_test_flows": total_test_flows,
                "flows_meeting_horizon": len(te_feats),
                "flows_classified": n_covered,
                "model": self.model_name,
            }
            results.append(row_data)

            logger.info(
                "Horizon %s -> Cov: %.1f%%, F1: %.4f, Acc: %.4f, AvgConf: %.4f, MedianLat: %.2f ms (Obs: %.2f ms, Infer: %.4f ms)",
                obs_name,
                coverage * 100.0,
                f1,
                acc,
                avg_conf,
                median_tot_lat,
                median_obs_lat,
                mean_inf_lat,
            )

        df_results = pd.DataFrame(results)
        csv_path = self.tables_dir / "research_early_prediction.csv"
        df_results.to_csv(csv_path, index=False)
        logger.info("Saved early prediction results table to: %s", csv_path)

        self.generate_figures(df_results)
        return df_results

    def generate_figures(self, df: pd.DataFrame) -> None:
        """Generates 3 required research figures adhering to strict visual guidelines."""
        logger.info("Generating research figures for early prediction study...")
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

        # Separate partial flows from full flow for plotting
        partial_df = df[~df["is_full_flow"]].copy()
        full_row = df[df["is_full_flow"]]
        full_f1 = full_row["macro_f1"].values[0] if len(full_row) > 0 else None
        full_cov = full_row["coverage"].values[0] if len(full_row) > 0 else None
        full_lat = full_row["median_latency_ms"].values[0] if len(full_row) > 0 else None

        x_vals = [int(p) for p in partial_df["packet_horizon"]]

        # -------------------------------------------------------------
        # Figure 1: early_prediction_f1_vs_packets.png
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
        ax.plot(
            x_vals,
            partial_df["macro_f1"],
            marker="o",
            color="#1f77b4",
            linewidth=2.5,
            markersize=8,
            label=f"Early Prediction ({self.model_name})",
        )
        for x, y in zip(x_vals, partial_df["macro_f1"]):
            ax.annotate(
                f"{y:.3f}",
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                fontweight="bold",
                color="#1f77b4",
            )

        if full_f1 is not None:
            ax.axhline(
                full_f1,
                color="#d62728",
                linestyle="--",
                linewidth=2.0,
                label=f"Full Flow Retrospective (F1 = {full_f1:.3f})",
            )

        ax.set_title(
            "Early Encrypted-Traffic Classification Fidelity (Macro-F1 vs Packet Horizon)",
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Observation Point (First N Packets)", fontsize=11, labelpad=8)
        ax.set_ylabel("Macro-F1 Score", fontsize=11, labelpad=8)
        ax.set_xticks(x_vals)
        ax.set_ylim(0.0, 1.0)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="upper right")
        plt.tight_layout()

        f1_path = self.figures_dir / "early_prediction_f1_vs_packets.png"
        fig.savefig(f1_path)
        plt.close(fig)
        logger.info("Saved figure: %s", f1_path)

        # -------------------------------------------------------------
        # Figure 2: early_prediction_coverage_vs_packets.png
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
        ax.plot(
            x_vals,
            partial_df["coverage"] * 100.0,
            marker="s",
            color="#2ca02c",
            linewidth=2.5,
            markersize=8,
            label="Decision Coverage % (Valid Evidence & Threshold)",
        )
        for x, y in zip(x_vals, partial_df["coverage"] * 100.0):
            ax.annotate(
                f"{y:.1f}%",
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                fontweight="bold",
                color="#2ca02c",
            )

        if full_cov is not None:
            ax.axhline(
                full_cov * 100.0,
                color="#7f7f7f",
                linestyle=":",
                linewidth=1.8,
                label=f"Full Flow Coverage ({full_cov * 100.0:.1f}%)",
            )

        ax.set_title(
            "Early Prediction Decision Coverage vs Observation Horizon",
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Observation Point (First N Packets)", fontsize=11, labelpad=8)
        ax.set_ylabel("Decision Coverage (%)", fontsize=11, labelpad=8)
        ax.set_xticks(x_vals)
        ax.set_ylim(0, 105)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="lower right")
        plt.tight_layout()

        cov_path = self.figures_dir / "early_prediction_coverage_vs_packets.png"
        fig.savefig(cov_path)
        plt.close(fig)
        logger.info("Saved figure: %s", cov_path)

        # -------------------------------------------------------------
        # Figure 3: early_prediction_latency_vs_packets.png
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
        obs_delays = partial_df["median_observation_delay_ms"]
        tot_latencies = partial_df["median_latency_ms"]
        p95_latencies = partial_df["p95_latency_ms"]

        ax.plot(
            x_vals,
            tot_latencies,
            marker="^",
            color="#d62728",
            linewidth=2.5,
            markersize=8,
            label="Median Total Latency (Obs + Extract + Infer)",
        )
        ax.plot(
            x_vals,
            p95_latencies,
            marker="v",
            color="#ff7f0e",
            linestyle="--",
            linewidth=2.0,
            markersize=7,
            label="P95 Total Latency",
        )
        ax.plot(
            x_vals,
            obs_delays,
            marker="o",
            color="#9467bd",
            linestyle=":",
            linewidth=1.8,
            markersize=6,
            label="Median Observation Delay (Physical Wire Arrival)",
        )

        for x, y in zip(x_vals, tot_latencies):
            ax.annotate(
                f"{y:.0f} ms",
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#d62728",
            )

        if full_lat is not None:
            ax.annotate(
                f"Full Flow Retrospective Median: {full_lat / 1000.0:.1f} s",
                xy=(x_vals[-1], tot_latencies.iloc[-1]),
                xytext=(x_vals[-2], tot_latencies.iloc[-1] * 1.5),
                arrowprops=dict(arrowstyle="->", color="#333333"),
                fontsize=9,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="#ffffcc", ec="#cccc99"),
            )

        ax.set_title(
            "End-to-End Latency Decomposition Across Packet Horizons\n(Demonstrating Physical Observation Arrival vs Inference Delay)",
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Observation Point (First N Packets)", fontsize=11, labelpad=8)
        ax.set_ylabel("Latency (Milliseconds, Log Scale)", fontsize=11, labelpad=8)
        ax.set_yscale("log")
        ax.set_xticks(x_vals)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, loc="upper left")
        plt.tight_layout()

        lat_path = self.figures_dir / "early_prediction_latency_vs_packets.png"
        fig.savefig(lat_path)
        plt.close(fig)
        logger.info("Saved figure: %s", lat_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run early encrypted-traffic classification study (EXP-R12)."
    )
    parser.add_argument(
        "--flows-path",
        type=str,
        default="data/processed/flows/flows_real_clean.csv",
        help="Path to clean flow data containing packet JSON arrays.",
    )
    parser.add_argument(
        "--splits-dir",
        type=str,
        default="data/processed/splits/real_clean",
        help="Path to session-isolated train/val/test split directory.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="random_forest",
        choices=["random_forest", "lightgbm", "decision_tree", "logistic_regression"],
        help="Classifier to evaluate.",
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
        help="Output directory for tables and figures.",
    )

    args = parser.parse_args()

    study = EarlyPredictionStudy(
        flows_path=args.flows_path,
        splits_dir=args.splits_dir,
        model_name=args.model,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    df_results = study.run_study()
    print("\n=== Final Early Prediction Results ===")
    print(
        df_results[
            [
                "observation_point",
                "coverage",
                "accuracy",
                "macro_f1",
                "balanced_accuracy",
                "average_confidence",
                "median_latency_ms",
                "p95_latency_ms",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
