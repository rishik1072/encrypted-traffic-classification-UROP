"""
Multi-Criteria Model Comparison Visualization Module.

Generates bar charts and trade-off scatter plots (Accuracy vs Latency, F1 vs Model Size)
saved to results/figures/model_comparison/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def generate_comparison_plots(
    comparison_records: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    """Generates comparison bar charts and Pareto trade-off scatter plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        output_dir.mkdir(parents=True, exist_ok=True)
        models = [r["model"] for r in comparison_records]
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

        # 1. Accuracy Comparison
        plt.figure(figsize=(7, 4))
        plt.bar(models, [r["accuracy"] for r in comparison_records], color=colors, alpha=0.85, edgecolor="black")
        plt.title("Test Accuracy by Model", fontweight="bold")
        plt.ylabel("Accuracy")
        plt.ylim(0, 1.05)
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "accuracy_comparison.png", dpi=150)
        plt.close()

        # 2. Macro F1 Comparison
        plt.figure(figsize=(7, 4))
        plt.bar(models, [r["f1_macro"] for r in comparison_records], color=colors, alpha=0.85, edgecolor="black")
        plt.title("Test Macro F1-Score by Model", fontweight="bold")
        plt.ylabel("Macro F1")
        plt.ylim(0, 1.05)
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "f1_comparison.png", dpi=150)
        plt.close()

        # 3. Inference Latency Comparison
        plt.figure(figsize=(7, 4))
        plt.bar(models, [r["avg_inference_ms"] for r in comparison_records], color=colors, alpha=0.85, edgecolor="black")
        plt.title("Single-Flow Inference Latency (ms)", fontweight="bold")
        plt.ylabel("Latency (ms / flow)")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "inference_latency_comparison.png", dpi=150)
        plt.close()

        # 4. Model Size Comparison
        plt.figure(figsize=(7, 4))
        plt.bar(models, [r["model_size_mb"] for r in comparison_records], color=colors, alpha=0.85, edgecolor="black")
        plt.title("Serialized Model Artifact Size (MB)", fontweight="bold")
        plt.ylabel("Size (MB)")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "model_size_comparison.png", dpi=150)
        plt.close()

        # 5. Training Time Comparison
        plt.figure(figsize=(7, 4))
        plt.bar(models, [r["training_time_seconds"] for r in comparison_records], color=colors, alpha=0.85, edgecolor="black")
        plt.title("Model Training Duration (Seconds)", fontweight="bold")
        plt.ylabel("Time (s)")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "training_time_comparison.png", dpi=150)
        plt.close()

        # 6. Trade-off Scatter: Accuracy vs Inference Latency
        plt.figure(figsize=(7.5, 5))
        for r, c in zip(comparison_records, colors):
            plt.scatter(r["avg_inference_ms"], r["accuracy"], s=180, color=c, edgecolors="black", label=r["model"], alpha=0.9)
            plt.text(r["avg_inference_ms"], r["accuracy"] + 0.02, r["model"], fontsize=9, fontweight="bold", ha="center")
        plt.title("Trade-off: Accuracy vs. Inference Latency", fontweight="bold")
        plt.xlabel("Inference Latency (ms / flow) [Lower is Better]")
        plt.ylabel("Test Accuracy [Higher is Better]")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "accuracy_vs_inference_latency.png", dpi=150)
        plt.close()

        # 7. Trade-off Scatter: Macro F1 vs Model Size
        plt.figure(figsize=(7.5, 5))
        for r, c in zip(comparison_records, colors):
            plt.scatter(r["model_size_mb"], r["f1_macro"], s=180, color=c, edgecolors="black", label=r["model"], alpha=0.9)
            plt.text(r["model_size_mb"], r["f1_macro"] + 0.02, r["model"], fontsize=9, fontweight="bold", ha="center")
        plt.title("Trade-off: Macro F1 vs. Model Size", fontweight="bold")
        plt.xlabel("Model Size (MB) [Lower is Better]")
        plt.ylabel("Test Macro F1 [Higher is Better]")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.savefig(output_dir / "f1_vs_model_size.png", dpi=150)
        plt.close()

        logger.info("Saved comparison visualizations to %s", output_dir)
    except ImportError:
        logger.info("Matplotlib not available. Visual comparison charts skipped.")
