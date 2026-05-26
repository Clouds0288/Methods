import time
from pathlib import Path
import sys

import pandas as pd
import matplotlib.pyplot as plt
import gurobipy as gp
from gurobipy import GRB
from openpyxl import load_workbook

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from network.case6 import (
    ROOT_DIR, S_base, V_min, V_max, hours,
    buses, branches, branch_df, children, parent,
    p_load_mw, q_load_mvar, p_dg_max, q_grid_max,
)


OUT_DIR = ROOT_DIR / "results" / "planning" / "misocp"
OUTPUT_XLSX = OUT_DIR / "planning_comparison.xlsx"
OUT_DIR.mkdir(parents=True, exist_ok=True)

grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))  # 电网购电单价，代表日逐小时给定
dg_cost = 85.0  # DG 有功出力成本

candidate_buses = [3, 4, 5, 6]  # 储能候选安装节点，不考虑平衡节点和近端 2 号节点
max_storage_sites = 1  # 为了突出选址含义，当前算例最多建设一个储能站
p_cap_site_max = 0.8  # 单个候选点最大储能功率容量，MW
e_cap_site_max = 2.4  # 单个候选点最大储能能量容量，MWh
eta_ch, eta_dis = 0.95, 0.95  # 充放电效率
soc_min_frac, soc_init_frac = 0.10, 0.50  # 最小 SOC 和代表日起始 SOC，均按能量容量比例给定

storage_fixed_cost = 15.0  # 储能固定投资日化成本，货币单位/日
storage_power_cost = 18.0  # 功率容量日化成本，货币单位/(MW·日)
storage_energy_cost = 12.0  # 能量容量日化成本，货币单位/(MWh·日)
storage_cycle_cost = 1.0  # 充放电吞吐成本，避免无意义循环，货币单位/MWh


def write_sheets(sheets):
    mode = "a" if OUTPUT_XLSX.exists() else "w"
    kwargs = {"engine": "openpyxl", "mode": mode}
    if mode == "a":
        kwargs["if_sheet_exists"] = "replace"
    with pd.ExcelWriter(OUTPUT_XLSX, **kwargs) as writer:
        for sheet, df, index in sheets:
            df.to_excel(writer, sheet_name=sheet, index=index)


t_start = time.time()
m = gp.Model("storage_siting_misocp_6bus")
m.Params.LogToConsole = 0
m.Params.LogFile = str(OUT_DIR / "gurobi_storage_misocp.log")
m.Params.MIPGap = 1e-9

P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # 支路有功潮流，MW
Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q")  # 支路无功潮流，MVAr
v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name="v")  # 节点电压幅值平方，p.u.
ell = m.addVars(branches, hours, lb=0, name="ell")  # 支路电流幅值平方，p.u.
p_grid = m.addVars(hours, lb=0, ub=6.0, name="p_grid")  # 平衡节点购电有功，MW
q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name="q_grid")  # 平衡节点购电无功，MVAr
p_dg = m.addVars(hours, lb=0, ub=p_dg_max, name="p_dg")  # 6 号节点 DG 有功，MW

y = m.addVars(candidate_buses, vtype=GRB.BINARY, name="y_storage")  # 是否在候选节点建设储能
p_cap = m.addVars(candidate_buses, lb=0, ub=p_cap_site_max, name="p_cap")  # 储能功率容量，MW
e_cap = m.addVars(candidate_buses, lb=0, ub=e_cap_site_max, name="e_cap")  # 储能能量容量，MWh
p_ch = m.addVars(candidate_buses, hours, lb=0, name="p_ch")  # 储能充电功率，MW，作为节点负荷
p_dis = m.addVars(candidate_buses, hours, lb=0, name="p_dis")  # 储能放电功率，MW，作为节点电源
e_sto = m.addVars(candidate_buses, hours, lb=0, name="e_sto")  # 储能电量，MWh

m.addConstr(gp.quicksum(y[b] for b in candidate_buses) <= max_storage_sites, name="max_storage_sites")  # 选址约束：最多建一个储能站

for b in candidate_buses:
    m.addConstr(p_cap[b] <= p_cap_site_max * y[b], name=f"p_cap_install[{b}]")  # 未建设时功率容量必须为 0
    m.addConstr(e_cap[b] <= e_cap_site_max * y[b], name=f"e_cap_install[{b}]")  # 未建设时能量容量必须为 0
    m.addConstr(e_sto[b, 0] == soc_init_frac * e_cap[b], name=f"initial_soc[{b}]")  # 代表日初始 SOC 固定为容量的 50%

    for h in hours:
        h_next = (h + 1) % len(list(hours))
        m.addConstr(p_ch[b, h] <= p_cap[b], name=f"charge_cap[{b},{h}]")  # 充电功率不能超过建设功率容量
        m.addConstr(p_dis[b, h] <= p_cap[b], name=f"discharge_cap[{b},{h}]")  # 放电功率不能超过建设功率容量
        m.addConstr(p_ch[b, h] + p_dis[b, h] <= p_cap[b], name=f"converter_cap[{b},{h}]")  # 连续变流器容量约束，替代充放电互斥二进制
        m.addConstr(e_sto[b, h] >= soc_min_frac * e_cap[b], name=f"soc_min[{b},{h}]")  # 最小 SOC 约束
        m.addConstr(e_sto[b, h] <= e_cap[b], name=f"soc_max[{b},{h}]")  # 最大 SOC 约束
        m.addConstr(e_sto[b, h_next] == e_sto[b, h] + eta_ch * p_ch[b, h] - p_dis[b, h] / eta_dis, name=f"soc_balance[{b},{h}]")  # 储能能量递推，时间步长为 1 h；最后一小时回到 0 点形成循环


for h in hours:
    m.addConstr(v[1, h] == 1.0, name=f"slack_v[{h}]")  # 平衡节点电压固定为 1.0 p.u. squared
    m.addConstr(p_grid[h] == P["L12", h], name=f"grid_p[{h}]")  # 变电站有功注入等于首支路潮流
    m.addConstr(q_grid[h] == Q["L12", h], name=f"grid_q[{h}]")  # 变电站无功注入等于首支路潮流

    for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
        p_pu, q_pu = P[br, h] / S_base, Q[br, h] / S_base
        m.addConstr(v[t, h] == v[f, h] - 2 * (r * p_pu + x * q_pu) + (r**2 + x**2) * ell[br, h], name=f"voltage_drop[{br},{h}]")  # DistFlow 电压降，保留损耗项
        m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= S_base**2 * v[f, h] * ell[br, h], name=f"current_soc[{br},{h}]")  # DistFlow 电流等式的 SOCP 松弛
        m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= smax**2, name=f"branch_soc[{br},{h}]")  # 支路视在容量约束

    for b in buses[1:]:
        in_br = parent[b]
        row = branch_df.loc[branch_df["branch"] == in_br].iloc[0]
        out_p = gp.quicksum(P[br, h] for br in children[b])  # 节点 b 向下游送出的有功
        out_q = gp.quicksum(Q[br, h] for br in children[b])  # 节点 b 向下游送出的无功
        p_gen = p_dg[h] if b == 6 else 0
        sto_dis = p_dis[b, h] if b in candidate_buses else 0
        sto_ch = p_ch[b, h] if b in candidate_buses else 0
        m.addConstr(P[in_br, h] == p_load_mw.loc[h, b] + sto_ch - p_gen - sto_dis + out_p + S_base * row.r_pu * ell[in_br, h], name=f"p_balance[{b},{h}]")  # 储能充电加负荷、放电减负荷
        m.addConstr(Q[in_br, h] == q_load_mvar.loc[h, b] + out_q + S_base * row.x_pu * ell[in_br, h], name=f"q_balance[{b},{h}]")  # 当前储能按单位功率因数运行，不提供无功

operation_cost = gp.quicksum(grid_price[h] * p_grid[h] + dg_cost * p_dg[h] for h in hours)
cycle_cost = gp.quicksum(storage_cycle_cost * (p_ch[b, h] + p_dis[b, h]) for b in candidate_buses for h in hours)
investment_cost = gp.quicksum(storage_fixed_cost * y[b] + storage_power_cost * p_cap[b] + storage_energy_cost * e_cap[b] for b in candidate_buses)
m.setObjective(operation_cost + cycle_cost + investment_cost, GRB.MINIMIZE)
m.update()
m.write(str(OUT_DIR / "storage_misocp_6bus.lp"))
m.optimize()

if m.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Storage planning MISOCP status: {m.Status}")

plan_rows = [
    (
        b,
        round(y[b].X),
        p_cap[b].X,
        e_cap[b].X,
        e_cap[b].X / p_cap[b].X if round(y[b].X) else pd.NA,
        storage_fixed_cost * round(y[b].X),
        storage_power_cost * p_cap[b].X,
        storage_energy_cost * e_cap[b].X,
    )
    for b in candidate_buses
]
storage_plan = pd.DataFrame(plan_rows, columns=["bus", "build", "p_cap_mw", "e_cap_mwh", "duration_h", "fixed_cost", "power_cost", "energy_cost"])

storage_dispatch = pd.DataFrame(
    [
        (h, b, p_ch[b, h].X, p_dis[b, h].X, p_dis[b, h].X - p_ch[b, h].X, e_sto[b, h].X)
        for h in hours
        for b in candidate_buses
    ],
    columns=["hour", "bus", "p_ch_mw", "p_dis_mw", "p_net_dis_mw", "e_mwh"],
)

dispatch = pd.DataFrame(
    {
        "p_grid_mw": [p_grid[h].X for h in hours],
        "p_dg_mw": [p_dg[h].X for h in hours],
        "q_grid_mvar": [q_grid[h].X for h in hours],
        "p_storage_ch_mw": [sum(p_ch[b, h].X for b in candidate_buses) for h in hours],
        "p_storage_dis_mw": [sum(p_dis[b, h].X for b in candidate_buses) for h in hours],
        "e_storage_total_mwh": [sum(e_sto[b, h].X for b in candidate_buses) for h in hours],
        "v_min_pu": [min(v[b, h].X**0.5 for b in buses) for h in hours],
    },
    index=list(hours),
)
dispatch.index.name = "hour"

v_pu = pd.DataFrame({b: [v[b, h].X**0.5 for h in hours] for b in buses}, index=list(hours))
v_pu.index.name = "hour"

branch_flow = pd.DataFrame(
    [
        (
            h, br, f, t,
            P[br, h].X, Q[br, h].X,
            (P[br, h].X**2 + Q[br, h].X**2) ** 0.5,
            smax, ell[br, h].X,
            S_base * r * ell[br, h].X,
            S_base * x * ell[br, h].X,
            v[f, h].X * ell[br, h].X - (P[br, h].X / S_base) ** 2 - (Q[br, h].X / S_base) ** 2,
        )
        for h in hours
        for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None)
    ],
    columns=["hour", "branch", "from_bus", "to_bus", "p_mw", "q_mvar", "s_mva", "s_max_mva", "ell_pu", "p_loss_mw", "q_loss_mvar", "soc_gap"],
)
branch_flow["loading_pct"] = 100 * branch_flow["s_mva"] / branch_flow["s_max_mva"]

summary = pd.DataFrame(
    [
        ("objective", m.ObjVal),
        ("operation_cost", operation_cost.getValue()),
        ("cycle_cost", cycle_cost.getValue()),
        ("investment_cost", investment_cost.getValue()),
        ("built_sites", storage_plan["build"].sum()),
        ("total_p_cap_mw", storage_plan["p_cap_mw"].sum()),
        ("total_e_cap_mwh", storage_plan["e_cap_mwh"].sum()),
        ("total_grid_mwh", dispatch["p_grid_mw"].sum()),
        ("total_dg_mwh", dispatch["p_dg_mw"].sum()),
        ("total_charge_mwh", dispatch["p_storage_ch_mw"].sum()),
        ("total_discharge_mwh", dispatch["p_storage_dis_mw"].sum()),
        ("min_voltage_pu", dispatch["v_min_pu"].min()),
        ("max_branch_loading_pct", branch_flow["loading_pct"].max()),
        ("total_active_loss_mwh", branch_flow["p_loss_mw"].sum()),
        ("max_soc_gap", branch_flow["soc_gap"].abs().max()),
    ],
    columns=["metric", "storage_misocp"],
)

model_info = pd.DataFrame(
    [
        ("model", "storage_siting_misocp_6bus"),
        ("solver", "Gurobi"),
        ("mip_gap", m.MIPGap),
        ("runtime_sec", m.Runtime),
        ("total_wall_time_sec", time.time() - t_start),
        ("variables", m.NumVars),
        ("binary_variables", sum(1 for var in m.getVars() if var.VType == GRB.BINARY)),
        ("linear_constraints", m.NumConstrs),
        ("quadratic_constraints", m.NumQConstrs),
        ("candidate_buses", ",".join(map(str, candidate_buses))),
        ("max_storage_sites", max_storage_sites),
        ("p_cap_site_max_mw", p_cap_site_max),
        ("e_cap_site_max_mwh", e_cap_site_max),
        ("eta_ch", eta_ch),
        ("eta_dis", eta_dis),
    ],
    columns=["metric", "value"],
)

write_sheets([
    ("summary", summary, False),
    ("storage_plan", storage_plan, False),
    ("storage_dispatch", storage_dispatch, False),
    ("planning_dispatch", dispatch, True),
    ("planning_voltage", v_pu, True),
    ("planning_branch_flow", branch_flow, False),
    ("planning_model_info", model_info, False),
])

wb = load_workbook(OUTPUT_XLSX)
ws = wb["summary"]
wb.move_sheet(ws, offset=-wb.index(ws))  # 把规划汇总表移动到第一个 sheet
wb.save(OUTPUT_XLSX)

built_buses = storage_plan.loc[storage_plan["build"] == 1, "bus"].tolist()
fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), dpi=120, sharex=True)
axes[0].plot(hours, dispatch["p_grid_mw"], marker="o", ms=3, label="Grid")
axes[0].plot(hours, dispatch["p_dg_mw"], marker="s", ms=3, label="DG")
axes[0].plot(hours, dispatch["p_storage_ch_mw"], marker="v", ms=3, label="Storage charge")
axes[0].plot(hours, dispatch["p_storage_dis_mw"], marker="^", ms=3, label="Storage discharge")
axes[0].set_ylabel("MW")
axes[0].legend(frameon=False, ncol=4)

for b in built_buses:
    s = storage_dispatch[storage_dispatch["bus"] == b].set_index("hour")
    axes[1].plot(hours, s["e_mwh"], marker="o", ms=3, label=f"Bus {b}")
axes[1].set_ylabel("MWh")
if built_buses:
    axes[1].legend(frameon=False, ncol=4)

axes[2].plot(hours, dispatch["v_min_pu"], marker="o", ms=3, label="Min voltage")
axes[2].axhline(V_min, color="red", ls="--", lw=1)
axes[2].set_ylabel("Voltage / pu")
axes[2].set_xlabel("Hour")
axes[2].set_xticks(list(hours))
axes[2].legend(frameon=False)

for ax in axes:
    ax.grid(ls="--", alpha=0.35)
fig.suptitle("Storage planning MISOCP", y=0.99)
fig.tight_layout()
fig.savefig(OUT_DIR / "storage_planning.png", dpi=200, bbox_inches="tight")
plt.close(fig)

print("Model: storage_siting_misocp_6bus")
print(f"Objective: {m.ObjVal:.4f}")
print(f"Operation cost: {operation_cost.getValue():.4f}")
print(f"Investment cost: {investment_cost.getValue():.4f}")
print(f"Cycle cost: {cycle_cost.getValue():.4f}")
print(f"Variables: {m.NumVars}, binaries: {sum(1 for var in m.getVars() if var.VType == GRB.BINARY)}")
print(f"Linear constraints: {m.NumConstrs}")
print(f"Quadratic constraints: {m.NumQConstrs}")

print("\nStorage plan")
print(storage_plan.round(4).to_string(index=False))

print("\nHourly system dispatch")
print(dispatch.round(4).to_string())

print("\nBuilt-storage dispatch")
if built_buses:
    print(storage_dispatch.loc[storage_dispatch["bus"].isin(built_buses)].round(4).to_string(index=False))
else:
    print("No storage built.")

print(f"Minimum voltage: {dispatch['v_min_pu'].min():.4f} pu")
print(f"Maximum branch loading: {branch_flow['loading_pct'].max():.2f}%")
print(f"Total active loss: {branch_flow['p_loss_mw'].sum():.4f} MWh")
