from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR / "results" / "opf"  # 6 节点径向配电网 OPF 实验输出目录，1 号节点为平衡节点
OUTPUT_XLSX = OUT_DIR / "comparison.xlsx"
S_base = 10.0
V_min, V_max = 0.95, 1.05
hours = range(24)

bus_df = pd.DataFrame(
    [(1, "slack"), (2, "PQ"), (3, "PQ"), (4, "PQ"), (5, "PQ"), (6, "PQ")],
    columns=["bus", "type"],
)

branch_df = pd.DataFrame(
    [
        ("L12", 1, 2, 0.010, 0.030, 6.0),
        ("L23", 2, 3, 0.012, 0.025, 4.5),
        ("L34", 3, 4, 0.010, 0.020, 4.0),
        ("L45", 4, 5, 0.011, 0.022, 3.5),
        ("L56", 5, 6, 0.009, 0.018, 3.0),
    ],
    columns=["branch", "from_bus", "to_bus", "r_pu", "x_pu", "s_max_mva"],
)

load_base_df = pd.DataFrame(
    [(2, "res", 0.85), (3, "com", 1.10), (4, "ind", 0.75), (5, "res", 0.60), (6, "com", 0.50)],
    columns=["bus", "class", "p_base_mw"],
)
load_base_df["q_base_mvar"] = load_base_df["p_base_mw"] * np.tan(np.arccos(0.95))


profile = {  # 住宅、商业、工业三类负荷的 24 小时倍率
    "res": [0.45, 0.42, 0.40, 0.39, 0.40, 0.47, 0.60, 0.72, 0.76, 0.70, 0.66, 0.64, 0.62, 0.61, 0.63, 0.69, 0.80, 0.95, 1.00, 0.96, 0.88, 0.75, 0.60, 0.52],
    "com": [0.35, 0.33, 0.32, 0.31, 0.32, 0.38, 0.55, 0.75, 0.90, 0.98, 1.00, 0.98, 0.95, 0.94, 0.93, 0.90, 0.82, 0.70, 0.60, 0.52, 0.48, 0.44, 0.40, 0.37],
    "ind": [0.70, 0.68, 0.66, 0.65, 0.66, 0.72, 0.80, 0.88, 0.92, 0.95, 0.96, 0.97, 0.96, 0.96, 0.95, 0.95, 0.94, 0.90, 0.86, 0.82, 0.78, 0.75, 0.73, 0.71],
}

load_ts = pd.DataFrame(
    [(h, bus, p * profile[c][h], q * profile[c][h]) for _, bus, c, p, q in load_base_df.itertuples(name=None) for h in hours],
    columns=["hour", "bus", "p_mw", "q_mvar"],
)
p_load_mw = load_ts.pivot(index="hour", columns="bus", values="p_mw")
q_load_mvar = load_ts.pivot(index="hour", columns="bus", values="q_mvar")
total_load = load_ts.groupby("hour")[["p_mw", "q_mvar"]].sum()


buses = bus_df["bus"].tolist()
branches = branch_df["branch"].tolist()
parent = dict(zip(branch_df["to_bus"], branch_df["branch"]))
children = {b: branch_df.loc[branch_df["from_bus"] == b, "branch"].tolist() for b in buses}


p_dg_max = 0.8  # DG 接在 6 号节点；当前 DistFlow 对比已移除电容器
q_grid_max = 1.5


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl", mode="w") as writer:
        bus_df.to_excel(writer, sheet_name="bus", index=False)
        branch_df.to_excel(writer, sheet_name="branch", index=False)
        load_base_df.to_excel(writer, sheet_name="load_base", index=False)
        load_ts.to_excel(writer, sheet_name="load_timeseries", index=False)
        total_load.to_excel(writer, sheet_name="total_load")
    print(f"Saved network and load data to {OUTPUT_XLSX}")
