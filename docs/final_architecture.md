# Final System Architecture

## 1. End-to-End System Architecture

The pipeline processes encrypted network traffic strictly through statistical, temporal, and metadata-based attributes without payload decryption or Deep Packet Inspection (DPI).

```
[ LIVE NETWORK STREAM / DEMO REPLAY ]
                 │
                 ▼
     [ capture/packet_capture.py ]
                 │ (RawPacketMetadata: IP, Port, Proto, Length, Timestamp)
                 ▼
     [ realtime/flow_tracker.py ]
                 │ (Active 5-Tuple Window, Timeouts & Early Triggers)
                 ▼
  [ preprocessing/feature_extractor.py ]
                 │ (Zero-Payload Statistical Distributions: K in {21, 15, 10, 5, 3})
                 ▼
  [ preprocessing/preprocessing.py ]
                 │ (Missing value median imputation & Standard scaling)
                 ▼
     [ models/<model>.py ]
                 │ (LightGBM / Decision Tree / Random Forest / Logistic Regression)
                 ▼
     [ realtime/classifier.py ]
                 │ (Asynchronous Decoupled Worker Queue & Confidence Thresholding)
                 ▼
       [ realtime/events.py ]
                 │ (TrafficPredictionEvent on in-memory EventBus)
                 ├──▶ Persistence: results/realtime/predictions.csv & .jsonl
                 ▼
      [ dashboard/app.py ]
                 │ (Streamlit Cybersecurity SOC Monitoring Console)
```

---

## 2. Offline Research & Model Optimization Path

```
[ Raw PCAP Datasets ] ──▶ [ training/build_flow_dataset.py ] ──▶ [ flows.csv ]
                                                                       │
                                                                       ▼
                                                       [ build_feature_dataset.py ]
                                                                       │
                                                                       ▼
                                                          [ dataset_cleaner.py ]
                                                                       │
                                                                       ▼
                                                           [ create_splits.py ]
                                                    (Group-Aware Leakage-Free)
                                                                       │
                                                                       ▼
                                                      [ feature_ranking.py ]
                                                      (MI, RF, LGBM, Permutation)
                                                                       │
                                                                       ▼
                                                  [ feature_reduction_experiment.py ]
                                                      (K in {21, 15, 10, 5, 3})
                                                                       │
                                                                       ▼
                                                      [ pareto_analysis.py ]
                                                  (Accuracy-Cost Trade-Offs)
                                                                       │
                                                                       ▼
                                                  [ finalize_configuration.py ]
                                                  (Locked Configuration Checkpoint)
                                                                       │
                                                                       ▼
                                                   [ Single Test Evaluation ]
```

---

## 3. Component Responsibilities & Boundaries

| Component | Responsibility | Privacy & Payload Boundary |
| :--- | :--- | :--- |
| `capture/` | Raw network packet capture via Scapy or offline PCAP reader. | Strips packet payload bytes immediately; extracts Layer-3/4 header stats only. |
| `flows/` | Bidirectional 5-tuple flow aggregation with idle/active timeouts. | Maintains rolling packet length and arrival timestamp queues. |
| `preprocessing/`| Computes 21 zero-payload statistical distributions, imputes medians, scales values. | Scrubs IP addresses from feature space to eliminate network topology shortcuts. |
| `models/` | Multiclass classifiers with scikit-learn APIs and pure-Python fallbacks. | Model accepts normalized numerical feature vectors only. |
| `training/` | Splitting, cross-validation, feature ranking, Pareto selection, calibration. | Strict train/validation isolation; single held-out test evaluation. |
| `realtime/` | Non-blocking async classification worker, event bus, metrics telemetry. | Buffers stream events and logs anonymized classifications to CSV/JSONL. |
| `dashboard/` | SOC-style monitoring console with KPI cards, flow feeds, and trade-off tabs. | Displays statistical telemetry without revealing sensitive packet payloads. |
