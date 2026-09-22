# Operator Traffic Collection Workflow

A standardized procedure for running controlled traffic captures.

---

## 🛠️ Step-by-Step Operator Guide

### Step 1: Select Target Traffic Class
Choose the class to record from: `Web`, `Video`, `Messaging`, `VoIP`, `File Transfer`, `Other`.

### Step 2: Close Background Applications
Close unrelated network programs (e.g. background torrents, music players, automated updates) to avoid traffic contamination.

### Step 3: Launch Collection CLI
Run the collection script with the selected class and duration (e.g. 30 seconds):
```bash
python scripts/collect_traffic.py --class Web --duration 30
```

### Step 4: Perform Activity During Capture Window
When prompted by the terminal ("WARMUP COMPLETE - CAPTURING"), perform *only* the intended action (e.g., browse Wikipedia articles).

### Step 5: Automatic Processing & Validation
Upon completion of the timer, the system automatically:
1. Stops the live packet capture.
2. If any adapter error or 0 packets occurred, **fails closed** immediately without registering any real session or generating synthetic data.
3. If capture succeeded, extracts whitelisted metadata (timestamps, packet lengths, ports, protocols).
4. Securely removes any ephemeral raw capture files.
5. Validates minimum packet/byte counts.
6. Registers the capture in `data/dataset_manifest.csv` with `data_origin = "real"` and `capture_source = "REAL_LIVE_CAPTURE"`.
7. Calculates the SHA-256 digest in `results/tables/dataset_version_manifest.csv`.

### Step 6: Verify Dataset Status
Check current class balances at any time:
```bash
python scripts/dataset_status.py
```
