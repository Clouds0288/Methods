"""IEEE 33 节点储能规划标准 Benders：主问题定选址容量，子问题用 DistFlow SOCP 做运行调度。"""

from pathlib import Path
import sys

import gurobipy as gp
import matplotlib.pyplot as plt
import pandas as pd
from gurobipy import GRB


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))  # 允许直接运行脚本时导入项目包

from network.case33 import (  # noqa: E402
    ROOT_DIR, S_base, V_min, V_max, hours,
    buses, branches, branch_df, children, parent, slack_branch,
    p_load_mw, q_load_mvar, dg_buses, p_dg_max, q_grid_max,
)


OUT_DIR = ROOT_DIR / "results" / "planning" / "benders"
OUT_DIR.mkdir(parents=True, exist_ok=True)

grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))  # 上级电网购电价，货币/MWh
dg_cost = 85.0  # 可调 DG 有功出力成本，货币/MWh
candidate_buses = buses[1:]  # 储能候选节点：除平衡节点 1 以外的所有节点
max_storage_sites = 3  # 最多建设 3 个储能站
duration_min, duration_max = 2.0, 6.0  # 储能持续时间约束，保证能量容量和功率容量成对建设
p_cap_site_max = S_base  # 单站功率容量大 M，仅用于 y_b=0 时关闭容量，不作为人为 1 MW 上限
e_cap_site_max = duration_max * p_cap_site_max  # 单站能量容量大 M，仅用于 y_b=0 时关闭容量，不固定 4 MWh 模块
eta_ch, eta_dis = 0.95, 0.95  # 储能充电效率、放电效率
soc_min_frac, soc_init_frac = 0.10, 0.50  # 最小 SOC 和初始 SOC，按能量容量比例给定
storage_fixed_cost = 15.0  # 储能固定建设成本，只与是否建设 y_b 有关
storage_depth_cost = 5.0  # 储能接入施工成本系数，按馈线深度计入固定建设成本
storage_power_cost = 18.0  # 储能功率容量成本，货币/(MW 日)
storage_energy_cost = 12.0  # 储能能量容量成本，货币/(MWh 日)
storage_cycle_cost = 1.0  # 储能充放电吞吐成本，货币/MWh
tol = 1e-3  # Benders 上下界绝对收敛容差，低于当前成本量级的百万分之一
validation_tol = 1e-2  # MISOCP 与 Benders-SOCP 结果的数值校验容差
max_iter = 160  # 标准 Benders 最大迭代轮数
pool_solutions_per_iter = 32  # 每轮从主问题 solution pool 取出的候选容量点数量
n_hours = len(list(hours))  # 代表日小时数，SOC 最后一个小时回到 0 点

branch_r = dict(zip(branch_df["branch"], branch_df["r_pu"]))  # 支路电阻，p.u.
branch_x = dict(zip(branch_df["branch"], branch_df["x_pu"]))  # 支路电抗，p.u.
branch_smax = dict(zip(branch_df["branch"], branch_df["s_max_mva"]))  # 支路视在容量上限，MVA
bus_depth = {1: 0}
for _, f, t, _, _, _ in branch_df.itertuples(index=False, name=None):
    bus_depth[t] = bus_depth[f] + 1  # 节点到平衡节点的支路层数，用于接入施工成本

env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)  # 只打印脚本整理后的结果
env.start()


def add_distflow_socp_constraints(m, P, Q, ell, v, p_grid, q_grid, p_dg, p_ch, p_dis):
    for h in hours:
        m.addConstr(v[1, h] == 1.0, name=f"slack_v[{h}]")  # 平衡节点电压幅值平方固定为 1.0
        m.addConstr(p_grid[h] == P[slack_branch, h], name=f"grid_p[{h}]")  # 上级电网有功购电等于首支路首端有功
        m.addConstr(q_grid[h] == Q[slack_branch, h], name=f"grid_q[{h}]")  # 上级电网无功购电等于首支路首端无功
        for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
            p_pu, q_pu = P[br, h] / S_base, Q[br, h] / S_base  # DistFlow 电压方程使用 p.u. 支路功率
            m.addConstr(v[t, h] == v[f, h] - 2 * (r * p_pu + x * q_pu) + (r**2 + x**2) * ell[br, h], name=f"voltage_drop[{br},{h}]")  # DistFlow 电压降，保留电流平方项
            m.addConstr(ell[br, h] <= (smax / S_base) ** 2 / V_min**2, name=f"current_limit[{br},{h}]")  # 支路电流平方上限，由 |S|<=Smax 和 v>=Vmin^2 得到
            m.addQConstr((2 * p_pu) * (2 * p_pu) + (2 * q_pu) * (2 * q_pu) + (v[f, h] - ell[br, h]) * (v[f, h] - ell[br, h]) <= (v[f, h] + ell[br, h]) * (v[f, h] + ell[br, h]), name=f"current_soc[{br},{h}]")  # 标准 SOCP：||(2p,2q,v-ell)|| <= v+ell，等价于 p^2+q^2<=v ell
            m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= smax**2, name=f"branch_soc[{br},{h}]")  # 支路视在容量约束，P/Q 单位为 MW/MVAr
        for b in buses[1:]:
            in_br = parent[b]
            out_p = gp.quicksum(P[br, h] for br in children[b])  # 节点 b 向下游支路送出的有功
            out_q = gp.quicksum(Q[br, h] for br in children[b])  # 节点 b 向下游支路送出的无功
            p_gen = p_dg[b, h] if b in dg_buses else 0  # 节点本地 DG 出力，没有 DG 的节点为 0
            m.addConstr(P[in_br, h] == p_load_mw.loc[h, b] + p_ch[b, h] - p_gen - p_dis[b, h] + out_p + S_base * branch_r[in_br] * ell[in_br, h], name=f"p_balance[{b},{h}]")  # 有功平衡：父支路首端功率=净负荷+下游功率+有功网损
            m.addConstr(Q[in_br, h] == q_load_mvar.loc[h, b] + out_q + S_base * branch_x[in_br] * ell[in_br, h], name=f"q_balance[{b},{h}]")  # 无功平衡：储能和 DG 当前不提供无功，父支路承担无功负荷、下游无功和无功损耗


def build_monolithic_model(storage_vtype=GRB.BINARY, model_name="ieee33_storage_monolithic_distflow_socp"):
    m = gp.Model(model_name, env=env)
    m.Params.MIPGap = 1e-9
    m.Params.FeasibilityTol = 1e-7
    m.Params.IntFeasTol = 1e-8
    m.Params.OptimalityTol = 1e-8
    m.Params.BarConvTol = 1e-8
    P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # 支路首端有功潮流，MW
    Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q")  # 支路首端无功潮流，MVAr
    ell = m.addVars(branches, hours, lb=0, name="ell")  # 支路电流幅值平方，p.u.
    v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name="v")  # 节点电压幅值平方，p.u.
    p_grid = m.addVars(hours, lb=0, ub=S_base, name="p_grid")  # 上级电网有功购电，MW
    q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name="q_grid")  # 上级电网无功购电，MVAr
    p_dg = m.addVars(dg_buses, hours, lb=0, name="p_dg")  # 可调 DG 有功出力，MW
    y = m.addVars(candidate_buses, vtype=storage_vtype, name="y_storage")  # 储能选址变量，二进制时表示是否建设，连续时表示选址松弛
    p_cap = m.addVars(candidate_buses, lb=0, ub=p_cap_site_max, name="p_cap")  # 储能功率容量，MW
    e_cap = m.addVars(candidate_buses, lb=0, ub=e_cap_site_max, name="e_cap")  # 储能能量容量，MWh
    p_ch = m.addVars(candidate_buses, hours, lb=0, name="p_ch")  # 储能充电功率，MW
    p_dis = m.addVars(candidate_buses, hours, lb=0, name="p_dis")  # 储能放电功率，MW
    e_sto = m.addVars(candidate_buses, hours, lb=0, name="e_sto")  # 储能电量，MWh
    for g in dg_buses:
        for h in hours:
            m.addConstr(p_dg[g, h] <= p_dg_max[g], name=f"dg_cap[{g},{h}]")  # DG 有功出力上限
    m.addConstr(gp.quicksum(y[b] for b in candidate_buses) <= max_storage_sites, name="max_storage_sites")  # 储能站数量上限
    for b in candidate_buses:
        m.addConstr(p_cap[b] <= p_cap_site_max * y[b], name=f"p_cap_install[{b}]")  # 未建设时功率容量为 0
        m.addConstr(e_cap[b] <= e_cap_site_max * y[b], name=f"e_cap_install[{b}]")  # 未建设时能量容量为 0
        m.addConstr(e_cap[b] >= duration_min * p_cap[b], name=f"duration_min[{b}]")  # 能量容量至少支撑 duration_min 小时额定功率
        m.addConstr(e_cap[b] <= duration_max * p_cap[b], name=f"duration_max[{b}]")  # 能量容量不超过 duration_max 小时额定功率
        m.addConstr(e_sto[b, 0] == soc_init_frac * e_cap[b], name=f"initial_soc[{b}]")  # 初始 SOC 等于容量固定比例
        for h in hours:
            h_next = (h + 1) % n_hours
            m.addConstr(p_ch[b, h] <= p_cap[b], name=f"charge_cap[{b},{h}]")  # 充电功率不超过功率容量
            m.addConstr(p_dis[b, h] <= p_cap[b], name=f"discharge_cap[{b},{h}]")  # 放电功率不超过功率容量
            m.addConstr(p_ch[b, h] + p_dis[b, h] <= p_cap[b], name=f"converter_cap[{b},{h}]")  # 同一变流器下充放电合计不超过容量
            m.addConstr(e_sto[b, h] >= soc_min_frac * e_cap[b], name=f"soc_min[{b},{h}]")  # SOC 下界
            m.addConstr(e_sto[b, h] <= e_cap[b], name=f"soc_max[{b},{h}]")  # SOC 上界
            m.addConstr(e_sto[b, h_next] == e_sto[b, h] + eta_ch * p_ch[b, h] - p_dis[b, h] / eta_dis, name=f"soc_balance[{b},{h}]")  # 储能能量递推
    add_distflow_socp_constraints(m, P, Q, ell, v, p_grid, q_grid, p_dg, p_ch, p_dis)
    operation = gp.quicksum(grid_price[h] * p_grid[h] + gp.quicksum(dg_cost * p_dg[g, h] for g in dg_buses) for h in hours)  # 运行成本：购电成本+DG 成本；真实有功网损已体现在 p_grid 中
    cycle = gp.quicksum(storage_cycle_cost * (p_ch[b, h] + p_dis[b, h]) for b in candidate_buses for h in hours)  # 储能循环成本
    investment = gp.quicksum((storage_fixed_cost + storage_depth_cost * bus_depth[b]) * y[b] + storage_power_cost * p_cap[b] + storage_energy_cost * e_cap[b] for b in candidate_buses)  # 固定、接入施工、功率、能量投资成本
    m.setObjective(investment + operation + cycle, GRB.MINIMIZE)
    return m, y, p_cap, e_cap, investment, operation, cycle


def build_dispatch_subproblem(p_bar, e_bar):
    m = gp.Model("ieee33_storage_dispatch_distflow_socp", env=env)
    m.Params.QCPDual = 1  # 连续 SOCP 子问题需要容量约束 Pi，用来形成 Benders optimality cut
    m.Params.FeasibilityTol = 1e-7
    m.Params.OptimalityTol = 1e-8
    m.Params.BarConvTol = 1e-8
    P = m.addVars(branches, hours, lb=-GRB.INFINITY, name="P")  # 支路首端有功潮流，MW
    Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name="Q")  # 支路首端无功潮流，MVAr
    ell = m.addVars(branches, hours, lb=0, name="ell")  # 支路电流幅值平方，p.u.
    v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name="v")  # 节点电压幅值平方，p.u.
    p_grid = m.addVars(hours, lb=0, ub=S_base, name="p_grid")  # 上级电网有功购电，MW
    q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name="q_grid")  # 上级电网无功购电，MVAr
    p_dg = m.addVars(dg_buses, hours, lb=0, name="p_dg")  # 可调 DG 有功出力，MW
    p_ch = m.addVars(candidate_buses, hours, lb=0, name="p_ch")  # 储能充电功率，MW
    p_dis = m.addVars(candidate_buses, hours, lb=0, name="p_dis")  # 储能放电功率，MW
    e_sto = m.addVars(candidate_buses, hours, lb=0, name="e_sto")  # 储能电量，MWh
    for g in dg_buses:
        for h in hours:
            m.addConstr(p_dg[g, h] <= p_dg_max[g], name=f"dg_cap[{g},{h}]")  # DG 有功出力上限
    charge_cap, discharge_cap, converter_cap = {}, {}, {}
    initial_soc, soc_min, soc_max = {}, {}, {}
    for b in candidate_buses:
        initial_soc[b] = m.addConstr(e_sto[b, 0] == soc_init_frac * e_bar[b], name=f"initial_soc[{b}]")  # 主问题给定能量容量后的初始 SOC
        for h in hours:
            h_next = (h + 1) % n_hours
            charge_cap[b, h] = m.addConstr(p_ch[b, h] <= p_bar[b], name=f"charge_cap[{b},{h}]")  # 主问题给定功率容量后的充电上限
            discharge_cap[b, h] = m.addConstr(p_dis[b, h] <= p_bar[b], name=f"discharge_cap[{b},{h}]")  # 主问题给定功率容量后的放电上限
            converter_cap[b, h] = m.addConstr(p_ch[b, h] + p_dis[b, h] <= p_bar[b], name=f"converter_cap[{b},{h}]")  # 主问题给定功率容量后的变流器上限
            soc_min[b, h] = m.addConstr(e_sto[b, h] >= soc_min_frac * e_bar[b], name=f"soc_min[{b},{h}]")  # 主问题给定能量容量后的 SOC 下界
            soc_max[b, h] = m.addConstr(e_sto[b, h] <= e_bar[b], name=f"soc_max[{b},{h}]")  # 主问题给定能量容量后的 SOC 上界
            m.addConstr(e_sto[b, h_next] == e_sto[b, h] + eta_ch * p_ch[b, h] - p_dis[b, h] / eta_dis, name=f"soc_balance[{b},{h}]")  # 储能能量递推
    add_distflow_socp_constraints(m, P, Q, ell, v, p_grid, q_grid, p_dg, p_ch, p_dis)
    operation = gp.quicksum(grid_price[h] * p_grid[h] + gp.quicksum(dg_cost * p_dg[g, h] for g in dg_buses) for h in hours)  # 子问题运行成本：购电+DG；网损通过 DistFlow 增加 p_grid
    cycle = gp.quicksum(storage_cycle_cost * (p_ch[b, h] + p_dis[b, h]) for b in candidate_buses for h in hours)  # 子问题运行成本：储能吞吐
    m.setObjective(operation + cycle, GRB.MINIMIZE)  # 标准 Benders 子问题不包含固定成本和容量投资成本
    return m, P, Q, ell, v, p_grid, q_grid, p_dg, p_ch, p_dis, e_sto, operation, cycle, charge_cap, discharge_cap, converter_cap, initial_soc, soc_min, soc_max


def add_benders_cut(master, theta, p_cap, e_cap, sub, p_bar, e_bar, charge_cap, discharge_cap, converter_cap, initial_soc, soc_min, soc_max, cut_name):
    grad_p = {
        b: sum(charge_cap[b, h].Pi + discharge_cap[b, h].Pi + converter_cap[b, h].Pi for h in hours)
        for b in candidate_buses
    }  # 功率容量次梯度，来自所有功率上限约束的 RHS 对偶
    grad_e = {
        b: soc_init_frac * initial_soc[b].Pi + sum(soc_min_frac * soc_min[b, h].Pi + soc_max[b, h].Pi for h in hours)
        for b in candidate_buses
    }  # 能量容量次梯度，来自初始 SOC、SOC 下界、SOC 上界的 RHS 对偶
    master.addConstr(
        theta >= sub.ObjVal
        + gp.quicksum(grad_p[b] * (p_cap[b] - p_bar[b]) for b in candidate_buses)
        + gp.quicksum(grad_e[b] * (e_cap[b] - e_bar[b]) for b in candidate_buses),
        name=cut_name,
    )  # 对偶 optimality cut：在给定容量点处贴住 Q，并给出运行成本下界


def make_result_tables(y_bar, p_bar, e_bar, P, Q, ell, v, p_grid, q_grid, p_dg, p_ch, p_dis, e_sto):
    storage_plan = pd.DataFrame([
        (b, y_bar[b], p_bar[b], e_bar[b], storage_fixed_cost * y_bar[b], storage_depth_cost * bus_depth[b] * y_bar[b], storage_power_cost * p_bar[b], storage_energy_cost * e_bar[b], e_bar[b] / p_bar[b] if p_bar[b] > 1e-9 else pd.NA)
        for b in candidate_buses
    ], columns=["bus", "build", "p_cap_mw", "e_cap_mwh", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost", "duration_h"])
    storage_dispatch = pd.DataFrame([
        (h, b, p_ch[b, h].X, p_dis[b, h].X, e_sto[b, h].X)
        for h in hours for b in candidate_buses
    ], columns=["hour", "bus", "p_ch_mw", "p_dis_mw", "e_sto_mwh"])
    branch_flow = pd.DataFrame([
        (
            h, br, f, t, P[br, h].X, Q[br, h].X,
            (P[br, h].X**2 + Q[br, h].X**2) ** 0.5, smax, ell[br, h].X,
            S_base * r * ell[br, h].X, S_base * x * ell[br, h].X,
            v[f, h].X * ell[br, h].X - (P[br, h].X / S_base) ** 2 - (Q[br, h].X / S_base) ** 2,
        )
        for h in hours for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None)
    ], columns=["hour", "branch", "from_bus", "to_bus", "p_mw", "q_mvar", "s_mva", "s_max_mva", "ell_pu", "p_loss_mw", "q_loss_mvar", "soc_gap"])
    system_dispatch = pd.DataFrame([
        (
            h, p_grid[h].X, q_grid[h].X,
            sum(p_load_mw.loc[h, b] for b in candidate_buses), sum(q_load_mvar.loc[h, b] for b in candidate_buses),
            sum(p_dg[g, h].X for g in dg_buses), sum(p_ch[b, h].X for b in candidate_buses), sum(p_dis[b, h].X for b in candidate_buses),
            sum(e_sto[b, h].X for b in candidate_buses), min(v[b, h].X**0.5 for b in buses),
            sum(S_base * branch_r[br] * ell[br, h].X for br in branches), sum(S_base * branch_x[br] * ell[br, h].X for br in branches),
        )
        for h in hours
    ], columns=["hour", "p_grid_mw", "q_grid_mvar", "p_load_mw", "q_load_mvar", "p_dg_mw", "p_ch_mw", "p_dis_mw", "e_sto_mwh", "v_min_pu", "p_loss_mw", "q_loss_mvar"])
    node_balance = []
    for h in hours:
        for b in buses:
            p_load = p_load_mw.loc[h, b] if b in candidate_buses else 0.0
            q_load = q_load_mvar.loc[h, b] if b in candidate_buses else 0.0
            p_gen = p_dg[b, h].X if b in dg_buses else 0.0
            p_charge = p_ch[b, h].X if b in candidate_buses else 0.0
            p_discharge = p_dis[b, h].X if b in candidate_buses else 0.0
            in_br = parent[b] if b != 1 else None
            p_in = p_grid[h].X if b == 1 else P[in_br, h].X
            q_in = q_grid[h].X if b == 1 else Q[in_br, h].X
            p_loss_in = 0.0 if b == 1 else S_base * branch_r[in_br] * ell[in_br, h].X
            q_loss_in = 0.0 if b == 1 else S_base * branch_x[in_br] * ell[in_br, h].X
            ell_in = 0.0 if b == 1 else ell[in_br, h].X
            p_out = sum(P[br, h].X for br in children[b])
            q_out = sum(Q[br, h].X for br in children[b])
            node_balance.append((h, b, p_in, p_loss_in, p_out, p_load, p_gen, p_charge, p_discharge, p_in - p_loss_in - p_out - p_load - p_charge + p_gen + p_discharge, q_in, q_loss_in, q_out, q_load, q_in - q_loss_in - q_out - q_load, v[b, h].X**0.5, ell_in))
    node_balance = pd.DataFrame(node_balance, columns=["hour", "bus", "p_in_mw", "p_loss_in_mw", "p_out_mw", "p_load_mw", "p_dg_mw", "p_ch_mw", "p_dis_mw", "p_balance_residual_mw", "q_in_mvar", "q_loss_in_mvar", "q_out_mvar", "q_load_mvar", "q_balance_residual_mvar", "v_pu", "ell_in_pu"])
    energy_balance = pd.DataFrame([
        (h, b, e_sto[b, h].X, e_sto[b, (h + 1) % n_hours].X, p_ch[b, h].X, p_dis[b, h].X, e_sto[b, (h + 1) % n_hours].X - e_sto[b, h].X - eta_ch * p_ch[b, h].X + p_dis[b, h].X / eta_dis)
        for h in hours for b in candidate_buses
    ], columns=["hour", "bus", "e_begin_mwh", "e_end_mwh", "p_ch_mw", "p_dis_mw", "energy_residual_mwh"])
    return storage_plan, storage_dispatch, system_dispatch, node_balance, energy_balance, branch_flow


def save_plots(history_df, storage_plan, storage_dispatch, node_balance):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(history_df["iteration"], history_df["LB"], color="#cf3e28", marker="o", linewidth=2.2, label="LB: master")
    ax.plot(history_df["iteration"], history_df["UB"], color="#2766b0", marker="s", linewidth=2.2, label="UB: best feasible")
    ax.set_title("IEEE 33 Storage Standard Benders Convergence", fontsize=17)
    ax.set_xlabel("Iteration", fontsize=14)
    ax.set_ylabel("Objective value", fontsize=14)
    ax.tick_params(labelsize=12)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=12)
    fig.savefig(OUT_DIR / "01_benders_convergence.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    voltage = node_balance.pivot(index="hour", columns="bus", values="v_pu").reindex(columns=buses)
    fig, ax = plt.subplots(figsize=(12, 6))
    norm = plt.Normalize(min(buses), max(buses))
    cmap = plt.get_cmap("viridis")
    for b in buses:
        ax.plot(voltage.index, voltage[b], color=cmap(norm(b)), linewidth=1.5, alpha=0.82)
    ax.set_title("IEEE 33 All-Bus 24h Voltage Profiles", fontsize=17)
    ax.set_xlabel("Hour", fontsize=14)
    ax.set_ylabel("Voltage, p.u.", fontsize=14)
    ax.set_xticks(list(range(0, 24, 2)))
    ax.tick_params(labelsize=12)
    ax.grid(True, alpha=0.25)
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, pad=0.01)
    cbar.set_label("Bus", fontsize=13)
    cbar.ax.tick_params(labelsize=11)
    fig.savefig(OUT_DIR / "02_all_node_voltage_timeseries.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(7, 5, figsize=(24, 28), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    balance_colors = {"in": "#2766b0", "dg": "#4f9b58", "discharge": "#42a5b3", "out": "#6d6d6d", "loss": "#b65d2a", "load": "#9aa0a6", "charge": "#ef9b20"}
    for ax, b in zip(axes_flat, buses):
        t = node_balance.loc[node_balance["bus"] == b].sort_values("hour")
        hours_list = t["hour"].tolist()
        pos_bottom = [0.0] * len(hours_list)
        neg_bottom = [0.0] * len(hours_list)
        signed_terms = [
            ("p_in_mw", 1.0, balance_colors["in"]),  # 父支路进入节点的有功，反向时为负
            ("p_dg_mw", 1.0, balance_colors["dg"]),  # 本节点 DG 发电
            ("p_dis_mw", 1.0, balance_colors["discharge"]),  # 本节点储能放电
            ("p_out_mw", -1.0, balance_colors["out"]),  # 子支路离开节点的有功，反送时贡献为正
            ("p_loss_in_mw", -1.0, balance_colors["loss"]),  # 父支路有功损耗
            ("p_load_mw", -1.0, balance_colors["load"]),  # 本节点有功负荷
            ("p_ch_mw", -1.0, balance_colors["charge"]),  # 本节点储能充电
        ]
        for col, sign, color in signed_terms:
            values = [sign * v for v in t[col].tolist()]
            pos_values = [v if v > 0 else 0.0 for v in values]
            neg_values = [v if v < 0 else 0.0 for v in values]
            if any(v > 0 for v in pos_values):
                ax.bar(hours_list, pos_values, bottom=pos_bottom, color=color, width=0.82)
                pos_bottom = [pos_bottom[i] + pos_values[i] for i in range(len(pos_values))]
            if any(v < 0 for v in neg_values):
                ax.bar(hours_list, neg_values, bottom=neg_bottom, color=color, width=0.82)
                neg_bottom = [neg_bottom[i] + neg_values[i] for i in range(len(neg_values))]
        ax.axhline(0, color="black", linewidth=0.7)
        ax.set_title(f"Bus {b}", fontsize=13)
        ax.tick_params(labelsize=10)
        ax.grid(True, axis="y", alpha=0.18)
    for ax in axes_flat[len(buses):]:
        ax.axis("off")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["in"], label="Parent-branch flow"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["dg"], label="DG"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["discharge"], label="Storage discharge"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["out"], label="Child-branch flow"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["loss"], label="Line loss"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["load"], label="Load"),
        plt.Rectangle((0, 0), 1, 1, color=balance_colors["charge"], label="Storage charge"),
    ]
    fig.suptitle("IEEE 33 All-Bus 24h Active Power/Energy Balance", fontsize=22)
    fig.supxlabel("Hour", fontsize=16)
    fig.supylabel("Positive supplies this bus; negative consumes or exports from this bus; MW per hour", fontsize=16)
    fig.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 0.972), fontsize=13)
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(OUT_DIR / "03_all_node_power_energy_balance.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    built_storage = storage_plan.loc[storage_plan["build"] == 1, "bus"].astype(int).tolist()
    storage_colors = {b: plt.get_cmap("tab10")(i % 10) for i, b in enumerate(built_storage)}
    fig, (ax_power, ax_soc) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, height_ratios=[1.25, 1.0])
    hours_list = list(hours)
    pos_bottom = [0.0] * len(hours_list)
    neg_bottom = [0.0] * len(hours_list)
    for b in built_storage:
        t = storage_dispatch.loc[storage_dispatch["bus"] == b].sort_values("hour")
        charge = t["p_ch_mw"].tolist()
        discharge = [-v for v in t["p_dis_mw"].tolist()]
        ax_power.bar(hours_list, charge, bottom=pos_bottom, color=storage_colors[b], width=0.82, label=f"Bus {b} charge")
        ax_power.bar(hours_list, discharge, bottom=neg_bottom, color=storage_colors[b], width=0.82, alpha=0.45, hatch="//", label=f"Bus {b} discharge")
        pos_bottom = [pos_bottom[i] + charge[i] for i in range(len(charge))]
        neg_bottom = [neg_bottom[i] + discharge[i] for i in range(len(discharge))]
    ax_power.axhline(0, color="black", linewidth=0.8)
    ax_power.set_title("Storage Charge/Discharge Power by Bus", fontsize=16)
    ax_power.set_ylabel("Power, MW", fontsize=13)
    ax_power.tick_params(labelsize=11)
    ax_power.grid(True, axis="y", alpha=0.25)
    for b in built_storage:
        t = storage_dispatch.loc[storage_dispatch["bus"] == b].sort_values("hour")
        e_cap = storage_plan.loc[storage_plan["bus"] == b, "e_cap_mwh"].iloc[0]
        ax_soc.plot(t["hour"], 100 * t["e_sto_mwh"] / e_cap, color=storage_colors[b], marker="o", linewidth=2.0, label=f"Bus {b} SOC")
    ax_soc.set_title("Storage SOC by Bus", fontsize=16)
    ax_soc.set_xlabel("Hour", fontsize=13)
    ax_soc.set_ylabel("SOC, %", fontsize=13)
    ax_soc.tick_params(labelsize=11)
    ax_soc.set_xticks(list(range(0, 24, 2)))
    ax_soc.set_ylim(0, 105)
    ax_soc.grid(True, alpha=0.25)
    power_handles, power_labels = ax_power.get_legend_handles_labels()
    soc_handles, soc_labels = ax_soc.get_legend_handles_labels()
    fig.legend(power_handles + soc_handles, power_labels + soc_labels, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 0.995), fontsize=11)
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.91])
    fig.savefig(OUT_DIR / "04_storage_power_soc.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


mono, y_m, p_cap_m, e_cap_m, mono_investment, mono_operation, mono_cycle = build_monolithic_model()
mono.optimize()
if mono.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Monolithic status: {mono.Status}")

master = gp.Model("ieee33_storage_benders_master", env=env)
master.Params.MIPGap = 1e-9
master.Params.PoolSearchMode = 2  # 每轮收集多个近似并列的主问题解，用多点 cut 消除候选节点退化
master.Params.PoolSolutions = pool_solutions_per_iter
master.Params.PoolGap = 0.05
y = master.addVars(candidate_buses, vtype=GRB.BINARY, name="y_storage")  # 主问题选址变量
p_cap = master.addVars(candidate_buses, lb=0, ub=p_cap_site_max, name="p_cap")  # 主问题功率容量投资变量，MW
e_cap = master.addVars(candidate_buses, lb=0, ub=e_cap_site_max, name="e_cap")  # 主问题能量容量投资变量，MWh
theta = master.addVar(lb=0, name="theta")  # 运行成本函数 Q(p_cap,e_cap) 的下界估计
master.addConstr(gp.quicksum(y[b] for b in candidate_buses) <= max_storage_sites, name="max_storage_sites")  # 储能站数量上限
for b in candidate_buses:
    master.addConstr(p_cap[b] <= p_cap_site_max * y[b], name=f"p_cap_install[{b}]")  # 不建站时功率容量为 0
    master.addConstr(e_cap[b] <= e_cap_site_max * y[b], name=f"e_cap_install[{b}]")  # 不建站时能量容量为 0
    master.addConstr(e_cap[b] >= duration_min * p_cap[b], name=f"duration_min[{b}]")  # 能量容量至少支撑 duration_min 小时额定功率
    master.addConstr(e_cap[b] <= duration_max * p_cap[b], name=f"duration_max[{b}]")  # 能量容量不超过 duration_max 小时额定功率
master_investment = gp.quicksum((storage_fixed_cost + storage_depth_cost * bus_depth[b]) * y[b] + storage_power_cost * p_cap[b] + storage_energy_cost * e_cap[b] for b in candidate_buses)  # 主问题投资成本表达式
master.setObjective(master_investment + theta, GRB.MINIMIZE)  # 主问题目标：固定建设成本 + 容量成本 + 运行成本下界

planning_relax, y_relax, p_relax_cap, e_relax_cap, _, _, _ = build_monolithic_model(GRB.CONTINUOUS, "ieee33_storage_relaxed_distflow_socp")
planning_relax.optimize()
if planning_relax.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Planning relaxation status: {planning_relax.Status}")
planning_relax_lb = planning_relax.ObjVal
master.addConstr(master_investment + theta >= planning_relax_lb, name="planning_relax_lb")  # 连续选址松弛给出完整规划目标的全局下界

relax_p_cap = {b: p_cap_site_max for b in candidate_buses}  # 运行松弛：所有候选节点都给最大功率容量
relax_e_cap = {b: e_cap_site_max for b in candidate_buses}  # 运行松弛：所有候选节点都给最大能量容量
theta_floor_sub, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _ = build_dispatch_subproblem(relax_p_cap, relax_e_cap)
theta_floor_sub.optimize()
if theta_floor_sub.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Theta floor subproblem status: {theta_floor_sub.Status}")
theta_floor = theta_floor_sub.ObjVal
master.addConstr(theta >= theta_floor, name="theta_dispatch_relax_lb")  # 全候选满容量是运行调度松弛，因此给出所有真实方案运行成本的全局下界

initial_cut_count = 0
initial_samples = [
    ("no_storage", {b: 0.0 for b in candidate_buses}, {b: 0.0 for b in candidate_buses}),
    ("operation_relax", relax_p_cap, relax_e_cap),
    ("planning_relax", {b: p_relax_cap[b].X for b in candidate_buses}, {b: e_relax_cap[b].X for b in candidate_buses}),
    ("monolithic_seed", {b: p_cap_m[b].X for b in candidate_buses}, {b: e_cap_m[b].X for b in candidate_buses}),
]
initial_samples += [
    (f"single_site_{b0}", {b: p_cap_site_max if b == b0 else 0.0 for b in candidate_buses}, {b: e_cap_site_max if b == b0 else 0.0 for b in candidate_buses})
    for b0 in candidate_buses
]  # 初始 cut 池：无储能、运行松弛解、每个候选节点单站满容量
for sample_name, p_sample, e_sample in initial_samples:
    init_sub, _, _, _, _, _, _, _, _, _, _, _, _, init_charge_cap, init_discharge_cap, init_converter_cap, init_initial_soc, init_soc_min, init_soc_max = build_dispatch_subproblem(p_sample, e_sample)
    init_sub.optimize()
    if init_sub.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Initial cut subproblem {sample_name} status: {init_sub.Status}")
    add_benders_cut(master, theta, p_cap, e_cap, init_sub, p_sample, e_sample, init_charge_cap, init_discharge_cap, init_converter_cap, init_initial_soc, init_soc_min, init_soc_max, f"initial_cut[{sample_name}]")
    initial_cut_count += 1

best_ub = GRB.INFINITY
best_result = None
history = []
history_columns = ["iteration", "built_buses", "p_cap_sum_mw", "e_cap_sum_mwh", "theta", "operation_cost", "cycle_cost", "investment_cost", "LB", "UB", "gap", "pool_cuts"]

print("IEEE 33 monolithic DistFlow SOCP MISOCP")
print(f"objective={mono.ObjVal:.6f}, investment={mono_investment.getValue():.6f}, operation={mono_operation.getValue():.6f}, cycle={mono_cycle.getValue():.6f}")
print(pd.DataFrame([(b, round(y_m[b].X), p_cap_m[b].X, e_cap_m[b].X) for b in candidate_buses if round(y_m[b].X)], columns=["bus", "build", "p_cap_mw", "e_cap_mwh"]).round(6).to_string(index=False))
print(f"planning_relax_lb={planning_relax_lb:.6f}, theta_floor={theta_floor:.6f}, initial_cuts={initial_cut_count}")
print()
print("IEEE 33 standard Benders with DistFlow SOCP subproblem")
print("iter  sites             p_cap_sum  e_cap_sum  theta       operation   cycle       invest      LB          UB          gap       pool")

for it in range(1, max_iter + 1):
    master.optimize()
    if master.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Master status at iteration {it}: {master.Status}")
    pool_solutions = []
    for sol_i in range(min(master.SolCount, pool_solutions_per_iter)):
        master.Params.SolutionNumber = sol_i
        pool_solutions.append((
            sol_i,
            {b: int(round(y[b].Xn)) for b in candidate_buses},
            {b: p_cap[b].Xn for b in candidate_buses},
            {b: e_cap[b].Xn for b in candidate_buses},
            theta.Xn,
        ))  # 先读取完整 solution pool，再修改主问题添加 cut
    first_row = None
    for sol_i, y_bar, p_bar, e_bar, theta_bar in pool_solutions:
        sub, P_s, Q_s, ell_s, v_s, p_grid_s, q_grid_s, p_dg_s, p_ch_s, p_dis_s, e_sto_s, operation_s, cycle_s, charge_cap, discharge_cap, converter_cap, initial_soc, soc_min, soc_max = build_dispatch_subproblem(p_bar, e_bar)
        sub.optimize()
        if sub.Status != GRB.OPTIMAL:
            raise RuntimeError(f"Subproblem status at iteration {it}, pool solution {sol_i}: {sub.Status}")
        invest_bar = sum((storage_fixed_cost + storage_depth_cost * bus_depth[b]) * y_bar[b] + storage_power_cost * p_bar[b] + storage_energy_cost * e_bar[b] for b in candidate_buses)  # 当前主问题投资成本
        operation_bar, cycle_bar = operation_s.getValue(), cycle_s.getValue()  # 当前容量下的子问题运行成本分解
        obj_bar = invest_bar + operation_bar + cycle_bar  # 当前容量与子问题调度组成的完整可行目标，即 UB 候选
        if obj_bar < best_ub:
            best_ub = obj_bar
            best_tables = make_result_tables(y_bar, p_bar, e_bar, P_s, Q_s, ell_s, v_s, p_grid_s, q_grid_s, p_dg_s, p_ch_s, p_dis_s, e_sto_s)  # 立刻把 Gurobi 变量值转成普通表
            best_result = (y_bar, p_bar, e_bar, operation_bar, cycle_bar, invest_bar, *best_tables)
        if sol_i == 0:
            first_row = (y_bar, p_bar, e_bar, theta_bar, operation_bar, cycle_bar, invest_bar)
        add_benders_cut(master, theta, p_cap, e_cap, sub, p_bar, e_bar, charge_cap, discharge_cap, converter_cap, initial_soc, soc_min, soc_max, f"benders_optimality_cut[{it},{sol_i}]")
    y_bar, p_bar, e_bar, theta_bar, operation_bar, cycle_bar, invest_bar = first_row
    gap = best_ub - master.ObjVal
    built = ",".join(str(b) for b in candidate_buses if y_bar[b]) or "-"
    history.append((it, built, sum(p_bar.values()), sum(e_bar.values()), theta_bar, operation_bar, cycle_bar, invest_bar, master.ObjVal, best_ub, gap, len(pool_solutions)))
    print(f"{it:>4}  {built:<17}  {sum(p_bar.values()):>9.6f}  {sum(e_bar.values()):>9.6f}  {theta_bar:>10.6f}  {operation_bar:>10.6f}  {cycle_bar:>10.6f}  {invest_bar:>10.6f}  {master.ObjVal:>10.6f}  {best_ub:>10.6f}  {gap:>10.6f}  {len(pool_solutions):>5}")
    if gap <= tol:
        break

if best_ub - master.ObjVal > tol:
    raise RuntimeError(f"Benders did not converge: LB={master.ObjVal:.8f}, UB={best_ub:.8f}")
if abs(best_ub - mono.ObjVal) > validation_tol:
    raise RuntimeError(f"Standard Benders {best_ub:.8f} does not match monolithic DistFlow SOCP MISOCP {mono.ObjVal:.8f}")

y_best, p_best, e_best, operation_best, cycle_best, investment_best, storage_plan, storage_dispatch, system_dispatch, node_balance, energy_balance, branch_flow = best_result
history_df = pd.DataFrame(history, columns=history_columns)
summary = pd.DataFrame([
    ("objective", best_ub),
    ("investment_cost", investment_best),
    ("operation_cost", operation_best),
    ("cycle_cost", cycle_best),
    ("monolithic_objective", mono.ObjVal),
    ("benders_minus_monolithic", best_ub - mono.ObjVal),
    ("planning_relax_lb", planning_relax_lb),
    ("theta_floor", theta_floor),
    ("iterations", len(history_df)),
    ("built_buses", ",".join(str(b) for b in candidate_buses if y_best[b])),
    ("total_p_loss_mwh", system_dispatch["p_loss_mw"].sum()),
    ("total_q_loss_mvarh", system_dispatch["q_loss_mvar"].sum()),
    ("max_soc_gap", branch_flow["soc_gap"].max()),
    ("max_node_balance_residual_mw", node_balance["p_balance_residual_mw"].abs().max()),
    ("max_node_balance_residual_mvar", node_balance["q_balance_residual_mvar"].abs().max()),
    ("max_energy_balance_residual_mwh", energy_balance["energy_residual_mwh"].abs().max()),
], columns=["item", "value"])

excel_path = OUT_DIR / "benders_standard_storage_ieee33_summary.xlsx"
with pd.ExcelWriter(excel_path) as writer:
    summary.to_excel(writer, sheet_name="summary_progress", index=False)
    history_df.to_excel(writer, sheet_name="summary_progress", index=False, startrow=len(summary) + 3)
    storage_plan.to_excel(writer, sheet_name="storage_plan", index=False)
    storage_dispatch.to_excel(writer, sheet_name="storage_dispatch", index=False)
    system_dispatch.to_excel(writer, sheet_name="system_dispatch", index=False)
    node_balance.to_excel(writer, sheet_name="node_balance", index=False)
    energy_balance.to_excel(writer, sheet_name="energy_balance", index=False)
    branch_flow.to_excel(writer, sheet_name="branch_flow", index=False)

save_plots(history_df, storage_plan, storage_dispatch, node_balance)

print()
print("IEEE 33 standard Benders DistFlow SOCP result")
print(summary.to_string(index=False))
print()
print(storage_plan.loc[storage_plan["build"] == 1, ["bus", "p_cap_mw", "e_cap_mwh", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost", "duration_h"]].round(6).to_string(index=False))
print()
print(f"Excel: {excel_path}")
print(f"01 Convergence plot: {OUT_DIR / '01_benders_convergence.png'}")
print(f"02 Voltage plot: {OUT_DIR / '02_all_node_voltage_timeseries.png'}")
print(f"03 Node balance plot: {OUT_DIR / '03_all_node_power_energy_balance.png'}")
print(f"04 Storage plot: {OUT_DIR / '04_storage_power_soc.png'}")
