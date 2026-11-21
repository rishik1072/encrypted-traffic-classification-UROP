# Probability Calibration and Selective Classification Audit

**Repository**: `encrypted-traffic-classification-UROP`  
**Audit Date**: November 2026  
**Auditor**: Independent ML & Systems Research Audit  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Executive Summary

This audit evaluates the reliability, calibration, and selective classification claims of the machine learning models in the repository.

Two central findings emerge from empirical artifacts:
1. **Model Calibration Status**: The deployed LightGBM model is **uncalibrated**. Although `models/production_registry.json` lists `"calibration": "Platt_Scaling_Sigmoid"`, no post-hoc calibration wrapper (such as Scikit-Learn's `CalibratedClassifierCV`) is applied in `models/lightgbm_model.py` or `realtime/classifier.py`. The model exhibits severe miscalibration on held-out test data, with an Expected Calibration Error (**ECE**) of **19.96%** and a Maximum Calibration Error (**MCE**) of **55.81%**.
2. **Selective Accuracy Reconciliation**: The claim that selective classification achieves **87.1% accuracy at $\tau=0.70$** is **factually contradicted**. Authoritative results in `results/tables/research_selective_prediction.csv` demonstrate that at $\tau=0.70$, test accuracy is **73.08%** (Macro-F1 **0.6515**, coverage **54.17%**). The 87.1% figure was an error resulting from misreading an empirical risk figure of $0.8717$ in `results/tables/risk_coverage.csv`.

---

## 2. Empirical Calibration Audit (`results/tables/research_calibration.csv`)

On the locked group-aware test split of `dataset_v2` ($N=48$ flows), the LightGBM classifier exhibits the following overall calibration metrics:
- **Expected Calibration Error (ECE)**: `0.1996` (19.96%)
- **Maximum Calibration Error (MCE)**: `0.5581` (55.81%)
- **Multiclass Brier Score**: `0.6061`
- **Negative Log-Likelihood (NLL)**: `1.4153`

### 2.1 Complete 10-Bin Reliability Distribution

| Bin Index | Confidence Range | Sample Count | Proportion | Avg Confidence | Empirical Accuracy | Calibration Gap | Miscalibration Mode |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | $[0.00, 0.10)$ | 0 | 0.00% | 0.0500 | 0.0000 | 0.0000 | N/A |
| **2** | $[0.10, 0.20)$ | 0 | 0.00% | 0.1500 | 0.0000 | 0.0000 | N/A |
| **3** | $[0.20, 0.30)$ | 0 | 0.00% | 0.2500 | 0.0000 | 0.0000 | N/A |
| **4** | $[0.30, 0.40)$ | 0 | 0.00% | 0.3500 | 0.0000 | 0.0000 | N/A |
| **5** | $[0.40, 0.50)$ | 4 | 8.33% | 0.4360 | 0.0000 | 0.4360 | Extreme Overconfidence |
| **6** | $[0.50, 0.60)$ | 8 | 16.67% | 0.5441 | 0.3750 | 0.1691 | Overconfidence |
| **7** | $[0.60, 0.70)$ | 10 | 20.83% | 0.6556 | 0.4000 | 0.2556 | Overconfidence |
| **8** | $[0.70, 0.80)$ | 5 | 10.42% | 0.7581 | **0.2000** | **0.5581** | **Severe Overconfidence (Peak MCE)** |
| **9** | $[0.80, 0.90)$ | 11 | 22.92% | 0.8615 | 0.8182 | 0.0434 | Well Calibrated |
| **10** | $[0.90, 1.00]$ | 10 | 20.83% | 0.9658 | 0.9000 | 0.0658 | Well Calibrated |

### 2.2 Forensic Analysis of the Calibration Failure
- **Bin 8 Inversion**: In the $[0.70, 0.80)$ confidence range, the model expresses an average confidence of 75.81%, but its empirical accuracy is only **20.00%** (1 correct out of 5 flows). This 55.81% calibration gap demonstrates that uncalibrated tree margin scores cannot be interpreted as true posterior probabilities.
- **Bimodal Confidence Concentration**: Over 85% of test samples are placed into confidence bins $> 0.50$, reflecting tree ensembles' inherent tendency to produce overconfident, saturated probability estimates near 0 and 1.

---

## 3. Selective Classification Sweep (`results/tables/research_selective_prediction.csv`)

Under selective classification, the system abstains from classifying flows whose maximum predicted posterior probability is below a threshold $\tau$.

### 3.1 Validation vs. Locked Test Progression

| Split | Threshold $\tau$ | Coverage | Accepted / Total | Selective Accuracy | Selective Macro-F1 | Error Rate Accepted | ECE | Brier Score | Selected $\tau^*$? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Validation** | 0.00 | 100.0% | 48 / 48 | 0.5625 | 0.5664 | 0.4375 | 0.1445 | 0.5682 | NO |
| **Validation** | 0.50 | 77.1% | 37 / 48 | 0.6757 | 0.7024 | 0.3243 | 0.1188 | 0.5018 | NO |
| **Validation** | 0.60 | 64.6% | 31 / 48 | 0.7097 | 0.7420 | 0.2903 | 0.1330 | 0.4633 | NO |
| **Validation** | **0.70** | **50.0%** | **24 / 48** | **0.7500** | **0.7741** | **0.2500** | **0.1495** | **0.4110** | **YES ($\tau^*$)** |
| **Validation** | 0.80 | 43.8% | 21 / 48 | 0.7619 | 0.7884 | 0.2381 | 0.1580 | 0.3827 | NO |
| **Validation** | 0.90 | 31.2% | 15 / 48 | 0.8667 | 0.8333 | 0.1333 | 0.0755 | 0.2333 | NO |
| **Test** | 0.00 | 100.0% | 48 / 48 | 0.5417 | 0.5474 | 0.4583 | 0.1996 | 0.6061 | NO |
| **Test** | 0.50 | 91.7% | 44 / 48 | 0.5909 | 0.6012 | 0.4091 | 0.1781 | 0.5716 | NO |
| **Test** | 0.60 | 75.0% | 36 / 48 | 0.6389 | 0.6110 | 0.3611 | 0.1800 | 0.5268 | NO |
| **Test** | **0.70** | **54.2%** | **26 / 48** | **0.7308** | **0.6515** | **0.2692** | **0.1510** | **0.4402** | **YES ($\tau^*$)** |
| **Test** | 0.80 | 43.8% | 21 / 48 | 0.8571 | 0.8752 | 0.1429 | 0.0541 | 0.2442 | NO |
| **Test** | 0.90 | 20.8% | 10 / 48 | 0.9000 | 0.9000 | 0.1000 | 0.0658 | 0.1912 | NO |

### 3.2 Audit of the Selected Operating Point ($\tau^* = 0.70$)
1. **Validation Selection**: Threshold $\tau^* = 0.70$ was selected on validation data to achieve $\ge 50\%$ coverage while maximizing selective accuracy (75.00%).
2. **Held-Out Test Generalization**:
   - Coverage: **54.2%** (26 accepted flows, 22 abstentions out of 48).
   - Selective Accuracy: **73.08%** (19 correct classifications among accepted flows).
   - Error Rate on Accepted Flows: **26.92%**.
   - Selective Macro-F1: **0.6515**.
3. **Discrepancy Source**:
   In `results/tables/risk_coverage.csv`, row 14 lists `empirical_risk = 0.8717` for an aggressive threshold. A superficial reading confused empirical risk with accuracy, leading to the erroneous assertion that selective accuracy reached 87.1%.

---

## 4. Architectural Audit: Deployed vs. Claimed Calibration

### 4.1 Production Model Inspection
In `models/production_registry.json`:
```json
{
  "active_model_id": "model_lightgbm_v1",
  "calibration": "Platt_Scaling_Sigmoid",
  "uncertainty_threshold": 0.50
}
```
Inspection of `realtime/classifier.py` reveals how predictions are actually computed:
```python
probas = self.model.predict_proba(features_scaled)
confidence = float(np.max(probas))
predicted_class = self.classes[int(np.argmax(probas))]
```
- **Finding**: The classifier calls `model.predict_proba()` directly on the `LightGBMTrafficClassifier` instance, which in turn invokes `self.booster.predict()` with raw multi-class softmax.
- **Finding**: No Platt scaling, isotonic regression, or temperature scaling transform is applied to the probability vector before thresholding. The metadata tag `"calibration": "Platt_Scaling_Sigmoid"` is purely descriptive documentation that does not correspond to an active processing component.

---

## 5. Phase 1 Implementation Plan for Formal Calibration

To publish verifiable calibration results in an academic venue, Phase 1 must implement:
1. **Temperature Scaling / Dirichlet Calibration**:
   Fit a temperature parameter $T > 0$ on the validation logit outputs $\mathbf{z}$:
   $$P(y = k \mid \mathbf{x}) = \frac{\exp(z_k / T)}{\sum_{j=1}^K \exp(z_j / T)}$$
   This scales softmax entropies without altering class rank order.
2. **Explicit Calibration Wrappers**:
   Wrap models using Scikit-Learn's `CalibratedClassifierCV(method='sigmoid', cv='prefit')` evaluated strictly on the validation partition.
3. **Formal Selective Risk Guarantees**:
   Formulate selective classification as a bounded-risk optimization:
   $$\min_\tau \operatorname{Coverage}(\tau) \quad \text{subject to} \quad \operatorname{Risk}(\tau) \le \epsilon$$
