# Dataset V3 Windows Npcap Layer-2 Interface Resolution & Socket Initialization Fix

**Project:** Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Phase:** 2B.1 — Windows Npcap Layer-2 Interface Resolution & Socket Initialization Fix  
**Environment:** Windows 11, Python 3.14.7, Scapy 2.5.0, Npcap 1.89 (`AdminOnly: 1`)  
**Status:** IMPLEMENTED AND VERIFIED VIA 121/121 RESEARCH TESTS PASSING (27/27 DEDICATED RESOLUTION & SOCKET TESTS)  

---

## 1. Executive Summary

During pre-pilot physical capture verification on Windows 11, two consecutive runtime issues were identified and comprehensively resolved:

1. **Win32 Error 123 (`ERROR_INVALID_NAME`):**  
   The friendly interface name `"Wi-Fi"` was passed directly to the Layer-2 socket constructor, propagating to Npcap's native C function `pcap_open_live("Wi-Fi")`. On Windows, Npcap requires an NT device identifier path (e.g., `\Device\NPF_{GUID}`).
2. **Interface Resolution Inconsistency (Dummy Fallback):**  
   While a standalone diagnostic in an Administrator terminal successfully resolved `"Wi-Fi"` to physical adapter `Intel(R) Wi-Fi 6 AX201 160MHz` (`\Device\NPF_{B383A2A4-A634-4F0D-89E5-5A56CBCB9A0B}`), the smoke test and collector failed with:
   ```text
   [INTERFACE_RESOLUTION_FAILED]
   Interface 'Wi-Fi' resolved to dummy fallback. No physical Npcap adapter match found.
   ```

### Confirmed Root Cause
In `research/dataset_v3/packet_parser.py` (and multiple other research files), an initialization function executed:
```python
conf.ifaces.reload = lambda *args, **kwargs: None
```
Because `research/dataset_v3/collector.py` imported `packet_parser.py` at module load time, `conf.ifaces.reload()` was neutralized globally across the process. As a result, when the collector attempted to refresh interfaces prior to capture, the reload was a silent no-op. `conf.ifaces` remained unpopulated, forcing `resolve_iface("Wi-Fi")` to fall back to a dummy Scapy interface (`dummy: True`).

### Core Resolutions Implemented
1. **Purged Monkey-Patched Reloads:** Completely removed `conf.ifaces.reload = lambda ...` across all research modules and adapters.
2. **Consolidated Canonical Resolution Helpers:** Refactored interface resolution and socket selection into two reusable, canonical functions (`resolve_and_validate_interface` and `select_and_validate_socket_factory`) used identically by both live capture (`start_capture`) and diagnostic verification (`smoke_test_socket`).
3. **12-Field Diagnostic Logging:** Instrumented dummy interface fallback detection with all 12 requested diagnostic fields (including Python paths, Scapy module locations, object IDs, and interface registry states before/after reload).
4. **Distinct Error Reporting:** Separated adapter discovery permission failures (`[INTERFACE_ENUMERATION_FAILED]`, raising `PermissionError`) from interface matching/dummy failures (`[INTERFACE_RESOLUTION_FAILED]`, raising `RuntimeError`).
5. **Elevated Pre-Flight Guard:** Added an immediate Windows elevation check in `test_socket_smoke.py` before driver loading, preventing driver IOCTL blocking in un-elevated terminals under Npcap `AdminOnly: 1`.
6. **Non-Admin Test Support:** Added low-level C hook in `tests/conftest.py` guarding `pcap_findalldevs` exclusively for un-elevated test runners without modifying `conf.ifaces.reload`.
7. **Comprehensive Test Suite:** Expanded test suite to 27 dedicated interface resolution and socket tests; verified all 121 research tests pass with a 100% success rate.

---

## 2. Root Cause Analysis & Purge of Global Overrides

### 2.1 The Monkey-Patch Investigation
Scapy's `scapy.layers.l2` imports `scapy.arch`, which executes `_set_conf_sockets()`, which in turn triggers `conf.ifaces.reload()`. When Npcap is installed with `AdminOnly: 1`, non-elevated processes attempting to query the Npcap driver can encounter blocking IOCTLs. To prevent test imports from hanging, earlier research code had monkey-patched `conf.ifaces.reload = lambda *args, **kwargs: None`.

However, because `research/dataset_v3/collector.py` imports `packet_parser.py` unconditionally:
```python
from research.dataset_v3.packet_parser import ...
```
any process importing `collector.py` immediately had its genuine Scapy `conf.ifaces.reload` method replaced with a no-op lambda. When `collector.start_capture()` or `smoke_test_socket()` executed in an elevated Administrator session, `conf.ifaces.reload()` did nothing, `conf.ifaces` remained empty, and `resolve_iface("Wi-Fi")` fell back to a dummy interface with `dummy: True` and `network_name: "Wi-Fi"`.

### 2.2 Files Purged of `conf.ifaces.reload` Overrides
The invalid `lambda` override and extraneous `scapy.interfaces`/`conf` imports were purged from all 6 files:
1. [research/dataset_v3/packet_parser.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/packet_parser.py)
2. [research/external_datasets/adapters/cipherspectrum.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/external_datasets/adapters/cipherspectrum.py)
3. [research/external_datasets/adapters/iscxvpn2016.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/external_datasets/adapters/iscxvpn2016.py)
4. [tests/research/dataset_v3/test_packet_parser.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/dataset_v3/test_packet_parser.py)
5. [tests/research/external_datasets/test_cipherspectrum_adapter.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/external_datasets/test_cipherspectrum_adapter.py)
6. [tests/research/external_datasets/test_iscxvpn2016_adapter.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/external_datasets/test_iscxvpn2016_adapter.py)

---

## 3. Canonical Architecture: Interface Resolution & Socket Selection

In [research/dataset_v3/collector.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/collector.py), all duplicated resolution and listener selection logic was extracted into two centralized functions:

### 3.1 `resolve_and_validate_interface()`
```python
def resolve_and_validate_interface(
    interface_name: str,
    is_mock_socket: bool = False,
    collector_instance: Optional[Any] = None,
) -> NetworkInterface:
```
1. **Pre-Resolution Refresh:** Performs genuine `conf.ifaces.reload()` on Windows when libpcap is active. Permission errors are caught and raised as `PermissionError("[INTERFACE_ENUMERATION_FAILED] ...")`.
2. **Resolution:** Resolves `interface_name` using `resolve_iface(interface_name)`.
3. **Dummy Fallback Rejection:** Verifies `getattr(resolved_iface, "dummy", False) is False` and `resolved_iface.is_valid()`. If dummy, logs the complete 12 diagnostic fields and raises `RuntimeError("[INTERFACE_RESOLUTION_FAILED] ...")`.
4. **Friendly Name & Path Validation:** Ensures `resolved_iface.name == interface_name` and verifies that the network identifier starts with `\Device\NPF_` (rejecting loopback identifiers and unmodified names).

### 3.2 `select_and_validate_socket_factory()`
```python
def select_and_validate_socket_factory(
    resolved_iface: NetworkInterface,
    is_mock_socket: bool = False,
    collector_instance: Optional[Any] = None,
) -> Any:
```
1. **Interface Listener Query:** Calls `resolved_iface.l2listen()` to retrieve the provider's Layer-2 listener class.
2. **Fallback:** Falls back to `getattr(conf, "L2listen", None)` if `l2listen()` is unavailable.
3. **Provider Validation:** In non-mock environments, verifies the socket factory is a subclass of `_L2libpcapSocket` (such as `L2pcapListenSocket`). Rejects non-pcap sockets with `RuntimeError("[SOCKET_SELECTION_FAILED] ...")`.

---

## 4. Comprehensive 12-Field Diagnostic Logging

When an interface resolves to a dummy fallback, `resolve_and_validate_interface()` emits structured diagnostics:

```python
diag_lines = [
    f"[INTERFACE_RESOLUTION_FAILED] Interface '{interface_name}' resolved to dummy fallback. No physical Npcap adapter match found.",
    "Detailed Resolution Diagnostics:",
    f"  sys.executable:            {sys.executable}",
    f"  scapy.__file__:            {getattr(scapy, '__file__', None)}",
    f"  scapy.interfaces.__file__:  {getattr(scapy.interfaces, '__file__', None)}",
    f"  scapy.config.__file__:      {getattr(scapy.config, '__file__', None)}",
    f"  conf.use_pcap:             {getattr(conf, 'use_pcap', False)}",
    f"  id(conf):                  {id(conf)}",
    f"  id(conf.ifaces):           {id(conf.ifaces) if hasattr(conf, 'ifaces') else None}",
    f"  interfaces before reload:  {interfaces_before}",
    f"  interfaces after reload:   {interfaces_after}",
    f"  requested interface:       {repr(interface_name)}",
    f"  resolved type:             {type(resolved_iface).__name__}",
    f"  resolved name:             {getattr(resolved_iface, 'name', None)}",
    f"  resolved description:      {getattr(resolved_iface, 'description', None)}",
    f"  resolved dummy flag:       {is_dummy}",
    f"  resolved network name:     {getattr(resolved_iface, 'network_name', None)}",
]
logger.error("%s", "\n".join(diag_lines))
```

---

## 5. Socket Smoke Test Operation & Elevation Protection

### 5.1 Standalone Diagnostic Script
[scripts/research/dataset_v3/test_socket_smoke.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/scripts/research/dataset_v3/test_socket_smoke.py) executes safe, non-capturing diagnostic socket verification:
1. Checks Windows Administrator privileges before loading Scapy/Npcap.
2. Resolves friendly interface name via `resolve_and_validate_interface()`.
3. Selects socket factory via `select_and_validate_socket_factory()`.
4. Opens Layer-2 socket synchronously using `socket_factory(iface=resolved_iface, filter=pcap_filter, promisc=promiscuous)`.
5. Confirms socket creation.
6. Guarantees socket closure in `finally: sock.close()`.
7. **Strict Guarantees:** Zero packet reads, zero `AsyncSniffer` calls, zero session directories, zero metadata writes.

### 5.2 Elevation Pre-Check Behavior
When executed in a non-elevated shell under Windows Npcap `AdminOnly: 1`:
```text
$ C:\Python314\python.exe scripts/research/dataset_v3/test_socket_smoke.py --interface "Wi-Fi"
======================================================================
DATASET V3 LAYER-2 SOCKET DIAGNOSTIC SMOKE TEST: ELEVATION REQUIRED
======================================================================
Windows Npcap is configured with 'AdminOnly: 1'.
Opening Layer-2 sockets or enumerating physical adapters requires
Administrator privileges.

Please run this command from an elevated Administrator terminal:
  1. Open PowerShell or Command Prompt as Administrator
  2. cd 'C:\UROP project\encrypted-traffic-classification-UROP'
  3. python scripts/research/dataset_v3/test_socket_smoke.py --interface "Wi-Fi"
======================================================================
```

---

## 6. Regression Testing & Verification

### 6.1 Dedicated Interface Resolution & Socket Test Suite
File: [tests/research/dataset_v3/test_interface_resolution_and_socket.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/dataset_v3/test_interface_resolution_and_socket.py)  
Execution: `pytest tests/research/dataset_v3/test_interface_resolution_and_socket.py -v`  
Result: **27 passed in 1.55s (100% pass rate)**

Verified Test Cases:
1. `test_friendly_name_resolution`
2. `test_correct_network_name_propagation`
3. `test_interface_specific_l2_listener_selection`
4. `test_correct_socket_class`
5. `test_synchronous_socket_initialization_failure`
6. `test_successful_mocked_socket_construction`
7. `test_socket_cleanup`
8. `test_error_123_reporting`
9. `test_no_unsupported_snaplen_argument`
10. `test_no_premature_capture_active_state`
11. `test_dry_run_cleanup`
12. `test_existing_quarantine_preservation`
13. `test_smoke_test_socket_diagnostic_success`
14. `test_interface_missing_before_explicit_refresh`
15. `test_interface_available_after_refresh`
16. `test_correct_physical_wifi_interface_selected`
17. `test_dummy_fallback_rejected`
18. `test_wrong_adapter_rejected`
19. `test_socket_factory_selected_correctly`
20. `test_socket_initialization_failure_preserved`
21. `test_no_packet_reads_during_smoke_test`
22. `test_socket_always_closed_after_successful_opening`
23. `test_importing_packet_parser_does_not_replace_reload` (Subprocess verification)
24. `test_importing_collector_does_not_replace_reload` (Subprocess verification)
25. `test_genuine_reload_method_invoked_before_resolution`
26. `test_refreshed_registry_resolves_wifi_to_non_dummy`
27. `test_enumeration_failure_reported_distinctly`

### 6.2 Full Research Test Suite Execution
Execution: `pytest tests/research/ -v`  
Result: **121 passed in 7.10s (100% pass rate across entire research suite)**

---

## 7. Operational Instructions for Physical Pilot Session 1

When ready to execute the physical pilot session, run from an **elevated Administrator terminal**:

```powershell
# 1. Run socket smoke test diagnostic (opens physical socket, verifies, closes immediately)
python scripts/research/dataset_v3/test_socket_smoke.py --interface "Wi-Fi"

# 2. Run physical pilot session 1
python scripts/research/dataset_v3/run_pilot_session_1.py
```

### Safety & Scope Guarantees Maintained
- **Zero Production Source Code Modifications:** `product/`, `capture/`, `flows/`, `models/`, `preprocessing/`, and production databases remain 100% untouched.
- **Npcap Security Intact:** `AdminOnly: 1` registry setting remains preserved.
- **Forensic Evidence Preserved:** `data/research_v3/.incomplete/sess_70fc712285d34d2cb75abb02db8c1f1f/` remains intact.
- **No Premature Pilot Execution:** Physical capture was not launched during this fix.
