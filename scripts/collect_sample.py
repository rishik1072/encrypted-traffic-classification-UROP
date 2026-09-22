"""
Sample Traffic Collection & Pipeline Ingestion Verification.

Validates the full end-to-end collection chain:
Capture -> Zero-Payload Metadata Export -> Validation -> Manifest Registration -> Flow Generation -> Feature Extraction.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.collection_runner import CollectionRunner
from capture.session_manager import CollectionSession
from training.ingest_collected_metadata import ingest_metadata_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("collect_sample")


def main():
    print("\n=======================================================")
    print("    SAMPLE REAL TRAFFIC COLLECTION & INGESTION TEST    ")
    print("=======================================================\n")

    # 1. Run sample Web capture
    session = CollectionSession.create(traffic_class="Web", seq_num=999, notes="Sample end-to-end verification")
    runner = CollectionRunner()
    res = runner.run_session(session=session, duration_seconds=5, warmup_seconds=1)

    print(f"[*] Capture Phase Complete: {res.session_id} -> {res.state.value}")
    print(f"    - Metadata Path: {res.metadata_path}")
    print(f"    - Packets: {res.packet_count} | Flows: {res.flow_count}")

    if res.state.value != "VALIDATED":
        print("[!] Sample collection failed validation -> FAIL")
        sys.exit(1)

    # 2. Ingest metadata into FlowGenerator & FeatureExtractor
    print("\n[*] Testing Pipeline Ingestion into existing Flow & Feature Extractor...")
    feature_count = ingest_metadata_file(
        metadata_csv_path=res.metadata_path,
        output_flows_csv="data/processed/flows/flows_real.csv",
        output_features_csv="data/processed/features/features_real.csv",
    )
    print(f"    - Successfully extracted {feature_count} tabular feature records!")

    print("\n=======================================================")
    print("   END-TO-END SAMPLE COLLECTION & INGESTION: SUCCESS   ")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
