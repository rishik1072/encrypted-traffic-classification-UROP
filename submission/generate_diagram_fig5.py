import matplotlib.pyplot as plt
import matplotlib.patches as patches

def create_realtime_pipeline_diagram(output_path):
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis('off')

    # Color palette - academic corporate
    navy = '#1A365D'
    blue = '#2B6CB0'
    light_blue = '#EBF8FF'
    border_blue = '#3182CE'
    gold = '#D69E2E'
    light_gold = '#FEFCBF'
    green = '#2F855A'
    light_green = '#F0FFF4'
    dark_gray = '#2D3748'
    bg_gray = '#EDF2F7'

    # Title box
    title_box = patches.FancyBboxPatch((0.5, 5.7), 11.0, 0.65,
                                       boxstyle="round,pad=0.1", fc=navy, ec='none')
    ax.add_patch(title_box)
    ax.text(6.0, 6.02, "Real-Time Streaming Classification Pipeline & SOC Monitoring Architecture",
            color='white', fontsize=13, fontweight='bold', ha='center', va='center')

    # Stage 1: Ingestion & Privacy Hygiene
    s1 = patches.FancyBboxPatch((0.5, 3.2), 2.4, 2.2, boxstyle="round,pad=0.1",
                                fc=light_blue, ec=border_blue, lw=1.5)
    ax.add_patch(s1)
    ax.text(1.7, 5.15, "1. Ingestion & Hygiene", color=navy, fontsize=10, fontweight='bold', ha='center')
    ax.text(1.7, 4.7, "• Npcap / Scapy Sniffer\n• Promiscuous Adapter Hook\n• Immediate Payload Strip\n• Transport Header Only\n• Zero-Payload Invariant",
            color=dark_gray, fontsize=8.5, ha='center', va='top', linespacing=1.4)

    # Stage 2: Flow Tracking
    s2 = patches.FancyBboxPatch((3.3, 3.2), 2.5, 2.2, boxstyle="round,pad=0.1",
                                fc=light_blue, ec=border_blue, lw=1.5)
    ax.add_patch(s2)
    ax.text(4.55, 5.15, "2. Flow Tracking", color=navy, fontsize=10, fontweight='bold', ha='center')
    ax.text(4.55, 4.7, "• Bidirectional 5-Tuple\n• Sliding-Window Table\n• Early Triggers (N=3,5,10)\n• Inactivity Expiry (15s)\n• Microsecond Timestamps",
            color=dark_gray, fontsize=8.5, ha='center', va='top', linespacing=1.4)

    # Stage 3: Feature Extraction & Model Inference
    s3 = patches.FancyBboxPatch((6.2, 3.2), 2.6, 2.2, boxstyle="round,pad=0.1",
                                fc=light_gold, ec=gold, lw=1.5)
    ax.add_patch(s3)
    ax.text(7.5, 5.15, "3. Feature & Inference", color='#744210', fontsize=10, fontweight='bold', ha='center')
    ax.text(7.5, 4.7, "• Compact K=3 Vectors\n• Directional & Size Ratios\n• Sub-millisecond Feature Time\n• LightGBM / Decision Tree\n• Warm Inference < 0.1 ms",
            color=dark_gray, fontsize=8.5, ha='center', va='top', linespacing=1.4)

    # Stage 4: Triage & Selective Abstention
    s4 = patches.FancyBboxPatch((9.2, 3.2), 2.3, 2.2, boxstyle="round,pad=0.1",
                                fc=light_green, ec=green, lw=1.5)
    ax.add_patch(s4)
    ax.text(10.35, 5.15, "4. Selective Gating", color=green, fontsize=10, fontweight='bold', ha='center')
    ax.text(10.35, 4.7, "• Softmax Probabilities\n• Threshold tau = 0.70\n• High Conf: Automated\n• Low Conf: Abstain/Triage\n• Fail-Closed Safety",
            color=dark_gray, fontsize=8.5, ha='center', va='top', linespacing=1.4)

    # Connecting Arrows (Top Row)
    arrow_props = dict(facecolor=navy, edgecolor='none', width=1.8, headwidth=6, headlength=6)
    ax.annotate('', xy=(3.3, 4.3), xytext=(2.9, 4.3), arrowprops=arrow_props)
    ax.annotate('', xy=(6.2, 4.3), xytext=(5.8, 4.3), arrowprops=arrow_props)
    ax.annotate('', xy=(9.2, 4.3), xytext=(8.8, 4.3), arrowprops=arrow_props)

    # Bottom Stage: Event Telemetry & SOC Dashboard
    bottom_box = patches.FancyBboxPatch((0.5, 0.4), 11.0, 2.3, boxstyle="round,pad=0.1",
                                        fc='#F7FAFC', ec='#A0AEC0', lw=1.5)
    ax.add_patch(bottom_box)
    ax.text(6.0, 2.45, "5. Telemetry, Persistence, and Cybersecurity SOC Dashboard (Streamlit)",
            color=navy, fontsize=11, fontweight='bold', ha='center')

    # SOC Tabs inside bottom box
    tab_w = 2.4
    tab_h = 1.6
    y_tab = 0.65

    tabs = [
        ("Live Triage Console", "• Real-time classification\n• Confidence score meters\n• Automated vs. abstained flows\n• High-risk alert highlights"),
        ("Model Performance", "• Validation vs. test metrics\n• Macro-F1 & selective accuracy\n• Latency percentiles (P50/P95)\n• Resource utilization monitors"),
        ("Distribution Drift", "• Direct vs. tunnel shift\n• Environment shift tracker\n• Packet size histogram drift\n• Continuous concept audit"),
        ("Event Log & Audit", "• SQLite persistence table\n• JSON event bus schemas\n• Zero-payload verification\n• Cryptographic SHA-256 hashes")
    ]

    for idx, (tab_title, tab_desc) in enumerate(tabs):
        x_tab = 0.8 + idx * 2.7
        t_box = patches.FancyBboxPatch((x_tab, y_tab), tab_w, tab_h, boxstyle="round,pad=0.08",
                                       fc='white', ec=border_blue, lw=1.0)
        ax.add_patch(t_box)
        ax.text(x_tab + tab_w/2, y_tab + tab_h - 0.22, tab_title,
                color=blue, fontsize=9, fontweight='bold', ha='center')
        ax.text(x_tab + 0.12, y_tab + tab_h - 0.42, tab_desc,
                color=dark_gray, fontsize=7.5, ha='left', va='top', linespacing=1.3)

    # Arrow from selective gating down to SOC
    ax.annotate('', xy=(6.0, 2.7), xytext=(10.35, 3.2),
                arrowprops=dict(facecolor=navy, edgecolor='none', width=1.8, headwidth=6, headlength=6))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Diagram saved to: {output_path}")

if __name__ == '__main__':
    create_realtime_pipeline_diagram('submission/fig_soc_architecture.png')
