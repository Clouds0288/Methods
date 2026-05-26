import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB

from network.case6 import (
    OUT_DIR, S_base, hours,
    buses, branches, branch_df, children,
    p_load_mw, p_dg_max,
)
from opf.opf_report import write_sheets


OUT_DIR.mkdir(parents=True, exist_ok=True)
grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))
dg_cost = 85.0
incoming = {b: branch_df.loc[branch_df["to_bus"] == b, "branch"].tolist() for b in buses}


def load_at(h, b):
    return float(p_load_mw.loc[h, b]) if b in p_load_mw.columns else 0.0


m = gp.Model("dcflow_opf_6bus")
m.Params.LogToConsole = 0
m.Params.LogFile = str(OUT_DIR / "gurobi_dcflow.log")

theta = m.addVars(buses, hours, lb=-GRB.INFINITY, name="theta")  # 节点电压相角，rad，DC 潮流只保留相角
P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # 支路有功潮流，MW
p_grid = m.addVars(hours, lb=0, ub=6.0, name="p_grid")
p_dg = m.addVars(hours, lb=0, ub=p_dg_max, name="p_dg")


for h in hours:
    m.addConstr(theta[1, h] == 0.0, name=f"slack_theta[{h}]")  # 平衡节点相角参考

    for br, f, t, _, x, smax in branch_df.itertuples(index=False, name=None):
        m.addConstr(P[br, h] == S_base * (theta[f, h] - theta[t, h]) / x, name=f"dc_flow[{br},{h}]")  # P=S_base*(theta_i-theta_j)/x
        m.addConstr(P[br, h] <= smax, name=f"branch_ub[{br},{h}]")  # DC 只用有功潮流近似容量
        m.addConstr(P[br, h] >= -smax, name=f"branch_lb[{br},{h}]")

    for b in buses:
        out_p = gp.quicksum(P[br, h] for br in children[b])  # 从节点 b 送往下游的有功
        in_p = gp.quicksum(P[br, h] for br in incoming[b])  # 从上游流入节点 b 的有功
        p_gen = p_dg[h] if b == 6 else 0
        p_slack = p_grid[h] if b == 1 else 0
        m.addConstr(p_slack + p_gen - load_at(h, b) == out_p - in_p, name=f"p_balance[{b},{h}]")  # DC 有功节点平衡


m.setObjective(gp.quicksum(grid_price[h] * p_grid[h] + dg_cost * p_dg[h] for h in hours), GRB.MINIMIZE)
m.update()
m.write(str(OUT_DIR / "dcflow_opf_6bus.lp"))
m.optimize()

if m.Status != GRB.OPTIMAL:
    raise RuntimeError(f"DC flow model status: {m.Status}")

print("Model: dcflow_opf_6bus")
print(f"Objective: {m.ObjVal:.4f}")
print(f"Variables: {m.NumVars}")
print(f"Linear constraints: {m.NumConstrs}")
print(f"Quadratic constraints: {m.NumQConstrs}")


opf = pd.DataFrame(
    {
        "p_grid_mw": [p_grid[h].X for h in hours],
        "p_dg_mw": [p_dg[h].X for h in hours],
        "q_grid_mvar": [np.nan for _ in hours],
        "v_min_pu": [1.0 for _ in hours],
    },
    index=list(hours),
)
opf.index.name = "hour"

theta_deg = pd.DataFrame({b: [np.degrees(theta[b, h].X) for h in hours] for b in buses}, index=list(hours))
theta_deg.index.name = "hour"

branch_flow = pd.DataFrame(
    [   (h, br, f, t, P[br, h].X, abs(P[br, h].X), smax)
        for h in hours
        for br, f, t, _, _, smax in branch_df.itertuples(index=False, name=None)
    ],
    columns=["hour", "branch", "from_bus", "to_bus", "p_mw", "s_mva_approx", "s_max_mva"],)
branch_flow["loading_pct"] = 100 * branch_flow["s_mva_approx"] / branch_flow["s_max_mva"]

model_info = pd.DataFrame(
    [("objective", m.ObjVal), ("variables", m.NumVars), ("linear_constraints", m.NumConstrs), ("quadratic_constraints", m.NumQConstrs)],
    columns=["metric", "value"],)

write_sheets([
    ("dc_model_info", model_info, False),
    ("dc_dispatch", opf, True),
    ("dc_angle_deg", theta_deg, True),
    ("dc_branch_flow", branch_flow, False),
])

print()
print(opf.head().round(4))
print(f"Maximum branch loading: {branch_flow['loading_pct'].max():.2f}%")
