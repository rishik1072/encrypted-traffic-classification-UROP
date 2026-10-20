# Investigation and Resolution Report: Three Test Failures Audit

**Project:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Branch:** `audit/fix-research-and-pipeline`  
**Host Environment:** Windows 11 AMD64, Python 3.14.7, pytest 9.1.1  
**Date:** 2026-10-20  

---

## Executive Summary

A comprehensive investigation was conducted into the three failures identified during baseline testing (`python -m pytest tests/`):

| Test Identifier | Initial Status | Root Cause | Final Status |
| :--- | :--- | :--- | :--- |
| `tests/test_offline_realtime_parity.py::TestOfflineRealtimeParity::test_inference_outcome_parity` | **FAIL** (`AssertionError: unexpectedly None`) | Test fixture constructed an ad-hoc unobserved `Flow` bypassing `FlowTracker`; classifier triggered intentional fail-closed security boundary. | **PASS** (100% parity verified; fail-closed regression test added) |
| `tests/test_product_adapters.py::TestProductAdapters::test_mock_npcap_unavailable_empty_list` | **FAIL** (`AssertionError: dict is not None`) | `get_default_adapter()` retained stale cached adapters and fabricated a fake Wi-Fi fallback dictionary when interface discovery returned empty. | **PASS** (clears cache, returns `None` strictly; 2 regression tests added) |
| `tests/test_product_hardening.py::TestProductHardening::test_run_installation_validation_scorecard` | **FAIL** (`AssertionError: 'FAIL' != 'PASS'`) | Missing dependency (`click` for `streamlit`) caused Test 2 to report missing dependency; Windows Npcap `AdminOnly` privilege restrictions caused interface probing to hang/fail. | **PASS** (All 9/9 scorecard checks pass; failure regression test added) |

**Overall Suite Outcome:**
- **Initial Baseline:** 244 passed, 3 failed, 1 skipped (248 total tests).
- **Post-Fix Baseline:** **251 passed, 1 skipped (252 total tests)** with **0 failures** in **334.96 seconds**.

---

## 1. Root Cause Analysis

### Failure 1: Offline / Realtime Parity
- **Test:** `tests/test_offline_realtime_parity.py::TestOfflineRealtimeParity::test_inference_outcome_parity`
- **Symptom:**
  ```text
  AssertionError: unexpectedly None
  Log: WARNING realtime.classifier:classifier.py:233 [FAIL-CLOSED] Refusing to emit prediction: flow F-00000 has not been observed by flow tracker.
  ```
- **Root Cause:**
  In `RealTimeClassifier._classify_flow_instance(flow)`, lines 226–235 enforce an authoritative security invariant:
  ```python
  flow_id = self.flow_tracker.get_flow_id(flow.key)
  if not self.flow_tracker.has_observed_flow(flow_id):
      logger.warning("[FAIL-CLOSED] Refusing to emit prediction: flow %s has not been observed by flow tracker.", flow_id)
      return None
  ```
  The production pipeline ingests packets through `flow_tracker.update(pkt)`, which registers active flows and session metadata into `flow_stability_map`. In `test_inference_outcome_parity`, the test author constructed a raw `Flow` instance manually and added packets to it directly, but never registered it with `self.classifier.flow_tracker`. Because `has_observed_flow` evaluated to `False`, the classifier correctly failed closed.
- **Resolution:**
  Updated `test_inference_outcome_parity` to follow the legitimate lifecycle by feeding the golden packet sequence through `self.classifier.flow_tracker.update(pkt)`, and confirmed identical feature extraction, probabilities, and class prediction (`Web`, 0.95 confidence) between offline `ModelLoader` and streaming `RealTimeClassifier`. A dedicated negative regression test was added verifying that unobserved flows continue to fail closed.

---

### Failure 2: Network Adapter Discovery
- **Test:** `tests/test_product_adapters.py::TestProductAdapters::test_mock_npcap_unavailable_empty_list`
- **Symptom:**
  ```text
  AssertionError: {'friendly_name': 'Wi-Fi', 'interface_description': 'Intel Wi-Fi 6 AX201', 'npcap_name': '\\Device\\NPF_{WIFI}', ...} is not None
  ```
- **Root Cause:**
  Two defects in `product/adapter_manager.py`:
  1. `get_default_adapter()` cached the discovered adapter in global `_CACHED_DEFAULT_ADAPTER`. When `test_mock_adapter_priority_wifi_over_ethernet` ran prior to `test_mock_npcap_unavailable_empty_list`, the global cache held the mock Wi-Fi adapter.
  2. Even if cache was empty, lines 126–138 of `product/adapter_manager.py` had a hardcoded fallback that fabricated a synthetic Wi-Fi dictionary (`r"\Device\NPF_Generic"`) out of thin air when `adapters` was empty, directly violating the contract that an unavailable capture environment must return `None`.
- **Resolution:**
  1. Removed the synthetic fallback dictionary from `get_default_adapter()`. When `adapters` is empty, `get_default_adapter()` resets `_CACHED_DEFAULT_ADAPTER = None` and returns `None`.
  2. Updated `list_adapters()` to clear `_CACHED_DEFAULT_ADAPTER = None` whenever interface discovery returns an empty list.

---

### Failure 3: Installation Validation Scorecard
- **Test:** `tests/test_product_hardening.py::TestProductHardening::test_run_installation_validation_scorecard`
- **Symptom:**
  ```text
  AssertionError: 'FAIL' != 'PASS'
  - FAIL
  + PASS
  ```
- **Root Cause:**
  1. **Missing Core Dependency:** `streamlit` 1.62.0 was installed in the user site-packages, but its transitive dependency `click` was missing. When `run_installation_validation` executed Test 2 (`required_pkgs`), `__import__("streamlit")` raised `ModuleNotFoundError: No module named 'click'`, causing Test 2 to fail and marking `overall_status = "FAIL"`.
  2. **Npcap Access & UAC Prompt:** On Windows 11 with Npcap configured in `AdminOnly` mode (`HKLM\SYSTEM\CurrentControlSet\Services\npcap\Parameters\AdminOnly = 1`), a standard non-elevated user calling `import scapy.all` or `resolve_capture_interface()` triggered Scapy's Windows interface provider to execute `powershell Start-Process cmd -Verb RunAs ...` (UAC prompt), which hangs in non-interactive/automated environments.
- **Resolution:**
  1. Installed `click>=8.5.0` to resolve `streamlit` importability.
  2. Added a safe, non-blocking Windows registry and `psutil` adapter resolver (`_get_windows_adapters_safe()`) in `capture/interface_resolver.py`. On Windows, standard non-elevated callers retrieve active adapters (`Wi-Fi`, `Ethernet`, `Loopback`) directly from `HKLM\SYSTEM\CurrentControlSet\Control\Network` and `psutil` without invoking blocking driver calls or UAC prompts.
  3. Cleaned `resolve_capture_interface()` to avoid importing `scapy.all` when resolving interface metadata.

---

## 2. Files Changed and Rationale

| File Path | Description of Changes | Rationale |
| :--- | :--- | :--- |
| [`capture/interface_resolver.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/capture/interface_resolver.py) | Added `_get_windows_adapters_safe()` using Windows Registry and `psutil`. Updated `list_scapy_interfaces()` and `resolve_capture_interface()` to use safe Windows enumeration when running without elevation. | Prevents non-interactive hangs and blocking UAC prompts on Windows while preserving accurate Wi-Fi and Ethernet detection. |
| [`product/adapter_manager.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/product/adapter_manager.py) | Removed fabricated synthetic Wi-Fi dictionary in `get_default_adapter()`. Cleared `_CACHED_DEFAULT_ADAPTER` when `adapters` is empty. | Satisfies requirement that missing/empty Npcap discovery returns `None` strictly without fabricating devices. |
| [`tests/test_offline_realtime_parity.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/test_offline_realtime_parity.py) | Updated `test_inference_outcome_parity` to register flows via `flow_tracker.update(pkt)`. Added regression test `test_unregistered_flow_fails_closed`. | Uses legitimate production lifecycle and explicitly asserts fail-closed security boundary on untracked flows. |
| [`tests/test_product_adapters.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/test_product_adapters.py) | Added `test_default_adapter_cleared_on_empty_discovery` and `test_safe_windows_adapter_discovery_structure`. | Verifies cache invalidation upon empty discovery and validates safe Windows adapter discovery schema. |
| [`tests/test_product_hardening.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/test_product_hardening.py) | Added `test_installation_validation_scorecard_fails_on_missing_prerequisite`. | Verifies that the scorecard accurately transitions to `FAIL` when mandatory prerequisites or configurations are missing. |

---

## 3. Regression Tests Added

1. **`tests/test_offline_realtime_parity.py::TestOfflineRealtimeParity::test_unregistered_flow_fails_closed`**  
   Verifies that an unobserved flow created outside `FlowTracker` is rejected by `_classify_flow_instance`, returning `None` and preserving the fail-closed invariant.

2. **`tests/test_product_adapters.py::TestProductAdapters::test_default_adapter_cleared_on_empty_discovery`**  
   Simulates active adapter resolution followed by an empty discovery result, verifying that `get_default_adapter(force_refresh=True)` clears stale cached adapters and returns `None`.

3. **`tests/test_product_adapters.py::TestProductAdapters::test_safe_windows_adapter_discovery_structure`**  
   Ensures `_get_windows_adapters_safe()` discovers Windows network adapters with all required fields (`identifier`, `friendly_name`, `description`, `network_name`, `guid`, `ip`, `is_up`) without hanging or throwing exceptions.

4. **`tests/test_product_hardening.py::TestProductHardening::test_installation_validation_scorecard_fails_on_missing_prerequisite`**  
   Simulates a missing `config.yaml` file and asserts that `run_installation_validation()` correctly reports `overall_status == "FAIL"` and marks Test 1 as failed.

---

## 4. Verification Commands and Actual Output

### Command 1: Offline/Realtime Parity Suite
```powershell
python -m pytest tests/test_offline_realtime_parity.py -q
```
**Output:**
```text
...                                                                      [100%]
3 passed in 0.44s
```

### Command 2: Product Adapter Discovery Suite
```powershell
python -m pytest tests/test_product_adapters.py -q
```
**Output:**
```text
......                                                                   [100%]
6 passed in 0.27s
```

### Command 3: Product Hardening & Installation Validation Suite
```powershell
python -m pytest tests/test_product_hardening.py -q
```
**Output:**
```text
.........                                                                [100%]
9 passed in 8.71s
```

### Command 4: Complete Test Suite
```powershell
python -m pytest tests/
```
**Output:**
```text
================= 251 passed, 1 skipped in 334.96s (0:05:34) ==================
Exit code: 0
```

---

## 5. Security & Research Integrity Invariants

1. **Zero-Payload Policy Preserved:**  
   No payload bytes, packet buffers, or TLS plaintext are inspected, stored, or exposed. Canonical features remain strictly derived from packet lengths, timestamps, and directions.
2. **Fail-Closed Principle Intact:**  
   Flows not tracked in `flow_stability_map` are strictly rejected before inference.
3. **Localhost Binding Maintained:**  
   All API endpoints bind strictly to `127.0.0.1`.
4. **Research Artifacts Untouched:**  
   All baseline models (`lightgbm.joblib`, `random_forest.joblib`, `decision_tree.joblib`), evaluation splits, and benchmark tables in `results/tables/` remain 100% immutable and verified.
5. **Known Environmental Limitation:**  
   Npcap live capture on Windows requires running the terminal as Administrator when Npcap is installed in `AdminOnly` mode. When non-elevated, the system correctly and safely reports `FAIL_CLOSED_EXPECTED` under Test 8 while allowing all offline, synthetic, demo, and dashboard workflows to function.
