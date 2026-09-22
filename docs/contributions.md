# Research Contributions

The conservative scientific and engineering contributions of this research project are:

1. **Zero-Payload Pipeline Implementation**: Designed and implemented a complete pipeline processing Layer-3/4 transport headers, packet lengths, and timing dynamics without payload decryption or Deep Packet Inspection.
2. **Systematic Model & Feature Benchmarking**: Conducted multi-criteria evaluations across four lightweight ML families (Logistic Regression, Decision Tree, Random Forest, LightGBM) measuring Macro-F1, inference latency, and serialized disk footprint.
3. **Multi-Method Feature Ranking & Reduction**: Implemented multi-strategy feature ranking (Mutual Information, Random Forest, LightGBM, Permutation) and quantified the Pareto frontier across reduced feature subsets ($K \in \{21, 15, 10, 5, 3\}$).
4. **Asynchronous Real-Time Architecture**: Built an asynchronous classification engine with bidirectional flow lifecycle state tracking, confidence scoring, and sliding-window continuous metrics telemetry.
5. **Multi-Regime Generalization Assessment**: Quantified performance degradation across unseen captures, unseen user sessions, chronological temporal boundaries, and early-packet observation points ($N \le 5$).
6. **Fully Reproducible Research Packaging**: Provided single-command reproduction tooling, cryptographic dataset provenance manifests, claim verification scripts, and an interactive Streamlit SOC dashboard.
