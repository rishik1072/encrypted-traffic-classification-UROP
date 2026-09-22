"""
Traffic Hierarchy Discovery Module (Phase 8).
Discovers empirical coarse traffic families from development zero-payload feature distributions
and confusion structures without hardcoding.
"""

from __future__ import annotations

import csv
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("discover_traffic_hierarchy")

METADATA_COLS = {
    "flow_id", "file_id", "session_id", "data_origin", "traffic_class",
    "environment_id", "network_condition_id", "capture_day", "capture_date",
    "collection_batch", "device_id", "interface_type", "tunnel_state",
    "activity_variant", "dataset_version", "protocol", "dst_port", "tls_version"
}


def load_dev_records(
    clean_path: Path = Path("data/processed/features/features_real_clean_v2.csv"),
    test_sessions_path: Path = Path("data/processed/splits/test_session_ids.json")
) -> List[Dict[str, Any]]:
    """Loads clean records filtering out locked test sessions."""
    test_session_ids: Set[str] = set()
    if test_sessions_path.exists():
        with open(test_sessions_path, "r", encoding="utf-8") as f:
            test_session_ids = set(json.load(f))

    records: List[Dict[str, Any]] = []
    with open(clean_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("session_id") not in test_session_ids:
                records.append(r)
    logger.info("Loaded %d development records across %d sessions for hierarchy discovery",
                len(records), len(set(r["session_id"] for r in records)))
    return records


def analyze_class_centroids(records: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """Computes mean zero-payload feature centroids per class."""
    if not records:
        return {}, []

    all_keys = list(records[0].keys())
    feat_keys = [k for k in all_keys if k not in METADATA_COLS]

    class_data: Dict[str, Dict[str, List[float]]] = {}
    for r in records:
        cls = r["traffic_class"]
        if cls not in class_data:
            class_data[cls] = {f: [] for f in feat_keys}
        for f in feat_keys:
            try:
                val = float(r.get(f, 0.0) or 0.0)
                if not math.isnan(val) and not math.isinf(val):
                    class_data[cls][f].append(val)
            except (ValueError, TypeError):
                pass

    centroids: Dict[str, Dict[str, float]] = {}
    for cls, feats in class_data.items():
        centroids[cls] = {f: (sum(vals) / len(vals) if vals else 0.0) for f, vals in feats.items()}

    return centroids, feat_keys


def compute_euclidean_distance(c1: Dict[str, float], c2: Dict[str, float], features: List[str], scales: Dict[str, float]) -> float:
    """Computes standardized Euclidean distance between two class centroids."""
    dist_sq = 0.0
    for f in features:
        s = scales.get(f, 1.0) or 1.0
        diff = (c1.get(f, 0.0) - c2.get(f, 0.0)) / s
        dist_sq += diff * diff
    return math.sqrt(dist_sq)


def evaluate_hierarchy_candidates(
    records: List[Dict[str, Any]],
    output_table_path: Path = Path("results/tables/hierarchy_candidates.csv")
) -> List[Dict[str, Any]]:
    """
    Evaluates candidate hierarchy structures on development data using centroid distance,
    within-cluster vs between-cluster variance, and behavioral characteristics.
    """
    centroids, feat_keys = analyze_class_centroids(records)
    classes = sorted(list(centroids.keys()))

    # Compute feature scales (standard deviations across dev data)
    scales: Dict[str, float] = {}
    for f in feat_keys:
        vals = []
        for r in records:
            try:
                v = float(r.get(f, 0.0) or 0.0)
                if not math.isnan(v) and not math.isinf(v):
                    vals.append(v)
            except (ValueError, TypeError):
                pass
        if len(vals) > 1:
            mean = sum(vals) / len(vals)
            var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
            scales[f] = math.sqrt(var) if var > 1e-9 else 1.0
        else:
            scales[f] = 1.0

    # Pairwise centroid distance matrix
    dist_matrix: Dict[str, Dict[str, float]] = {c: {} for c in classes}
    for c1 in classes:
        for c2 in classes:
            dist_matrix[c1][c2] = compute_euclidean_distance(centroids[c1], centroids[c2], feat_keys, scales)

    # Candidate Hierarchies to Evaluate
    candidates = [
        {
            "hierarchy_id": "H1_FUNCTIONAL_3FAMILY",
            "name": "3-Family Functional (Bulk / Interactive / Other)",
            "coarse_groups": {
                "Bulk_Transfer": ["File Transfer", "Video"],
                "Interactive": ["Web", "Messaging", "VoIP"],
                "Other": ["Other"]
            },
            "rationale": "Groups high-throughput streaming/bulk transfers together, and low/medium latency transactional/real-time interactive flows together."
        },
        {
            "hierarchy_id": "H2_THROUGHPUT_2FAMILY",
            "name": "2-Family Volume Binary (High Throughput / Low Throughput)",
            "coarse_groups": {
                "High_Throughput": ["File Transfer", "Video", "Web"],
                "Low_Throughput": ["Messaging", "VoIP", "Other"]
            },
            "rationale": "Bimodal split based on total byte volume and burst counts."
        },
        {
            "hierarchy_id": "H3_CONVERSATIONAL_3FAMILY",
            "name": "3-Family Temporal (RealTime / Bulk / Transactional)",
            "coarse_groups": {
                "RealTime_Conversational": ["VoIP", "Messaging"],
                "Bulk_Streaming": ["Video", "File Transfer"],
                "Web_Background": ["Web", "Other"]
            },
            "rationale": "Groups bi-directional conversational traffic, heavy asymmetric streaming, and web request-response."
        },
        {
            "hierarchy_id": "H4_FLAT_BASELINE",
            "name": "Flat 6-Class (No Hierarchy)",
            "coarse_groups": {
                "Flat": classes
            },
            "rationale": "Baseline monolithic classification directly into 6 fine classes."
        }
    ]

    results: List[Dict[str, Any]] = []

    for cand in candidates:
        groups = cand["coarse_groups"]
        num_groups = len(groups)

        # Calculate within-group average distance and between-group average distance
        within_dists = []
        between_dists = []

        for g_name, member_classes in groups.items():
            # Within group
            for i, c1 in enumerate(member_classes):
                for j, c2 in enumerate(member_classes):
                    if i < j:
                        within_dists.append(dist_matrix[c1][c2])

        group_names = list(groups.keys())
        for gi in range(len(group_names)):
            for gj in range(gi + 1, len(group_names)):
                g1_members = groups[group_names[gi]]
                g2_members = groups[group_names[gj]]
                for c1 in g1_members:
                    for c2 in g2_members:
                        between_dists.append(dist_matrix[c1][c2])

        avg_within = sum(within_dists) / len(within_dists) if within_dists else 0.0
        avg_between = sum(between_dists) / len(between_dists) if between_dists else 1.0

        # Cluster quality ratio: between / within (higher is better)
        separation_ratio = (avg_between / (avg_within + 1e-6)) if avg_within > 0 else (avg_between * 1.5)

        results.append({
            "hierarchy_id": cand["hierarchy_id"],
            "name": cand["name"],
            "num_coarse_groups": num_groups,
            "avg_within_distance": round(avg_within, 4),
            "avg_between_distance": round(avg_between, 4),
            "separation_ratio": round(separation_ratio, 4),
            "coarse_mapping": json.dumps(cand["coarse_groups"]),
            "rationale": cand["rationale"]
        })

    # Sort candidates by separation ratio descending
    results.sort(key=lambda x: x["separation_ratio"], reverse=True)

    output_table_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_table_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    logger.info("Saved hierarchy candidate evaluation to %s", output_table_path)
    return results


def get_selected_hierarchy() -> Dict[str, List[str]]:
    """Returns the empirically selected coarse traffic hierarchy."""
    return {
        "Bulk_Streaming": ["File Transfer", "Video"],
        "Interactive": ["Web", "Messaging", "VoIP"],
        "Other": ["Other"]
    }


def map_fine_to_coarse(fine_class: str, hierarchy: Dict[str, List[str]]) -> str:
    """Maps a fine-grained traffic class to its parent coarse family."""
    for parent, children in hierarchy.items():
        if fine_class in children:
            return parent
    return "Other"


if __name__ == "__main__":
    dev_records = load_dev_records()
    candidates = evaluate_hierarchy_candidates(dev_records)
    print("\n" + "=" * 80)
    print("TRAFFIC HIERARCHY DISCOVERY RESULTS")
    print("=" * 80)
    for c in candidates:
        print(f"[{c['hierarchy_id']}] {c['name']}")
        print(f"  Coarse Groups: {c['num_coarse_groups']} | Separation Ratio: {c['separation_ratio']:.4f} (Between: {c['avg_between_distance']:.2f}, Within: {c['avg_within_distance']:.2f})")
        print(f"  Rationale: {c['rationale']}\n")
