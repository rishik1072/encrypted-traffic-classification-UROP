"""
Research-Grade Generalization Benchmark Runner.

Research Question:
"How robust is zero-payload encrypted traffic classification when the test traffic differs from the training traffic?"

Evaluates 8 comprehensive domain shift and generalization regimes:
1. Random/group baseline (Group-aware session-stratified baseline)
2. Unseen capture split (File holdout)
3. Unseen session split (User session holdout)
4. Temporal split (Train Day 1-3 -> Test Day 4)
5. Unseen environment split (Train Wi-Fi -> Test Ethernet & Cellular)
6. Unseen network condition split (Train NORMAL -> Test Impaired: Loss/Latency/Bandwidth)
7. Unseen activity variant split (Train 24 variants -> Test 6 unseen variants)
8. Tunnel-state shift (Bidirectional: Tunneled WARP vs. Direct Encrypted)

Strictly enforces zero session or capture leakage between train and test splits.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from experiments.research_baseline.run import (
    CANONICAL_21_FEATURES,
    CANONICAL_CLASSES,
    benchmark_inference_latency,
    compute_multiclass_metrics,
)
from preprocessing.preprocessing import FeaturePreprocessor
from training.dataset_registry import DatasetRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_generalization")


class ResearchGeneralizationBenchmark:
    """Orchestrator for the 8 generalization regimes."""

    def __init__(
        self,
        data_path: str = "data/processed/features/features_real_clean_v2.csv",
        seed: int = 42,
        output_dir: str = "results",
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.data_path = self.project_root / data_path
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.tables_dir = self.output_dir / "tables"
        self.figures_dir = self.output_dir / "figures"

        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.registry = DatasetRegistry(self.project_root)
        self.features = list(CANONICAL_21_FEATURES)
        self.classes = list(CANONICAL_CLASSES)

    def load_dataset(self) -> List[Dict[str, Any]]:
        """Loads features and validates real-data provenance."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data not found: {self.data_path}")

        records: List[Dict[str, Any]] = []
        with open(self.data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                records.append(dict(r))

        self.registry.validate_real_data_claim("dataset_v2", records)
        logger.info("Loaded %d records for generalization benchmark", len(records))
        return records

    def _train_and_eval(
        self,
        train_recs: List[Dict[str, Any]],
        val_recs: List[Dict[str, Any]],
        test_recs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fits preprocessor and Random Forest classifier strictly on train; evaluates test."""
        # Preprocessing: strict fit on train only
        prep = FeaturePreprocessor({"features": {"numerical_features": self.features}})
        prep.fit(train_recs, target_col="traffic_class")

        x_tr = prep.transform(train_recs)
        y_tr = prep.encode_labels(train_recs, target_col="traffic_class")
        x_te = prep.transform(test_recs)
        y_te = prep.encode_labels(test_recs, target_col="traffic_class")

        clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=self.seed, n_jobs=-1)
        clf.fit(x_tr, y_tr)

        preds = clf.predict(x_te)
        metrics = compute_multiclass_metrics(y_te, np.array(preds), self.classes)

        lat = benchmark_inference_latency(clf, x_te, warmup_runs=20, benchmark_runs=200)

        return {
            "metrics": metrics,
            "latency": lat,
            "classifier": clf,
        }

    def evaluate_all_regimes(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Executes all 8 generalization evaluation regimes."""
        results: List[Dict[str, Any]] = []

        # =====================================================================
        # Regime 1: Random / Group Baseline (Stratified Session Split)
        # =====================================================================
        logger.info("Evaluating Regime 1: Random/Group Baseline...")
        class_sessions: Dict[str, List[str]] = defaultdict(list)
        session_to_recs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in records:
            s = r["session_id"]
            c = r["traffic_class"]
            session_to_recs[s].append(r)
            if s not in class_sessions[c]:
                class_sessions[c].append(s)

        rng = random.Random(self.seed)
        tr_s, val_s, te_s = set(), set(), set()
        for c, s_list in sorted(class_sessions.items()):
            shuffled = list(s_list)
            rng.shuffle(shuffled)
            n = len(shuffled)
            n_v = max(1, int(round(n * 0.16)))
            n_t = max(1, int(round(n * 0.16)))
            tr_s.update(shuffled[: n - n_v - n_t])
            val_s.update(shuffled[n - n_v - n_t : n - n_t])
            te_s.update(shuffled[n - n_t :])

        tr_recs = [r for s in tr_s for r in session_to_recs[s]]
        val_recs = [r for s in val_s for r in session_to_recs[s]]
        te_recs = [r for s in te_s for r in session_to_recs[s]]
        eval1 = self._train_and_eval(tr_recs, val_recs, te_recs)
        baseline_f1 = eval1["metrics"]["macro_f1"]

        results.append(self._format_row(
            regime_id="REG-01",
            regime_name="1. Random/Group Baseline",
            train_desc="102 sessions (stratified 70%)",
            val_desc="24 sessions (stratified 15%)",
            test_desc="24 sessions (stratified 15%)",
            train_recs=tr_recs,
            val_recs=val_recs,
            test_recs=te_recs,
            eval_res=eval1,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 2: Unseen Capture (File Holdout)
        # =====================================================================
        logger.info("Evaluating Regime 2: Unseen Capture Split...")
        # file_id partition: In dataset_v2, file_id holds distinct capture files
        file_sessions: Dict[str, List[str]] = defaultdict(list)
        for r in records:
            file_sessions[r["file_id"]].append(r)
        
        all_files = sorted(list(file_sessions.keys()))
        rng_files = random.Random(self.seed + 1)
        rng_files.shuffle(all_files)
        n_te_files = int(round(len(all_files) * 0.20))
        te_files = set(all_files[:n_te_files])
        tr_files = set(all_files[n_te_files:])

        tr_recs = [r for f in tr_files for r in file_sessions[f]]
        te_recs = [r for f in te_files for r in file_sessions[f]]
        eval2 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-02",
            regime_name="2. Unseen Capture Split",
            train_desc=f"{len(tr_files)} capture files (80%)",
            val_desc="N/A",
            test_desc=f"{len(te_files)} unseen capture files (20%)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval2,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 3: Unseen Session Split
        # =====================================================================
        logger.info("Evaluating Regime 3: Unseen Session Split...")
        # Pure session holdout without class stratification to test unconstrained session variance
        all_sessions = sorted(list(session_to_recs.keys()))
        rng_sess = random.Random(self.seed + 2)
        rng_sess.shuffle(all_sessions)
        n_te_sess = int(round(len(all_sessions) * 0.20))
        te_s_unconstrained = set(all_sessions[:n_te_sess])
        tr_s_unconstrained = set(all_sessions[n_te_sess:])

        tr_recs = [r for s in tr_s_unconstrained for r in session_to_recs[s]]
        te_recs = [r for s in te_s_unconstrained for r in session_to_recs[s]]
        eval3 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-03",
            regime_name="3. Unseen Session Split",
            train_desc=f"{len(tr_s_unconstrained)} user sessions (80%)",
            val_desc="N/A",
            test_desc=f"{len(te_s_unconstrained)} unconstrained sessions (20%)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval3,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 4: Temporal Split (Temporal Drift)
        # =====================================================================
        logger.info("Evaluating Regime 4: Temporal Split...")
        # Train on days 1, 2, 3 -> Test on day 4
        tr_recs = [r for r in records if r["capture_day"] in {"day_1", "day_2", "day_3"}]
        te_recs = [r for r in records if r["capture_day"] == "day_4"]
        eval4 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-04",
            regime_name="4. Temporal Split",
            train_desc="Past days (day_1, day_2, day_3)",
            val_desc="N/A",
            test_desc="Future day (day_4 chronological drift)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval4,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 5: Unseen Environment (Physical Interface Shift)
        # =====================================================================
        logger.info("Evaluating Regime 5: Unseen Environment...")
        # Train Wi-Fi -> Test Ethernet & Cellular LTE
        tr_recs = [r for r in records if r["environment_id"] == "env_win11_wifi"]
        te_recs = [r for r in records if r["environment_id"] in {"env_win11_eth", "env_win11_cellular"}]
        eval5 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-05",
            regime_name="5. Unseen Environment Split",
            train_desc="Wi-Fi 802.11ax (env_win11_wifi)",
            val_desc="N/A",
            test_desc="Unseen Ethernet + Cellular (env_win11_eth, env_win11_cellular)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval5,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 6: Unseen Network Condition (Impairment Shift)
        # =====================================================================
        logger.info("Evaluating Regime 6: Unseen Network Condition...")
        # Train NORMAL -> Test Impaired (LOW_BANDWIDTH, HIGH_LATENCY, PACKET_LOSS)
        tr_recs = [r for r in records if r["network_condition_id"] == "NORMAL"]
        te_recs = [r for r in records if r["network_condition_id"] != "NORMAL"]
        eval6 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-06",
            regime_name="6. Unseen Network Condition Split",
            train_desc="NORMAL baseline network condition",
            val_desc="N/A",
            test_desc="Impaired conditions (LOW_BANDWIDTH, HIGH_LATENCY, PACKET_LOSS)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval6,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 7: Unseen Activity Variant (Sub-Application Shift)
        # =====================================================================
        logger.info("Evaluating Regime 7: Unseen Activity Variant...")
        # 1 unseen variant per class
        unseen_variants = {
            "ft_sftp_sync",
            "msg_whatsapp_web",
            "oth_telemetry_heartbeat",
            "vid_youtube_1080p",
            "voip_zoom_audio",
            "web_wikipedia",
        }
        tr_recs = [r for r in records if r["activity_variant"] not in unseen_variants]
        te_recs = [r for r in records if r["activity_variant"] in unseen_variants]
        eval7 = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-07",
            regime_name="7. Unseen Activity Variant Split",
            train_desc="24 known activity variants (4 per class)",
            val_desc="N/A",
            test_desc="6 unseen activity variants (1 per class)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval7,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 8a: Tunnel-State Shift (Tunneled WARP -> Direct Encrypted)
        # =====================================================================
        logger.info("Evaluating Regime 8a: Tunnel Shift (Tunneled -> Direct)...")
        tr_recs = [r for r in records if r["tunnel_state"] == "warp_enabled"]
        te_recs = [r for r in records if r["tunnel_state"] == "warp_disabled"]
        eval8a = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-08a",
            regime_name="8a. Tunnel Shift (Tunneled -> Direct)",
            train_desc="Cloudflare WARP / WireGuard Tunneled (warp_enabled)",
            val_desc="N/A",
            test_desc="Direct Encrypted Traffic (warp_disabled)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval8a,
            baseline_f1=baseline_f1,
        ))

        # =====================================================================
        # Regime 8b: Tunnel-State Shift (Direct Encrypted -> Tunneled WARP)
        # =====================================================================
        logger.info("Evaluating Regime 8b: Tunnel Shift (Direct -> Tunneled)...")
        tr_recs = [r for r in records if r["tunnel_state"] == "warp_disabled"]
        te_recs = [r for r in records if r["tunnel_state"] == "warp_enabled"]
        eval8b = self._train_and_eval(tr_recs, [], te_recs)

        results.append(self._format_row(
            regime_id="REG-08b",
            regime_name="8b. Tunnel Shift (Direct -> Tunneled)",
            train_desc="Direct Encrypted Traffic (warp_disabled)",
            val_desc="N/A",
            test_desc="Cloudflare WARP / WireGuard Tunneled (warp_enabled)",
            train_recs=tr_recs,
            val_recs=[],
            test_recs=te_recs,
            eval_res=eval8b,
            baseline_f1=baseline_f1,
        ))

        return results

    def _format_row(
        self,
        regime_id: str,
        regime_name: str,
        train_desc: str,
        val_desc: str,
        test_desc: str,
        train_recs: List[Dict[str, Any]],
        val_recs: List[Dict[str, Any]],
        test_recs: List[Dict[str, Any]],
        eval_res: Dict[str, Any],
        baseline_f1: float,
    ) -> Dict[str, Any]:
        """Formats an evaluation regime result row with full metadata and leakage proofs."""
        tr_sessions = {r["session_id"] for r in train_recs}
        te_sessions = {r["session_id"] for r in test_recs}
        tr_captures = {r["file_id"] for r in train_recs}
        te_captures = {r["file_id"] for r in test_recs}

        # Assert zero leakage
        session_overlap = len(tr_sessions & te_sessions)
        capture_overlap = len(tr_captures & te_captures)
        assert session_overlap == 0, f"Leakage: {session_overlap} sessions overlap in {regime_name}!"
        assert capture_overlap == 0, f"Leakage: {capture_overlap} captures overlap in {regime_name}!"

        m = eval_res["metrics"]
        lat = eval_res["latency"]
        f1 = m["macro_f1"]
        diff_f1 = round(f1 - baseline_f1, 4)

        if diff_f1 >= -0.05:
            robustness = "ROBUST"
        elif diff_f1 >= -0.20:
            robustness = "MODERATE_DEGRADATION"
        else:
            robustness = "SEVERE_DEGRADATION"

        te_class_dist = dict(Counter([r["traffic_class"] for r in test_recs]))

        return {
            "regime_id": regime_id,
            "regime_name": regime_name,
            "dataset_version": "2.0.0",
            "train_groups": train_desc,
            "validation_groups": val_desc,
            "test_groups": test_desc,
            "class_distribution": json.dumps(te_class_dist, sort_keys=True),
            "sample_count": len(train_recs) + len(val_recs) + len(test_recs),
            "train_count": len(train_recs),
            "test_count": len(test_recs),
            "capture_count": len(tr_captures | te_captures),
            "session_count": len(tr_sessions | te_sessions),
            "accuracy": m["accuracy"],
            "macro_precision": m["macro_precision"],
            "macro_recall": m["macro_recall"],
            "macro_f1": m["macro_f1"],
            "weighted_f1": m["weighted_f1"],
            "balanced_accuracy": m["balanced_accuracy"],
            "latency": lat["mean_ms"],
            "f1_delta_vs_baseline": diff_f1,
            "robustness_rating": robustness,
        }

    def save_scorecard(self, results: List[Dict[str, Any]]) -> None:
        """Saves scorecard to results/tables/research_generalization_scorecard.csv."""
        scorecard_path = self.tables_dir / "research_generalization_scorecard.csv"
        fieldnames = list(results[0].keys())

        with open(scorecard_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        logger.info("Saved generalization scorecard to %s", scorecard_path)

    def render_plots(self, results: List[Dict[str, Any]], records: List[Dict[str, Any]]) -> None:
        """Generates the 5 required generalization research figures."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # -------------------------------------------------------------
        # Figure 1: generalization_comparison.png
        # -------------------------------------------------------------
        names = [r["regime_id"] for r in results]
        f1s = [r["macro_f1"] for r in results]
        accs = [r["accuracy"] for r in results]
        x = np.arange(len(names))
        width = 0.38

        plt.figure(figsize=(11, 6))
        plt.bar(x - width / 2, f1s, width, label="Macro F1-Score", color="#2b5c8f", alpha=0.85)
        plt.bar(x + width / 2, accs, width, label="Accuracy", color="#e27c38", alpha=0.85)
        plt.axhline(results[0]["macro_f1"], color="red", linestyle="--", alpha=0.7, label=f"Baseline F1 ({results[0]['macro_f1']:.3f})")
        plt.xticks(x, [r["regime_name"].split(" ")[0] for r in results], rotation=30, ha="right", fontsize=9)
        plt.ylabel("Performance Score", fontsize=11, fontweight="bold")
        plt.title("Encrypted Traffic Generalization Scorecard Across 8 Domain Shifts\n(dataset_v2, Zero Session Leakage)", fontsize=12, fontweight="bold")
        plt.legend(loc="upper right", fontsize=9)
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        plt.tight_layout()
        p1 = self.figures_dir / "generalization_comparison.png"
        plt.savefig(p1, dpi=300)
        plt.close()
        logger.info("Saved: %s", p1)

        # -------------------------------------------------------------
        # Figure 2: temporal_drift.png
        # -------------------------------------------------------------
        # Show flow volume and class stability across days
        days = ["day_1", "day_2", "day_3", "day_4"]
        day_counts = [sum(1 for r in records if r["capture_day"] == d) for d in days]
        r4 = next(r for r in results if r["regime_id"] == "REG-04")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
        ax1.bar(days, day_counts, color="#4582ec", alpha=0.85, edgecolor="#2b5c8f")
        ax1.set_ylabel("Flow Count", fontsize=10, fontweight="bold")
        ax1.set_title("(a) Chronological Sample Distribution", fontsize=11, fontweight="bold")
        ax1.grid(axis="y", linestyle="--", alpha=0.5)

        # Performance shift
        ax2.bar(["Group Baseline", "Temporal Shift (Day 4)"], [results[0]["macro_f1"], r4["macro_f1"]], color=["#38761d", "#d9534f"], width=0.45)
        ax2.set_ylabel("Macro F1-Score", fontsize=10, fontweight="bold")
        ax2.set_title(f"(b) Temporal Generalization Degradation\n(F1: {r4['macro_f1']:.4f} vs {results[0]['macro_f1']:.4f})", fontsize=11, fontweight="bold")
        ax2.grid(axis="y", linestyle="--", alpha=0.5)

        plt.suptitle("Temporal Drift Analysis: Day 1-3 Training -> Day 4 Unseen Testing", fontsize=12, fontweight="bold", y=0.98)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        p2 = self.figures_dir / "temporal_drift.png"
        plt.savefig(p2, dpi=300)
        plt.close()
        logger.info("Saved: %s", p2)

        # -------------------------------------------------------------
        # Figure 3: environment_shift.png
        # -------------------------------------------------------------
        # Compare Wi-Fi training performance on Wi-Fi test vs Ethernet & Cellular
        r5 = next(r for r in results if r["regime_id"] == "REG-05")
        plt.figure(figsize=(7, 5))
        bars = plt.bar(
            ["Baseline (Wi-Fi In-Domain)", "Unseen Environments (Eth + Cell)"],
            [results[0]["macro_f1"], r5["macro_f1"]],
            color=["#2b5c8f", "#d9534f"],
            width=0.45,
            edgecolor="black",
        )
        plt.ylabel("Macro F1-Score", fontsize=11, fontweight="bold")
        plt.title("Spatial / Physical Interface Shift\n(Wi-Fi 802.11ax -> Ethernet & Cellular LTE)", fontsize=12, fontweight="bold")
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        for b in bars:
            h = b.get_height()
            plt.annotate(f"{h:.4f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", fontweight="bold")
        plt.tight_layout()
        p3 = self.figures_dir / "environment_shift.png"
        plt.savefig(p3, dpi=300)
        plt.close()
        logger.info("Saved: %s", p3)

        # -------------------------------------------------------------
        # Figure 4: tunnel_shift.png
        # -------------------------------------------------------------
        # Compare 8a and 8b: Tunneled vs Direct
        r8a = next(r for r in results if r["regime_id"] == "REG-08a")
        r8b = next(r for r in results if r["regime_id"] == "REG-08b")
        plt.figure(figsize=(8, 5))
        t_labels = ["Baseline (In-Domain)", "Tunneled -> Direct", "Direct -> Tunneled"]
        t_f1s = [results[0]["macro_f1"], r8a["macro_f1"], r8b["macro_f1"]]
        t_colors = ["#2b5c8f", "#f0ad4e", "#d9534f"]

        bars = plt.bar(t_labels, t_f1s, color=t_colors, width=0.45, edgecolor="black")
        plt.ylabel("Macro F1-Score", fontsize=11, fontweight="bold")
        plt.title("Tunnel Encapsulation Shift:\nCloudflare WARP/WireGuard vs. Direct Encrypted Traffic", fontsize=12, fontweight="bold")
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        for b in bars:
            h = b.get_height()
            plt.annotate(f"{h:.4f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", fontweight="bold")
        plt.tight_layout()
        p4 = self.figures_dir / "tunnel_shift.png"
        plt.savefig(p4, dpi=300)
        plt.close()
        logger.info("Saved: %s", p4)

        # -------------------------------------------------------------
        # Figure 5: activity_variant_shift.png
        # -------------------------------------------------------------
        r7 = next(r for r in results if r["regime_id"] == "REG-07")
        plt.figure(figsize=(7, 5))
        bars = plt.bar(
            ["Baseline (Known Variants)", "Unseen Activity Variants"],
            [results[0]["macro_f1"], r7["macro_f1"]],
            color=["#38761d", "#8f3985"],
            width=0.45,
            edgecolor="black",
        )
        plt.ylabel("Macro F1-Score", fontsize=11, fontweight="bold")
        plt.title("Sub-Application Generalization:\nKnown Activity Variants vs. 6 Unseen Variants", fontsize=12, fontweight="bold")
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        for b in bars:
            h = b.get_height()
            plt.annotate(f"{h:.4f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", fontweight="bold")
        plt.tight_layout()
        p5 = self.figures_dir / "activity_variant_shift.png"
        plt.savefig(p5, dpi=300)
        plt.close()
        logger.info("Saved: %s", p5)

    def run(self) -> None:
        """Executes the full generalization evaluation suite."""
        logger.info("Starting Research Generalization Benchmark...")
        records = self.load_dataset()
        results = self.evaluate_all_regimes(records)
        self.save_scorecard(results)
        self.render_plots(results, records)
        logger.info("Generalization benchmark complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run research generalization benchmark.")
    parser.add_argument("--data", type=str, default="data/processed/features/features_real_clean_v2.csv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="results")
    args = parser.parse_args()

    bench = ResearchGeneralizationBenchmark(data_path=args.data, seed=args.seed, output_dir=args.output_dir)
    bench.run()


if __name__ == "__main__":
    main()
