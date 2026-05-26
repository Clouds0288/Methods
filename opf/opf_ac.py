import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB

from network.case6 import (
    OUT_DIR, S_base, V_min, V_max, hours,
    buses, branches, branch_df, p_load_mw, q_load_mvar,
    p_dg_max, q_grid_max,
)
from opf.opf_report import write_sheets


OUT_DIR.mkdir(parents=True, exist_ok=True)
grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))
dg_cost = 85.0


Y = pd.DataFrame(0j, index=buses, columns=buses)
for _, f, t, r, x, _ in branch_df.itertuples(index=False, name=None):
    y = 1 / complex(r, x)  # 线路串联导纳，p.u.
    Y.loc[f, f] += y
    Y.loc[t, t] += y
    Y.loc[f, t] -= y
    Y.loc[t, f] -= y
G, B = Y.map(lambda z: z.real), Y.map(lambda z: z.imag)


def load_at(df, h, b):
    return float(df.loc[h, b]) if b in df.columns else 0.0


def branch_power_expr(ei, fi, ej, fj, g, b):
    ire = g * (ei - ej) - b * (fi - fj)  # 支路电流实部
    iim = b * (ei - ej) + g * (fi - fj)  # 支路电流虚部
    p = ei * ire + fi * iim  # V * conj(I) 的实部，p.u.
    q = fi * ire - ei * iim  # V * conj(I) 的虚部，p.u.
    return p, q


m = gp.Model("ac_opf_6bus")
m.Params.LogToConsole = 0
m.Params.LogFile = str(OUT_DIR / "gurobi_ac.log")
m.Params.NonConvex = 2  # AC OPF 使用非凸二次等式

e = m.addVars(buses, hours, lb=-V_max, ub=V_max, name="e")  # 电压实部，p.u.
fvar = m.addVars(buses, hours, lb=-V_max, ub=V_max, name="f")  # 电压虚部，p.u.
v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name="v")
P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # from->to 首端有功，MW
Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q")  # from->to 首端无功，MVAr
P_rev = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P_rev")  # to->from 反向端有功，MW
Q_rev = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q_rev")  # to->from 反向端无功，MVAr
p_grid = m.addVars(hours, lb=0, ub=6.0, name="p_grid")
q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name="q_grid")
p_dg = m.addVars(hours, lb=0, ub=p_dg_max, name="p_dg")


for h in hours:
    m.addConstr(e[1, h] == 1.0, name=f"slack_e[{h}]")  # 平衡节点电压相角为 0
    m.addConstr(fvar[1, h] == 0.0, name=f"slack_f[{h}]")

    for b in buses:
        m.addQConstr(v[b, h] == e[b, h] * e[b, h] + fvar[b, h] * fvar[b, h], name=f"voltage_mag[{b},{h}]")  # v=|V|^2

        ire = gp.quicksum(G.loc[b, j] * e[j, h] - B.loc[b, j] * fvar[j, h] for j in buses)
        iim = gp.quicksum(B.loc[b, j] * e[j, h] + G.loc[b, j] * fvar[j, h] for j in buses)
        p_net = ((p_grid[h] if b == 1 else 0) + (p_dg[h] if b == 6 else 0) - load_at(p_load_mw, h, b)) / S_base
        q_net = ((q_grid[h] if b == 1 else 0) - load_at(q_load_mvar, h, b)) / S_base
        m.addQConstr(e[b, h] * ire + fvar[b, h] * iim == p_net, name=f"p_balance[{b},{h}]")  # AC 有功平衡
        m.addQConstr(fvar[b, h] * ire - e[b, h] * iim == q_net, name=f"q_balance[{b},{h}]")  # AC 无功平衡

    for br, fb, tb, r, x, smax in branch_df.itertuples(index=False, name=None):
        y = 1 / complex(r, x)
        pf, qf = branch_power_expr(e[fb, h], fvar[fb, h], e[tb, h], fvar[tb, h], y.real, y.imag)
        pt, qt = branch_power_expr(e[tb, h], fvar[tb, h], e[fb, h], fvar[fb, h], y.real, y.imag)
        m.addQConstr(P[br, h] == S_base * pf, name=f"p_from[{br},{h}]")  # 支路首端功率，换回 MW
        m.addQConstr(Q[br, h] == S_base * qf, name=f"q_from[{br},{h}]")
        m.addQConstr(P_rev[br, h] == S_base * pt, name=f"p_to[{br},{h}]")  # 支路末端反向注入，换回 MW
        m.addQConstr(Q_rev[br, h] == S_base * qt, name=f"q_to[{br},{h}]")
        m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= smax**2, name=f"branch_from[{br},{h}]")  # 首端容量
        m.addQConstr(P_rev[br, h] * P_rev[br, h] + Q_rev[br, h] * Q_rev[br, h] <= smax**2, name=f"branch_to[{br},{h}]")  # 末端容量


m.setObjective(gp.quicksum(grid_price[h] * p_grid[h] + dg_cost * p_dg[h] for h in hours), GRB.MINIMIZE)
m.update()
m.write(str(OUT_DIR / "ac_opf_6bus.lp"))
m.optimize()

if m.Status != GRB.OPTIMAL:
    raise RuntimeError(f"AC OPF model status: {m.Status}")

print("Model: ac_opf_6bus")
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
        "v_max_pu": [max(v[b, h].X**0.5 for b in buses) for h in hours],
    },
    index=list(hours),
)
opf.index.name = "hour"

v_pu = pd.DataFrame({b: [v[b, h].X**0.5 for h in hours] for b in buses}, index=list(hours))
v_pu.index.name = "hour"
theta_deg = pd.DataFrame({b: [np.degrees(np.arctan2(fvar[b, h].X, e[b, h].X)) for h in hours] for b in buses}, index=list(hours))
theta_deg.index.name = "hour"

branch_flow = pd.DataFrame(
    [   (h, br, fb, tb,
         P[br, h].X, Q[br, h].X,
         P_rev[br, h].X, Q_rev[br, h].X,
         (P[br, h].X**2 + Q[br, h].X**2) ** 0.5,
         (P_rev[br, h].X**2 + Q_rev[br, h].X**2) ** 0.5,
         smax,
         P[br, h].X + P_rev[br, h].X,
         Q[br, h].X + Q_rev[br, h].X,)
        for h in hours
        for br, fb, tb, _, _, smax in branch_df.itertuples(index=False, name=None)
    ],
    columns=["hour", "branch", "from_bus", "to_bus", "p_from_mw", "q_from_mvar", "p_to_mw", "q_to_mvar", "s_from_mva", "s_to_mva", "s_max_mva", "p_loss_mw", "q_loss_mvar"],)
branch_flow["loading_from_pct"] = 100 * branch_flow["s_from_mva"] / branch_flow["s_max_mva"]
branch_flow["loading_to_pct"] = 100 * branch_flow["s_to_mva"] / branch_flow["s_max_mva"]
branch_flow["loading_pct"] = branch_flow[["loading_from_pct", "loading_to_pct"]].max(axis=1)

model_info = pd.DataFrame(
    [("objective", m.ObjVal), ("variables", m.NumVars), ("linear_constraints", m.NumConstrs), ("quadratic_constraints", m.NumQConstrs), ("runtime_sec", m.Runtime)],
    columns=["metric", "value"],)

write_sheets([
    ("ac_model_info", model_info, False),
    ("ac_dispatch", opf, True),
    ("ac_voltage", v_pu, True),
    ("ac_angle_deg", theta_deg, True),
    ("ac_branch_flow", branch_flow, False),
])

print()
print(opf.head().round(4))
print(f"Minimum voltage: {v_pu.min().min():.4f} pu")
print(f"Maximum branch loading: {branch_flow['loading_pct'].max():.2f}%")
print(f"Total active loss: {branch_flow['p_loss_mw'].sum():.4f} MWh")
