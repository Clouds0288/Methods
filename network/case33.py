from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
S_base = 10.0  # MVA，IEEE 33 支路欧姆值换算到 p.u. 的功率基准
V_base_kv = 12.66  # kV，IEEE 33 标准电压基准
Z_base = V_base_kv**2 / S_base  # ohm，三相线电压基准下的阻抗基准
V_min, V_max = 0.90, 1.05  # IEEE 33 原始负荷下电压较低，第一版显式采用 0.90 下限
hours = range(24)

bus_df = pd.DataFrame([(1, "slack")] + [(b, "PQ") for b in range(2, 34)], columns=["bus", "type"])

branch_ohm = [
    ("L01_02", 1, 2, 0.0922, 0.0470, 10.0),
    ("L02_03", 2, 3, 0.4930, 0.2511, 10.0),
    ("L03_04", 3, 4, 0.3660, 0.1864, 10.0),
    ("L04_05", 4, 5, 0.3811, 0.1941, 10.0),
    ("L05_06", 5, 6, 0.8190, 0.7070, 10.0),
    ("L06_07", 6, 7, 0.1872, 0.6188, 10.0),
    ("L07_08", 7, 8, 1.7114, 1.2351, 10.0),
    ("L08_09", 8, 9, 1.0300, 0.7400, 10.0),
    ("L09_10", 9, 10, 1.0440, 0.7400, 10.0),
    ("L10_11", 10, 11, 0.1966, 0.0650, 10.0),
    ("L11_12", 11, 12, 0.3744, 0.1238, 10.0),
    ("L12_13", 12, 13, 1.4680, 1.1550, 10.0),
    ("L13_14", 13, 14, 0.5416, 0.7129, 10.0),
    ("L14_15", 14, 15, 0.5910, 0.5260, 10.0),
    ("L15_16", 15, 16, 0.7463, 0.5450, 10.0),
    ("L16_17", 16, 17, 1.2890, 1.7210, 10.0),
    ("L17_18", 17, 18, 0.7320, 0.5740, 10.0),
    ("L02_19", 2, 19, 0.1640, 0.1565, 10.0),
    ("L19_20", 19, 20, 1.5042, 1.3554, 10.0),
    ("L20_21", 20, 21, 0.4095, 0.4784, 10.0),
    ("L21_22", 21, 22, 0.7089, 0.9373, 10.0),
    ("L03_23", 3, 23, 0.4512, 0.3083, 10.0),
    ("L23_24", 23, 24, 0.8980, 0.7091, 10.0),
    ("L24_25", 24, 25, 0.8960, 0.7011, 10.0),
    ("L06_26", 6, 26, 0.2030, 0.1034, 10.0),
    ("L26_27", 26, 27, 0.2842, 0.1447, 10.0),
    ("L27_28", 27, 28, 1.0590, 0.9337, 10.0),
    ("L28_29", 28, 29, 0.8042, 0.7006, 10.0),
    ("L29_30", 29, 30, 0.5075, 0.2585, 10.0),
    ("L30_31", 30, 31, 0.9744, 0.9630, 10.0),
    ("L31_32", 31, 32, 0.3105, 0.3619, 10.0),
    ("L32_33", 32, 33, 0.3410, 0.5302, 10.0),
]
branch_df = pd.DataFrame(
    [(br, f, t, r / Z_base, x / Z_base, smax) for br, f, t, r, x, smax in branch_ohm],
    columns=["branch", "from_bus", "to_bus", "r_pu", "x_pu", "s_max_mva"],
)

load_base_kw_kvar = [
    (2, 100, 60), (3, 90, 40), (4, 120, 80), (5, 60, 30), (6, 60, 20), (7, 200, 100),
    (8, 200, 100), (9, 60, 20), (10, 60, 20), (11, 45, 30), (12, 60, 35), (13, 60, 35),
    (14, 120, 80), (15, 60, 10), (16, 60, 20), (17, 60, 20), (18, 90, 40), (19, 90, 40),
    (20, 90, 40), (21, 90, 40), (22, 90, 40), (23, 90, 50), (24, 420, 200), (25, 420, 200),
    (26, 60, 25), (27, 60, 25), (28, 60, 20), (29, 120, 70), (30, 200, 600), (31, 150, 70),
    (32, 210, 100), (33, 60, 40),
]
load_base_df = pd.DataFrame(
    [(bus, "load", p / 1000, q / 1000) for bus, p, q in load_base_kw_kvar],
    columns=["bus", "class", "p_base_mw", "q_base_mvar"],
)

load_profile = [0.55, 0.50, 0.48, 0.47, 0.50, 0.60, 0.72, 0.82, 0.90, 0.96, 1.00, 0.98, 0.95, 0.93, 0.92, 0.94, 1.00, 1.08, 1.12, 1.08, 1.00, 0.88, 0.72, 0.60]  # 代表日逐小时负荷倍率
load_ts = pd.DataFrame(
    [(h, bus, p * load_profile[h], q * load_profile[h]) for bus, _, p, q in load_base_df.itertuples(index=False, name=None) for h in hours],
    columns=["hour", "bus", "p_mw", "q_mvar"],
)
p_load_mw = load_ts.pivot(index="hour", columns="bus", values="p_mw")
q_load_mvar = load_ts.pivot(index="hour", columns="bus", values="q_mvar")

buses = bus_df["bus"].tolist()
branches = branch_df["branch"].tolist()
parent = dict(zip(branch_df["to_bus"], branch_df["branch"]))
children = {b: branch_df.loc[branch_df["from_bus"] == b, "branch"].tolist() for b in buses}
slack_branch = branch_df.loc[branch_df["from_bus"] == 1, "branch"].iloc[0]

dg_buses = [18, 33]  # 可调 DG 节点
p_dg_max = {18: 0.8, 33: 0.8}  # MW
q_grid_max = 5.0  # MVAr


if __name__ == "__main__":
    print(bus_df.to_string(index=False))
    print(branch_df.head().round(6).to_string(index=False))
    print(load_ts.head().round(6).to_string(index=False))
