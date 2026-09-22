import pandas as pd

for name in ["feature_family_ablation_research", "feature_count_tradeoff_research", "research_generalization_scorecard", "research_early_prediction", "research_selective_prediction", "research_calibration", "research_latency", "research_resource_usage", "research_model_footprint"]:
    df = pd.read_csv(f"results/tables/{name}.csv")
    print(f"=== {name} ({len(df)} rows) ===")
    print("Columns:", df.columns.tolist())
    print(df.head(2))
    print()
