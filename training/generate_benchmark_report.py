"""
Research Benchmark Report Generator.

Generates results/model_benchmark_report.md synthesizing empirical evaluation,
latency profiling, memory/CPU measurements, feature importances, and trade-off analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def generate_markdown_report(
    metadata: Dict[str, Any],
    comparison_records: List[Dict[str, Any]],
    pareto_models: List[str],
    error_analysis_records: List[Dict[str, Any]],
    feature_importances: Dict[str, List[Dict[str, Any]]],
    output_path: Optional[Path] = None,
) -> str:
    """Renders the comprehensive research benchmark markdown report."""
    dest_file = output_path or Path("results/model_benchmark_report.md")
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Research Benchmark Report: Real-Time Encrypted Traffic Classification",
        "",
        f"**Generated on:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Experiment Seed:** {metadata.get('random_seed', 42)}  ",
        f"**Project Version:** {metadata.get('version', '0.1.0')}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Research Question",
        "",
        "This experiment investigates how accurately encrypted network traffic can be classified using lightweight machine-learning models without inspecting or decrypting packet payloads, while quantifying the trade-offs between classification accuracy, model footprint, and inference latency.",
        "",
        "### Key Findings",
        f"- **Best Overall Accuracy / Macro-F1 Model:** `{metadata.get('best_f1_model', 'N/A')}`",
        f"- **Fastest Inference Model:** `{metadata.get('fastest_model', 'N/A')}`",
        f"- **Most Compact Footprint:** `{metadata.get('smallest_model', 'N/A')}`",
        f"- **Pareto-Efficient Models:** `{', '.join(pareto_models)}`",
        "",
        "---",
        "",
        "## 2. Experimental Setup & Dataset Summary",
        "",
        f"- **Total Training Samples:** {metadata.get('train_samples', 0)}",
        f"- **Total Validation Samples:** {metadata.get('val_samples', 0)}",
        f"- **Total Held-out Test Samples:** {metadata.get('test_samples', 0)}",
        f"- **Input Feature Dimensions:** {metadata.get('feature_count', 0)}",
        f"- **Target Classes ({metadata.get('class_count', 0)}):** `{', '.join(metadata.get('classes', []))}`",
        "- **Feature Engineering Strategy:** Pure zero-payload statistical distributions (packet timing, packet size, burst metrics, flow symmetry, port/protocol headers, TLS metadata).",
        "- **Data Leakage Safeguard:** Group-aware splitting on source PCAP (`file_id`) to ensure distinct sessions do not leak between train and test.",
        "",
        "---",
        "",
        "## 3. Master Empirical Model Comparison",
        "",
        "| Model | Accuracy | Macro F1 | Weighted F1 | Latency (ms) | Batch (ms/pkt) | Size (MB) | Train Time (s) | RAM (MB) | CPU % |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in comparison_records:
        lines.append(
            f"| **{r['model']}** | {r['accuracy']:.4f} | {r['f1_macro']:.4f} | {r['f1_weighted']:.4f} | "
            f"{r['avg_inference_ms']:.4f} | {r.get('batch_inference_ms_per_flow', 0.0):.4f} | {r['model_size_mb']:.4f} | "
            f"{r['training_time_seconds']:.4f} | {r.get('memory_mb', 0.0):.1f} | {r.get('cpu_percent', 0.0):.1f}% |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Multi-Criteria Trade-Off & Pareto Frontier Analysis",
        "",
        "In production edge networks and line-rate classification appliances, raw accuracy alone is insufficient. Models must balance latency constraints and memory consumption.",
        "",
        f"- **Non-Dominated (Pareto-Optimal) Models:** `{', '.join(pareto_models)}`",
        "- These models form the empirical efficiency frontier where no alternative is simultaneously higher in Macro-F1, faster in latency, and smaller in storage size.",
        "",
        "---",
        "",
        "## 5. Top Discriminative Features (Feature Importance)",
        "",
    ])

    for model_name, feats in feature_importances.items():
        top_5 = feats[:5]
        top_str = ", ".join([f"`{f['feature_name']}` ({f['importance']:.4f})" for f in top_5])
        lines.append(f"- **{model_name}:** {top_str}")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Error Analysis & Class Ambiguities",
        "",
        "| Model | Total Errors | Error Rate | Top Confused Class Pairs | Low-Confidence Predictions |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])

    for err in error_analysis_records:
        lines.append(
            f"| **{err['model']}** | {err['total_misclassifications']} | {err['error_rate']:.4f} | "
            f"{err['top_confused_pairs']} | {err['low_confidence_predictions']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 7. Threats to Validity & Limitations",
        "1. **Synthetic vs Real Traffic Variability:** Initial baselines were benchmarked against sample captures; real-world environments introduce jitter, TCP packet loss, and dynamic MTUs.",
        "2. **Zero-Day TLS Padding / ESNI:** Advanced encrypted traffic utilizing uniform packet padding (e.g. Tor or padded TLS 1.3) reduces the discriminative power of packet length statistics.",
        "3. **Inference Benchmarking Overhead:** Single-flow micro-benchmarks are subject to OS thread scheduling variances; warmups and repetition averaging are utilized to mitigate measurement noise.",
        "",
        "---",
        "",
        "## 8. Reproducibility Statement",
        "All data transformations, feature scalers, model weights, and split partitions are version-controlled and deterministically reproducible via:",
        "```bash",
        "python -m training.ml_pipeline",
        "```",
    ])

    content = "\n".join(lines)
    with open(dest_file, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Saved complete research benchmark report to %s", dest_file)
    return content
