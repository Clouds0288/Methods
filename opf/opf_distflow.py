import pandas as pd
import gurobipy as gp
from gurobipy import GRB

from network.case6 import (
    OUT_DIR, S_base, V_min, V_max, hours,
    buses, branches, branch_df, children, parent,
    p_load_mw, q_load_mvar, p_dg_max, q_grid_max,
)
from opf.opf_report import write_sheets


OUT_DIR.mkdir(parents=True, exist_ok=True)
grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))
dg_cost = 85.0


m = gp.Model("distflow_opf_6bus")
m.Params.LogToConsole = 0
m.Params.LogFile = str(OUT_DIR / "gurobi_distflow.log")

P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # 支路有功潮流，保留 MW，进入 p.u. 公式时再除以 S_base
Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q")  # 支路无功潮流，保留 MVAr，进入 p.u. 公式时再除以 S_base
v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name="v")
ell = m.addVars(branches, hours, lb=0, name="ell")  # 支路电流幅值平方，p.u.
p_grid = m.addVars(hours, lb=0, ub=6.0, name="p_grid")
q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name="q_grid")
p_dg = m.addVars(hours, lb=0, ub=p_dg_max, name="p_dg")


for h in hours:
    m.addConstr(v[1, h] == 1.0, name=f"slack_v[{h}]")  # 平衡节点电压固定为 1.0 p.u. squared
    m.addConstr(p_grid[h] == P["L12", h], name=f"grid_p[{h}]")  # 变电站有功注入等于首支路 L12 有功潮流
    m.addConstr(q_grid[h] == Q["L12", h], name=f"grid_q[{h}]")  # 变电站无功注入等于首支路 L12 无功潮流

    for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
        p_pu, q_pu = P[br, h] / S_base, Q[br, h] / S_base  # p.u. 功率用于 DistFlow 电压方程
        m.addConstr(v[t, h] == v[f, h] - 2 * (r * p_pu + x * q_pu) + (r**2 + x**2) * ell[br, h], name=f"voltage_drop[{br},{h}]")  # 保留一阶压降和电流平方项
        m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= S_base**2 * v[f, h] * ell[br, h], name=f"current_soc[{br},{h}]")  # 等价于 p_pu^2+q_pu^2 <= v*ell
        m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= smax**2, name=f"branch_soc[{br},{h}]")  # 支路容量为 MVA，与 MW/MVAr 的 P/Q 匹配，无需再转 p.u.

    for b in buses[1:]:
        in_br = parent[b]
        row = branch_df.loc[branch_df["branch"] == in_br].iloc[0]
        out_p = gp.quicksum(P[br, h] for br in children[b])  # 下游支路有功需求
        out_q = gp.quicksum(Q[br, h] for br in children[b])  # 下游支路无功需求
        p_gen = p_dg[h] if b == 6 else 0
        m.addConstr(P[in_br, h] == p_load_mw.loc[h, b] - p_gen + out_p + S_base * row.r_pu * ell[in_br, h], name=f"p_balance[{b},{h}]")  # 含有功损耗的径向平衡
        m.addConstr(Q[in_br, h] == q_load_mvar.loc[h, b] + out_q + S_base * row.x_pu * ell[in_br, h], name=f"q_balance[{b},{h}]")  # 含无功损耗的径向平衡


m.setObjective(gp.quicksum(grid_price[h] * p_grid[h] + dg_cost * p_dg[h] for h in hours), GRB.MINIMIZE)
m.update()
m.write(str(OUT_DIR / "distflow_opf_6bus.lp"))
m.optimize()

if m.Status != GRB.OPTIMAL:
    raise RuntimeError(f"DistFlow model status: {m.Status}")

print("Model: distflow_opf_6bus")
print(f"Objective: {m.ObjVal:.4f}")
print(f"Variables: {m.NumVars}")
print(f"Linear constraints: {m.NumConstrs}")
print(f"Quadratic constraints: {m.NumQConstrs}")


opf = pd.DataFrame(
    {
        "p_grid_mw": [p_grid[h].X for h in hours],
        "p_dg_mw": [p_dg[h].X for h in hours],
        "q_grid_mvar": [q_grid[h].X for h in hours],
        "v_min_pu": [min(v[b, h].X**0.5 for b in buses) for h in hours],
    },
    index=list(hours),
)
opf.index.name = "hour"

v_pu = pd.DataFrame({b: [v[b, h].X**0.5 for h in hours] for b in buses}, index=list(hours))
v_pu.index.name = "hour"

branch_flow = pd.DataFrame(
    [   (h, br, f, t,
         P[br, h].X, Q[br, h].X,
         P[br, h].X / S_base, Q[br, h].X / S_base,
         (P[br, h].X**2 + Q[br, h].X**2) ** 0.5,
         smax, ell[br, h].X,
         S_base * r * ell[br, h].X,
         S_base * x * ell[br, h].X,
         v[f, h].X * ell[br, h].X - (P[br, h].X / S_base) ** 2 - (Q[br, h].X / S_base) ** 2,)
        for h in hours
        for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None)
    ],
    columns=["hour", "branch", "from_bus", "to_bus", "p_mw", "q_mvar", "p_pu", "q_pu", "s_mva", "s_max_mva", "ell_pu", "p_loss_mw", "q_loss_mvar", "soc_gap"],)
branch_flow["loading_pct"] = 100 * branch_flow["s_mva"] / branch_flow["s_max_mva"]

model_info = pd.DataFrame([("objective", m.ObjVal), ("variables", m.NumVars), ("linear_constraints", m.NumConstrs), ("quadratic_constraints", m.NumQConstrs)], columns=["metric", "value"],)

write_sheets([
    ("dist_model_info", model_info, False),
    ("dist_dispatch", opf, True),
    ("dist_voltage", v_pu, True),
    ("dist_branch_flow", branch_flow, False),
])

print()
print(opf.head().round(4))
print(f"Minimum voltage: {v_pu.min().min():.4f} pu")
print(f"Maximum branch loading: {branch_flow['loading_pct'].max():.2f}%")
print(f"Total active loss: {branch_flow['p_loss_mw'].sum():.4f} MWh")
print(f"Maximum SOC gap: {branch_flow['soc_gap'].abs().max():.2e}")
