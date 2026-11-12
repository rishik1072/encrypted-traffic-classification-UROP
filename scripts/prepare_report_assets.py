import os
import shutil
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Ensure output directory exists
os.makedirs("UROP_Report/UROP_Report_Assets", exist_ok=True)

# 1. Copy university logo
if os.path.exists("UROP_Report_Assets/image1.png"):
    shutil.copy("UROP_Report_Assets/image1.png", "UROP_Report/UROP_Report_Assets/srm_logo.png")
    shutil.copy("UROP_Report_Assets/image1.png", "UROP_Report/UROP_Report_Assets/image1.png")
    print("Copied srm_logo.png")

# 2. Copy publication figures from results/figures/
fig_mappings = {
    "results/figures/research_baseline_model_comparison.png": "UROP_Report/UROP_Report_Assets/fig_baseline_comparison.png",
    "results/figures/research_baseline_confusion_matrix.png": "UROP_Report/UROP_Report_Assets/fig_confusion_matrix.png",
    "results/figures/feature_pareto_frontier.png": "UROP_Report/UROP_Report_Assets/fig_feature_pareto.png",
    "results/figures/generalization_comparison.png": "UROP_Report/UROP_Report_Assets/fig_generalization.png",
    "results/figures/early_prediction_f1_vs_packets.png": "UROP_Report/UROP_Report_Assets/fig_early_prediction.png",
    "results/figures/coverage_vs_accuracy.png": "UROP_Report/UROP_Report_Assets/fig_selective_coverage.png",
    "results/figures/calibration_curve.png": "UROP_Report/UROP_Report_Assets/fig_calibration_curve.png",
    "results/figures/latency_distribution.png": "UROP_Report/UROP_Report_Assets/fig_latency_distribution.png",
    "results/figures/environment_shift.png": "UROP_Report/UROP_Report_Assets/fig_environment_shift.png",
    "results/figures/tunnel_shift.png": "UROP_Report/UROP_Report_Assets/fig_tunnel_shift.png",
}

for src, dst in fig_mappings.items():
    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"Copied {src} -> {dst}")
    else:
        print(f"Warning: {src} not found")

# 3. Generate high-resolution System Architecture Diagram
fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

# Colors
c_input = "#E0F2FE"
c_proc = "#E0E7FF"
c_feat = "#FEF3C7"
c_ml = "#DCFCE7"
c_ui = "#F3E8FF"
border_col = "#334155"

def draw_box(ax, x, y, w, h, bg_color, title, subtitle, bullets=[]):
    box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.8,rounding_size=2.0",
                                facecolor=bg_color, edgecolor=border_col, linewidth=1.5)
    ax.add_patch(box)
    ax.text(x + w/2, y + h - 5, title, ha="center", va="center", fontsize=10, fontweight="bold", color="#0F172A")
    if subtitle:
        ax.text(x + w/2, y + h - 11, subtitle, ha="center", va="center", fontsize=8, fontstyle="italic", color="#475569")
    curr_y = y + h - 18
    for b in bullets:
        ax.text(x + 3, curr_y, f"• {b}", ha="left", va="center", fontsize=7.5, color="#1E293B")
        curr_y -= 5.5

# Pipeline boxes
draw_box(ax, 2, 35, 17, 50, c_input, "Physical Ingestion", "Layer-2/3 Network Tap", 
         ["Physical Wi-Fi / NIC", "Windows Npcap Driver", "Ring Buffer Polling", "Zero-Payload Tap", "Payload Scrubbing"])

draw_box(ax, 22, 35, 17, 50, c_proc, "Flow Reconstruction", "Bidirectional Tracking", 
         ["5-Tuple Canonical Key", "Forward/Backward Seg", "TCP FIN/RST State", "Idle/Active Timeout", "Connection Lifecycle"])

draw_box(ax, 42, 35, 17, 50, c_feat, "Feature Extraction", "Zero-Payload Dynamics", 
         ["21 Canonical Features", "Directional Ratios", "Packet Size Stats", "Welford IAT Variance", "Burst Density Profile"])

draw_box(ax, 62, 35, 17, 50, c_ml, "ML Inference", "Selective Decision", 
         ["CART Decision Tree", "Random Forest / LGBM", "Single-Flow 0.058 ms", "Posterior P(Class|X)", "Abstention Threshold"])

draw_box(ax, 82, 35, 17, 50, c_ui, "Event Transport", "Real-Time SOC Console", 
         ["Local REST API (:8080)", "LocalEventStore (SQLite)", "Streamlit SOC Console", "Security Alert Engine", "KPIs & Telemetry"])

# Draw Arrows
arrow_kw = dict(arrowstyle="->,head_width=0.4,head_length=0.6", color="#0284C7", lw=2)
ax.annotate("", xy=(22, 60), xytext=(19, 60), arrowprops=arrow_kw)
ax.annotate("", xy=(42, 60), xytext=(39, 60), arrowprops=arrow_kw)
ax.annotate("", xy=(62, 60), xytext=(59, 60), arrowprops=arrow_kw)
ax.annotate("", xy=(82, 60), xytext=(79, 60), arrowprops=arrow_kw)

# Privacy & Security Boundary Banner across bottom
sec_box = patches.FancyBboxPatch((2, 6), 96, 20, boxstyle="round,pad=0.5,rounding_size=1.5",
                                 facecolor="#F1F5F9", edgecolor="#64748B", linewidth=1.2, linestyle="--")
ax.add_patch(sec_box)
ax.text(50, 20, "STRICT ZERO-PAYLOAD PRIVACY & LOCALHOST SECURITY INVARIANT", ha="center", va="center", fontsize=9, fontweight="bold", color="#0F172A")
ax.text(50, 14, "100% Non-DPI: No payload byte inspection • No TLS decryption proxies • No Server Name Indication (SNI) mining", ha="center", va="center", fontsize=8, color="#334155")
ax.text(50, 9, "Scrubbed IP / Port addresses • Deterministic Group-Aware Session Isolation • Localhost REST / Socket Boundary", ha="center", va="center", fontsize=8, color="#334155")

plt.tight_layout()
arch_path = "UROP_Report/UROP_Report_Assets/architecture_diagram.png"
plt.savefig(arch_path, dpi=300, bbox_inches="tight")
plt.close()
print(f"Generated {arch_path}")

# 4. Generate Research Workflow Flowchart
fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

w_step = 16
h_step = 40
y_pos = 35

def draw_step(ax, x, y, title, subtitle, bullets, col):
    box = patches.FancyBboxPatch((x, y), w_step, h_step, boxstyle="round,pad=0.6,rounding_size=2.0",
                                facecolor=col, edgecolor="#334155", linewidth=1.4)
    ax.add_patch(box)
    ax.text(x + w_step/2, y + h_step - 5, title, ha="center", va="center", fontsize=8.5, fontweight="bold", color="#0F172A")
    ax.text(x + w_step/2, y + h_step - 10, subtitle, ha="center", va="center", fontsize=7.5, fontstyle="italic", color="#475569")
    curr_y = y + h_step - 16
    for b in bullets:
        ax.text(x + 2, curr_y, f"• {b}", ha="left", va="center", fontsize=7, color="#1E293B")
        curr_y -= 5

draw_step(ax, 2, y_pos, "Phase 1: Collection", "dataset_v2 Benchmark", ["301 Flows (150 Sess)", "802.11ax Wi-Fi Physical", "Sim. Eth & Cell Jitter", "Direct vs WireGuard"], "#E0F2FE")
draw_step(ax, 22, y_pos, "Phase 2: Partitioning", "Session Isolation", ["Group-Aware Splitting", "Zero Session Leakage", "6 Balanced Classes", "Train/Val/Test 60/20/20"], "#FEF08A")
draw_step(ax, 42, y_pos, "Phase 3: Extraction", "Feature Engineering", ["Welford Online IAT", "Size & Burst Metrics", "Directional Asymmetry", "84 -> 21 -> 3 Features"], "#FED7AA")
draw_step(ax, 62, y_pos, "Phase 4: Modeling", "Model Optimization", ["LR, DT, RF, LightGBM", "Hyperparam Tuning", "Early Triage (N=3)", "Calibration (ECE)"], "#BBF7D0")
draw_step(ax, 82, y_pos, "Phase 5: Evaluation", "Empirical Auditing", ["Generalization Scorecard", "Pareto Latency Profile", "Selective Rejection", "Live Physical Capture"], "#DDD6FE")

for x_arr in [18, 38, 58, 78]:
    ax.annotate("", xy=(x_arr + 4, 55), xytext=(x_arr, 55), arrowprops=dict(arrowstyle="->,head_width=0.4,head_length=0.6", color="#0284C7", lw=2))

ax.text(50, 15, "Figure 3.2: End-to-End Experimental Research Methodology and Verification Workflow", ha="center", va="center", fontsize=9.5, fontweight="bold", color="#1E293B")

plt.tight_layout()
flow_path = "UROP_Report/UROP_Report_Assets/workflow_flowchart.png"
plt.savefig(flow_path, dpi=300, bbox_inches="tight")
plt.close()
print(f"Generated {flow_path}")

