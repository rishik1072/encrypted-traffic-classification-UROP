import pandas as pd
import glob

for f in sorted(glob.glob('results/tables/*.csv')):
    df = pd.read_csv(f)
    print(f"=== {f} ===")
    print("Cols:", df.columns.tolist())
    print(df.head(2))
    print()
