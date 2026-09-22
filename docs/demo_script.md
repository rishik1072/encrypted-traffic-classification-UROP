# 5–10 Minute Live Demonstration Script

Follow this structured presentation sequence for demonstration sessions:

---

## ⏱️ Timeline & Step-by-Step Sequence

### 1. Introduction & Research Problem (1 min)
- **Goal:** Explain the challenge of classifying encrypted network traffic (HTTPS, TLS 1.3, QUIC) without violating user privacy or decrypting payloads.
- **Key Point:** "We classify traffic categories using only timing, packet lengths, and bidirectional flow dynamics."

### 2. Architecture & Zero-Payload Guarantee (1 min)
- **File Reference:** Show [`docs/final_architecture.md`](docs/final_architecture.md) and [`SECURITY.md`](SECURITY.md).
- **Key Point:** Highlight that payload bytes are stripped at packet ingress.

### 3. Launching the Real-Time SOC Console (1.5 min)
- **Command:**
  ```bash
  streamlit run dashboard/app.py
  ```
- **Console Features:** Show top KPI cards (Throughput, Packets/sec, Avg Latency, CPU %), Traffic Class breakdown, and live flow feed table.

### 4. Running the Real-Time Demo Stream (2 min)
- **Command in second terminal:**
  ```bash
  python -m realtime.run --demo
  ```
- **Observation:** Watch incoming flow events get classified in real time (< 0.6ms latency) with confidence levels.
- **Low-Confidence Alerts:** Point out low-confidence flags for ambiguous flows.

### 5. Exploring Lightweight Trade-Offs & Generalization Tabs (2 min)
- **Tab 2 (Lightweight Explorer):** Show accuracy-cost trade-offs as feature count drops from $K=21$ to $K=10$ and $K=3$.
- **Tab 3 (Generalization Scorecard):** Compare performance across Random Split (0.95), Capture Split (0.90), Session Split (0.88), and Temporal Split (0.84). Show early-prediction accuracy ($N=5$ packets).

### 6. Summary & Limitations (1 min)
- **Review:** Highlight sub-millisecond inference, early prediction viability, and reproducible CLI tools (`python scripts/reproduce.py --all`).
