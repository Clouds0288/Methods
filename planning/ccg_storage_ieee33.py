"""IEEE 33 节点教学版 CCG：有限场景鲁棒储能规划。

算法主线：
1. 主问题只放少数已激活场景，决定储能选址 y、功率容量 p_cap、能量容量 e_cap 和最坏运行成本 eta。
2. oracle 固定当前储能规划，对完整候选场景逐个求运行 SOCP，找运行成本最大的最坏场景。
3. 若最坏场景成本已经被 eta 覆盖，则收敛；否则把该场景加入主问题，下一轮再求。
"""

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


OUT_DIR = ROOT_DIR / "results" / "planning" / "ccg"
OUT_DIR.mkdir(parents=True, exist_ok=True)

grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))  # 基准上级电网购电价，货币/MWh
dg_cost = 85.0  # 可调 DG 有功出力成本，货币/MWh
candidate_buses = buses[1:]  # 储能候选节点：除平衡节点以外的所有节点
max_storage_sites = 3  # 最多建设 3 个储能站
duration_min, duration_max = 2.0, 6.0  # 储能持续时间约束
p_cap_site_max = S_base  # 容量关闭用功率大 M，不作为人为设备上限
e_cap_site_max = duration_max * p_cap_site_max  # 容量关闭用能量大 M
eta_ch, eta_dis = 0.95, 0.95  # 储能充放电效率
soc_min_frac, soc_init_frac = 0.10, 0.50  # 最小 SOC 和初始 SOC，均按能量容量比例
storage_fixed_cost = 15.0  # 储能建站固定成本
storage_depth_cost = 5.0  # 储能接入施工成本系数，按馈线深度计
storage_power_cost = 18.0  # 储能功率容量成本，货币/(MW 日)
storage_energy_cost = 12.0  # 储能能量容量成本，货币/(MWh 日)
storage_cycle_cost = 1.0  # 储能充放电吞吐成本，货币/MWh
tol = 1e-2  # CCG 场景违反量收敛容差，教学版 MISOCP 用 0.01 成本单位判断场景已覆盖
max_iter = 12  # 有限场景 CCG 最大迭代轮数，场景数为 6，理论上不需要超过场景数太多
n_hours = len(list(hours))  # 代表日小时数，SOC 按 24 小时循环

branch_r = dict(zip(branch_df["branch"], branch_df["r_pu"]))  # 支路电阻，p.u.
branch_x = dict(zip(branch_df["branch"], branch_df["x_pu"]))  # 支路电抗，p.u.
bus_depth = {1: 0}
for _, f, t, _, _, _ in branch_df.itertuples(index=False, name=None):
    bus_depth[t] = bus_depth[f] + 1  # 节点到平衡节点的支路层数，用于接入施工成本

env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)  # 教学脚本只打印整理后的 CCG 过程
env.start()


def build_scenario_pool():
    """显式构造有限不确定场景集 Xi；教学版不用随机数，方便复现实验。"""
    rows = [
        (0, "base", "基准代表日"),
        (1, "evening_peak", "晚高峰高负荷、低 DG、高电价"),
        (2, "heavy_load", "全天重负荷"),
        (3, "low_dg_high_price", "DG 不足且电价偏高"),
        (4, "midday_reverse", "中午低负荷、高 DG，可观察反向潮流"),
        (5, "night_load", "夜间负荷偏高"),
    ]
    scenario_pool = pd.DataFrame(rows, columns=["scenario_id", "scenario", "description"])
    multiplier_rows = []
    for scenario_id, scenario, _ in rows:
        for h in hours:
            load_mult, dg_mult, price_mult = 1.0, 1.0, 1.0  # 默认等于基准场景；下面按场景名改倍率
            if scenario == "evening_peak":
                load_mult = 1.18 if 17 <= h <= 20 else 1.05  # 晚高峰负荷更高，其余小时略高
                dg_mult = 0.70 if 17 <= h <= 20 else 0.90  # 晚高峰 DG 可用出力偏低
                price_mult = 1.25 if 17 <= h <= 20 else 1.00  # 晚高峰电价更高
            if scenario == "heavy_load":
                load_mult, dg_mult, price_mult = 1.12, 0.85, 1.05  # 全天重负荷，是本次运行中被 oracle 找到的最坏场景
            if scenario == "low_dg_high_price":
                load_mult, dg_mult = 1.05, 0.45
                price_mult = 1.20 if 7 <= h <= 20 else 1.00  # 白天电价偏高，DG 却被压低
            if scenario == "midday_reverse":
                load_mult = 0.88 if 10 <= h <= 15 else 1.00  # 中午低负荷
                dg_mult = 1.25 if 10 <= h <= 15 else 1.00  # 中午高 DG，容易出现反向潮流
                price_mult = 0.90 if 10 <= h <= 15 else 1.00  # 中午低电价
            if scenario == "night_load":
                load_mult = 1.15 if 0 <= h <= 6 else 1.00
                dg_mult = 0.90
            multiplier_rows.append((scenario_id, scenario, h, load_mult, dg_mult, price_mult))
    multipliers = pd.DataFrame(multiplier_rows, columns=["scenario_id", "scenario", "hour", "load_mult", "dg_mult", "price_mult"])
    return scenario_pool, multipliers


scenario_pool, scenario_multipliers = build_scenario_pool()
scenario_names = scenario_pool["scenario"].tolist()


def scenario_data(scenario):
    """把场景倍率变成模型真正使用的负荷、DG 上限和电价数据。"""
    multipliers = scenario_multipliers.loc[scenario_multipliers["scenario"] == scenario].set_index("hour")
    p_load = pd.DataFrame([(h, b, p_load_mw.loc[h, b] * multipliers.loc[h, "load_mult"]) for h in hours for b in candidate_buses],columns=["hour", "bus", "p_mw"],).pivot(index="hour", columns="bus", values="p_mw")  # 场景有功负荷
    q_load = pd.DataFrame([(h, b, q_load_mvar.loc[h, b] * multipliers.loc[h, "load_mult"]) for h in hours for b in candidate_buses],columns=["hour", "bus", "q_mvar"],).pivot(index="hour", columns="bus", values="q_mvar")  # 场景无功负荷，与有功使用同一负荷倍率
    dg_cap = {(g, h): p_dg_max[g] * multipliers.loc[h, "dg_mult"] for g in dg_buses for h in hours}  # 场景 DG 可用容量
    price = {h: grid_price[h] * multipliers.loc[h, "price_mult"] for h in hours}  # 场景电价
    return p_load, q_load, dg_cap, price


def investment_expr(y, p_cap, e_cap):
    return gp.quicksum((storage_fixed_cost + storage_depth_cost * bus_depth[b]) * y[b] + storage_power_cost * p_cap[b] + storage_energy_cost * e_cap[b] for b in candidate_buses)  # 第一阶段投资成本


def add_scenario_operation(m, scenario, p_cap, e_cap, tag):
    """向模型添加一个场景的完整运行 SOCP。

    在 CCG 主问题里，p_cap/e_cap 是第一阶段容量变量；在 oracle 里，p_cap/e_cap 是固定容量字典。
    因此同一套运行约束可以同时服务主问题和最坏场景 oracle。
    """
    p_load, q_load, dg_cap, price = scenario_data(scenario)
    P = m.addVars(branches, hours, lb=-GRB.INFINITY, name=f"P[{tag}]")  # 支路首端有功潮流，MW
    Q = m.addVars(branches, hours, lb=-GRB.INFINITY, name=f"Q[{tag}]")  # 支路首端无功潮流，MVAr
    ell = m.addVars(branches, hours, lb=0, name=f"ell[{tag}]")  # 支路电流幅值平方，p.u.
    v = m.addVars(buses, hours, lb=V_min**2, ub=V_max**2, name=f"v[{tag}]")  # 节点电压幅值平方，p.u.
    p_grid = m.addVars(hours, lb=0, ub=S_base, name=f"p_grid[{tag}]")  # 上级电网有功购电，MW
    q_grid = m.addVars(hours, lb=0, ub=q_grid_max, name=f"q_grid[{tag}]")  # 上级电网无功购电，MVAr
    p_dg = m.addVars(dg_buses, hours, lb=0, name=f"p_dg[{tag}]")  # DG 有功出力，MW
    p_ch = m.addVars(candidate_buses, hours, lb=0, name=f"p_ch[{tag}]")  # 储能充电功率，MW
    p_dis = m.addVars(candidate_buses, hours, lb=0, name=f"p_dis[{tag}]")  # 储能放电功率，MW
    e_sto = m.addVars(candidate_buses, hours, lb=0, name=f"e_sto[{tag}]")  # 储能电量，MWh

    for h in hours:
        # 网络约束：每个场景都必须满足 24 小时 DistFlow SOCP 潮流、电压和支路容量。
        m.addConstr(v[1, h] == 1.0, name=f"slack_v[{tag},{h}]")  # 平衡节点电压固定为 1 p.u.
        m.addConstr(p_grid[h] == P[slack_branch, h], name=f"grid_p[{tag},{h}]")  # 首支路有功等于上级购电
        m.addConstr(q_grid[h] == Q[slack_branch, h], name=f"grid_q[{tag},{h}]")  # 首支路无功等于上级购无功
        for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
            p_pu, q_pu = P[br, h] / S_base, Q[br, h] / S_base
            m.addConstr(v[t, h] == v[f, h] - 2 * (r * p_pu + x * q_pu) + (r**2 + x**2) * ell[br, h], name=f"voltage_drop[{tag},{br},{h}]")  # DistFlow 电压降
            m.addConstr(ell[br, h] <= (smax / S_base) ** 2 / V_min**2, name=f"current_limit[{tag},{br},{h}]")  # 电流平方上限
            m.addQConstr((2 * p_pu) * (2 * p_pu) + (2 * q_pu) * (2 * q_pu) + (v[f, h] - ell[br, h]) * (v[f, h] - ell[br, h]) <= (v[f, h] + ell[br, h]) * (v[f, h] + ell[br, h]), name=f"current_soc[{tag},{br},{h}]")  # 电流锥：p^2+q^2<=v*ell
            m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= smax**2, name=f"branch_soc[{tag},{br},{h}]")  # 支路视在容量约束
        for g in dg_buses:
            m.addConstr(p_dg[g, h] <= dg_cap[g, h], name=f"dg_cap[{tag},{g},{h}]")  # 场景 DG 可用容量上限
        for b in candidate_buses:
            # 储能约束：容量由第一阶段决定，运行变量在每个场景、每个小时单独调整。
            h_next = (h + 1) % n_hours
            m.addConstr(p_ch[b, h] <= p_cap[b], name=f"charge_cap[{tag},{b},{h}]")  # 充电功率不超过规划功率容量
            m.addConstr(p_dis[b, h] <= p_cap[b], name=f"discharge_cap[{tag},{b},{h}]")  # 放电功率不超过规划功率容量
            m.addConstr(p_ch[b, h] + p_dis[b, h] <= p_cap[b], name=f"converter_cap[{tag},{b},{h}]")  # 同一变流器下充放电合计不超过功率容量
            m.addConstr(e_sto[b, h] >= soc_min_frac * e_cap[b], name=f"soc_min[{tag},{b},{h}]")  # SOC 下界
            m.addConstr(e_sto[b, h] <= e_cap[b], name=f"soc_max[{tag},{b},{h}]")  # SOC 上界
            m.addConstr(e_sto[b, h_next] == e_sto[b, h] + eta_ch * p_ch[b, h] - p_dis[b, h] / eta_dis, name=f"soc_balance[{tag},{b},{h}]")  # 储能电量递推
            if h == 0:
                m.addConstr(e_sto[b, h] == soc_init_frac * e_cap[b], name=f"initial_soc[{tag},{b}]")  # 初始 SOC 与容量绑定
        for b in candidate_buses:
            # 节点功率平衡：负荷和 DG 上限来自当前场景，储能调度来自本场景运行变量。
            in_br = parent[b]
            out_p = gp.quicksum(P[br, h] for br in children[b])
            out_q = gp.quicksum(Q[br, h] for br in children[b])
            p_gen = p_dg[b, h] if b in dg_buses else 0
            m.addConstr(P[in_br, h] == p_load.loc[h, b] + p_ch[b, h] - p_gen - p_dis[b, h] + out_p + S_base * branch_r[in_br] * ell[in_br, h], name=f"p_balance[{tag},{b},{h}]")  # 节点有功平衡
            m.addConstr(Q[in_br, h] == q_load.loc[h, b] + out_q + S_base * branch_x[in_br] * ell[in_br, h], name=f"q_balance[{tag},{b},{h}]")  # 节点无功平衡

    operation = gp.quicksum(price[h] * p_grid[h] + gp.quicksum(dg_cost * p_dg[g, h] for g in dg_buses) for h in hours)  # 场景运行成本：购电+DG
    cycle = gp.quicksum(storage_cycle_cost * (p_ch[b, h] + p_dis[b, h]) for b in candidate_buses for h in hours)  # 场景储能循环成本
    variables = {"P": P, "Q": Q, "ell": ell, "v": v, "p_grid": p_grid, "q_grid": q_grid, "p_dg": p_dg, "p_ch": p_ch, "p_dis": p_dis, "e_sto": e_sto}
    return operation + cycle, operation, cycle, variables


def build_master(active_scenarios):
    """构造第 k 轮 CCG 主问题 MP(S_k)。"""
    m = gp.Model("ieee33_storage_ccg_master", env=env)
    m.Params.MIPGap = 1e-4
    m.Params.FeasibilityTol = 1e-6
    m.Params.IntFeasTol = 1e-8
    m.Params.OptimalityTol = 1e-8
    m.Params.BarConvTol = 1e-8
    m.Params.BarHomogeneous = 1
    m.Params.MIQCPMethod = 1
    y = m.addVars(candidate_buses, vtype=GRB.BINARY, name="y_storage")  # 第一阶段选址变量
    p_cap = m.addVars(candidate_buses, lb=0, ub=p_cap_site_max, name="p_cap")  # 第一阶段功率容量，MW
    e_cap = m.addVars(candidate_buses, lb=0, ub=e_cap_site_max, name="e_cap")  # 第一阶段能量容量，MWh
    eta = m.addVar(lb=0, name="eta")  # 已加入场景中的最坏运行成本
    m.addConstr(gp.quicksum(y[b] for b in candidate_buses) <= max_storage_sites, name="max_storage_sites")  # 储能站数量上限
    for b in candidate_buses:
        m.addConstr(p_cap[b] <= p_cap_site_max * y[b], name=f"p_cap_install[{b}]")  # 未建站时功率容量关闭
        m.addConstr(e_cap[b] <= e_cap_site_max * y[b], name=f"e_cap_install[{b}]")  # 未建站时能量容量关闭
        m.addConstr(e_cap[b] >= duration_min * p_cap[b], name=f"duration_min[{b}]")  # 能量容量至少支撑最小持续时间
        m.addConstr(e_cap[b] <= duration_max * p_cap[b], name=f"duration_max[{b}]")  # 能量容量不超过最大持续时间
    scene_cost, scene_vars = {}, {}
    for scenario in active_scenarios:
        # CCG 的 column：每加入一个场景，就新增一套该场景的运行变量和运行约束。
        total_cost, operation, cycle, variables = add_scenario_operation(m, scenario, p_cap, e_cap, scenario)
        m.addConstr(eta >= total_cost, name=f"eta_epigraph[{scenario}]")  # CCG 的 constraint：eta 必须不小于该场景运行成本
        scene_cost[scenario] = (total_cost, operation, cycle)
        scene_vars[scenario] = variables
    investment = investment_expr(y, p_cap, e_cap)
    m.setObjective(investment + eta, GRB.MINIMIZE)  # CCG 主问题目标：投资成本 + 已加入场景最坏运行成本
    return m, y, p_cap, e_cap, eta, investment, scene_cost, scene_vars


def solve_operation_for_fixed_plan(scenario, p_bar, e_bar):
    """oracle 的单场景运行子问题：固定当前规划 x^k，只优化运行调度 z_s。"""
    m = gp.Model(f"ieee33_storage_oracle_{scenario}", env=env)
    m.Params.FeasibilityTol = 1e-7
    m.Params.OptimalityTol = 1e-8
    m.Params.BarConvTol = 1e-8
    m.Params.BarHomogeneous = 1
    total_cost, operation, cycle, variables = add_scenario_operation(m, scenario, p_bar, e_bar, scenario)  # 固定当前规划，求单场景运行 SOCP
    m.setObjective(total_cost, GRB.MINIMIZE)
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Oracle scenario {scenario} status: {m.Status}")
    return m, m.ObjVal, operation.getValue(), cycle.getValue(), variables


def read_plan(y, p_cap, e_cap):
    """把主问题解出的第一阶段变量读成普通字典，供 oracle 固定规划使用。"""
    y_bar = {b: int(round(y[b].X)) for b in candidate_buses}
    p_bar = {b: p_cap[b].X for b in candidate_buses}
    e_bar = {b: e_cap[b].X for b in candidate_buses}
    return y_bar, p_bar, e_bar


def make_result_tables(scenario, y_bar, p_bar, e_bar, variables):
    """把最终最坏场景的 Gurobi 变量整理成 Excel 表。"""
    p_load, q_load, _, price = scenario_data(scenario)
    P, Q, ell, v = variables["P"], variables["Q"], variables["ell"], variables["v"]
    p_grid, q_grid, p_dg = variables["p_grid"], variables["q_grid"], variables["p_dg"]
    p_ch, p_dis, e_sto = variables["p_ch"], variables["p_dis"], variables["e_sto"]
    storage_plan = pd.DataFrame([
        (b, y_bar[b], p_bar[b], e_bar[b], storage_fixed_cost * y_bar[b], storage_depth_cost * bus_depth[b] * y_bar[b], storage_power_cost * p_bar[b], storage_energy_cost * e_bar[b], e_bar[b] / p_bar[b] if p_bar[b] > 1e-9 else pd.NA)
        for b in candidate_buses
    ], columns=["bus", "build", "p_cap_mw", "e_cap_mwh", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost", "duration_h"])
    storage_dispatch = pd.DataFrame([
        (scenario, h, b, p_ch[b, h].X, p_dis[b, h].X, e_sto[b, h].X)
        for h in hours for b in candidate_buses
    ], columns=["scenario", "hour", "bus", "p_ch_mw", "p_dis_mw", "e_sto_mwh"])
    system_dispatch = pd.DataFrame([
        (
            scenario, h, price[h], p_grid[h].X, q_grid[h].X,
            sum(p_load.loc[h, b] for b in candidate_buses), sum(q_load.loc[h, b] for b in candidate_buses),
            sum(p_dg[g, h].X for g in dg_buses), sum(p_ch[b, h].X for b in candidate_buses), sum(p_dis[b, h].X for b in candidate_buses),
            sum(e_sto[b, h].X for b in candidate_buses), min(v[b, h].X**0.5 for b in buses),
            sum(S_base * branch_r[br] * ell[br, h].X for br in branches), sum(S_base * branch_x[br] * ell[br, h].X for br in branches),
        )
        for h in hours
    ], columns=["scenario", "hour", "grid_price", "p_grid_mw", "q_grid_mvar", "p_load_mw", "q_load_mvar", "p_dg_mw", "p_ch_mw", "p_dis_mw", "e_sto_mwh", "v_min_pu", "p_loss_mw", "q_loss_mvar"])
    branch_flow = pd.DataFrame([
        (
            scenario, h, br, f, t, P[br, h].X, Q[br, h].X,
            (P[br, h].X**2 + Q[br, h].X**2) ** 0.5, smax, ell[br, h].X,
            S_base * r * ell[br, h].X, S_base * x * ell[br, h].X,
            v[f, h].X * ell[br, h].X - (P[br, h].X / S_base) ** 2 - (Q[br, h].X / S_base) ** 2,
        )
        for h in hours for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None)
    ], columns=["scenario", "hour", "branch", "from_bus", "to_bus", "p_mw", "q_mvar", "s_mva", "s_max_mva", "ell_pu", "p_loss_mw", "q_loss_mvar", "soc_gap"])
    node_rows = []
    for h in hours:
        for b in buses:
            p_load_b = p_load.loc[h, b] if b in candidate_buses else 0.0
            q_load_b = q_load.loc[h, b] if b in candidate_buses else 0.0
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
            node_rows.append((scenario, h, b, p_in, p_loss_in, p_out, p_load_b, p_gen, p_charge, p_discharge, p_in - p_loss_in - p_out - p_load_b - p_charge + p_gen + p_discharge, q_in, q_loss_in, q_out, q_load_b, q_in - q_loss_in - q_out - q_load_b, v[b, h].X**0.5, ell_in))
    node_balance = pd.DataFrame(node_rows, columns=["scenario", "hour", "bus", "p_in_mw", "p_loss_in_mw", "p_out_mw", "p_load_mw", "p_dg_mw", "p_ch_mw", "p_dis_mw", "p_balance_residual_mw", "q_in_mvar", "q_loss_in_mvar", "q_out_mvar", "q_load_mvar", "q_balance_residual_mvar", "v_pu", "ell_in_pu"])
    energy_balance = pd.DataFrame([
        (scenario, h, b, e_sto[b, h].X, e_sto[b, (h + 1) % n_hours].X, p_ch[b, h].X, p_dis[b, h].X, e_sto[b, (h + 1) % n_hours].X - e_sto[b, h].X - eta_ch * p_ch[b, h].X + p_dis[b, h].X / eta_dis)
        for h in hours for b in candidate_buses
    ], columns=["scenario", "hour", "bus", "e_begin_mwh", "e_end_mwh", "p_ch_mw", "p_dis_mw", "energy_residual_mwh"])
    return storage_plan, storage_dispatch, system_dispatch, node_balance, energy_balance, branch_flow


def save_plots(progress, scenario_costs, storage_plan, node_balance):
    """保存教学版 CCG 的收敛、场景成本、储能规划和最坏场景运行图。"""
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(progress["iteration"], progress["LB"], color="#cf3e28", marker="o", linewidth=2.2, label="LB: master")
    ax1.plot(progress["iteration"], progress["UB"], color="#2766b0", marker="s", linewidth=2.2, label="UB: full scenario set")
    ax1.set_title("IEEE 33 Storage CCG Convergence", fontsize=17)
    ax1.set_xlabel("Iteration", fontsize=13)
    ax1.set_ylabel("Objective value", fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax2 = ax1.twinx()
    ax2.bar(progress["iteration"], progress["violation"], color="#8c8c8c", alpha=0.25, label="Violation")
    ax2.set_ylabel("Worst scenario violation", fontsize=13)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="best", fontsize=11)
    fig.savefig(OUT_DIR / "ccg_01_convergence.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    pivot = scenario_costs.pivot(index="iteration", columns="scenario", values="total_operation_cost")
    fig, ax = plt.subplots(figsize=(11, 6))
    for scenario in scenario_names:
        ax.plot(pivot.index, pivot[scenario], marker="o", linewidth=1.8, label=scenario)
    worst = scenario_costs.loc[scenario_costs["is_worst"] == 1]
    ax.scatter(worst["iteration"], worst["total_operation_cost"], color="black", s=70, zorder=5, label="worst")
    ax.set_title("Scenario Operation Costs in CCG Oracle", fontsize=17)
    ax.set_xlabel("Iteration", fontsize=13)
    ax.set_ylabel("Operation + cycle cost", fontsize=13)
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=3, fontsize=10)
    fig.savefig(OUT_DIR / "ccg_02_scenario_costs.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    built = storage_plan.loc[storage_plan["build"] == 1].sort_values("bus")
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(built))
    ax.bar([i - 0.18 for i in x], built["p_cap_mw"], width=0.36, color="#2766b0", label="Power capacity")
    ax.bar([i + 0.18 for i in x], built["e_cap_mwh"], width=0.36, color="#ef9b20", label="Energy capacity")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Bus {int(b)}" for b in built["bus"]])
    ax.set_title("Final Robust Storage Plan", fontsize=17)
    ax.set_ylabel("MW / MWh", fontsize=13)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=11)
    fig.savefig(OUT_DIR / "ccg_03_storage_plan.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    voltage = node_balance.pivot(index="hour", columns="bus", values="v_pu").reindex(columns=buses)
    fig, ax = plt.subplots(figsize=(12, 6))
    norm = plt.Normalize(min(buses), max(buses))
    cmap = plt.get_cmap("viridis")
    for b in buses:
        ax.plot(voltage.index, voltage[b], color=cmap(norm(b)), linewidth=1.5, alpha=0.82)
    ax.set_title("Worst Scenario All-Bus 24h Voltage Profiles", fontsize=17)
    ax.set_xlabel("Hour", fontsize=13)
    ax.set_ylabel("Voltage, p.u.", fontsize=13)
    ax.set_xticks(list(range(0, 24, 2)))
    ax.grid(True, alpha=0.25)
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, pad=0.01)
    cbar.set_label("Bus", fontsize=12)
    fig.savefig(OUT_DIR / "ccg_04_worst_voltage.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(7, 5, figsize=(24, 28), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    colors = {"in": "#2766b0", "dg": "#4f9b58", "discharge": "#42a5b3", "out": "#6d6d6d", "loss": "#b65d2a", "load": "#9aa0a6", "charge": "#ef9b20"}
    for ax, b in zip(axes_flat, buses):
        t = node_balance.loc[node_balance["bus"] == b].sort_values("hour")
        hours_list = t["hour"].tolist()
        pos_bottom = [0.0] * len(hours_list)
        neg_bottom = [0.0] * len(hours_list)
        for col, sign, color in [
            ("p_in_mw", 1.0, colors["in"]),
            ("p_dg_mw", 1.0, colors["dg"]),
            ("p_dis_mw", 1.0, colors["discharge"]),
            ("p_out_mw", -1.0, colors["out"]),
            ("p_loss_in_mw", -1.0, colors["loss"]),
            ("p_load_mw", -1.0, colors["load"]),
            ("p_ch_mw", -1.0, colors["charge"]),
        ]:
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
        plt.Rectangle((0, 0), 1, 1, color=colors["in"], label="Parent-branch flow"),
        plt.Rectangle((0, 0), 1, 1, color=colors["dg"], label="DG"),
        plt.Rectangle((0, 0), 1, 1, color=colors["discharge"], label="Storage discharge"),
        plt.Rectangle((0, 0), 1, 1, color=colors["out"], label="Child-branch flow"),
        plt.Rectangle((0, 0), 1, 1, color=colors["loss"], label="Line loss"),
        plt.Rectangle((0, 0), 1, 1, color=colors["load"], label="Load"),
        plt.Rectangle((0, 0), 1, 1, color=colors["charge"], label="Storage charge"),
    ]
    fig.suptitle("Worst Scenario All-Bus Active Power Balance", fontsize=22)
    fig.supxlabel("Hour", fontsize=16)
    fig.supylabel("Positive supplies this bus; negative consumes or exports from this bus; MW per hour", fontsize=16)
    fig.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 0.972), fontsize=13)
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(OUT_DIR / "ccg_05_worst_power_balance.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


active_scenarios = ["base"]  # 初始主问题只考虑基准场景；其他场景由 oracle 逐步发现
UB = GRB.INFINITY  # 完整场景集可行解给出的累计上界
progress_rows = []  # 每轮主问题、oracle 和上下界结果
scenario_cost_rows = []  # 每轮固定当前规划后，各候选场景的运行成本
best_plan = None  # 当前 CCG 方案；收敛后用于最终导出
best_worst_scenario = None  # 当前方案对应的完整场景集最坏场景

print("IEEE 33 teaching CCG with finite scenarios")
print("iter  active_scenarios                         worst              invest      eta         worst_op    LB          UB          gap         violation")

for it in range(1, max_iter + 1):
    # 1. 求主问题 MP(S_k)：只对 active_scenarios 中的场景建运行变量和约束。
    master, y, p_cap, e_cap, eta, investment, _, _ = build_master(active_scenarios)
    master.optimize()
    if master.Status != GRB.OPTIMAL:
        raise RuntimeError(f"CCG master status at iteration {it}: {master.Status}")
    y_bar, p_bar, e_bar = read_plan(y, p_cap, e_cap)
    investment_bar = investment.getValue()
    scenario_results = {}

    # 2. oracle：固定当前储能规划 x^k，枚举完整场景集 Xi，逐个求运行 SOCP。
    for scenario in scenario_names:
        _, total_cost, operation_cost, cycle_cost, _ = solve_operation_for_fixed_plan(scenario, p_bar, e_bar)
        scenario_results[scenario] = (total_cost, operation_cost, cycle_cost)

    # 3. 在完整场景集中选运行成本最大的场景，这就是当前规划下的最坏场景。
    worst_scenario = max(scenario_names, key=lambda name: scenario_results[name][0])
    worst_operation = scenario_results[worst_scenario][0]

    # 4. 更新上下界：LB 来自主问题；UB 来自“当前规划 + 完整场景集最坏运行成本”。
    LB = master.ObjVal  # 主问题只含部分场景，是原鲁棒问题的下界
    UB = min(UB, investment_bar + worst_operation)  # 当前规划对全部场景可行，因此给出上界候选
    gap = UB - LB  # 上下界差
    violation = worst_operation - eta.X  # 若 >0，说明还有场景成本超过主问题 eta，必须加入该场景
    built_buses = ",".join(str(b) for b in candidate_buses if y_bar[b]) or "-"
    active_text = ",".join(active_scenarios)
    progress_rows.append((it, active_text, worst_scenario, investment_bar, eta.X, worst_operation, LB, UB, gap, gap / max(1.0, abs(UB)), violation, built_buses, sum(p_bar.values()), sum(e_bar.values())))
    for scenario in scenario_names:
        total_cost, operation_cost, cycle_cost = scenario_results[scenario]
        scenario_cost_rows.append((it, scenario, total_cost, operation_cost, cycle_cost, int(scenario == worst_scenario), int(scenario in active_scenarios)))
    print(f"{it:>4}  {active_text:<40}  {worst_scenario:<18}  {investment_bar:>10.6f}  {eta.X:>10.6f}  {worst_operation:>10.6f}  {LB:>10.6f}  {UB:>10.6f}  {gap:>10.6f}  {violation:>10.6f}")
    best_plan = (y_bar, p_bar, e_bar, investment_bar)
    best_worst_scenario = worst_scenario
    if violation <= tol:
        break  # 最坏场景已被 eta 覆盖，完整有限场景集上收敛
    if worst_scenario not in active_scenarios:
        active_scenarios.append(worst_scenario)  # CCG 加入新场景：下一轮主问题新增该场景变量和约束

progress = pd.DataFrame(progress_rows, columns=["iteration", "active_scenarios", "new_worst_scenario", "investment", "eta", "worst_operation", "LB", "UB", "gap", "relgap", "violation", "built_buses", "p_cap_sum_mw", "e_cap_sum_mwh"])
scenario_costs = pd.DataFrame(scenario_cost_rows, columns=["iteration", "scenario", "total_operation_cost", "operation_cost", "cycle_cost", "is_worst", "is_active"])

y_best, p_best, e_best, investment_best = best_plan
final_model, final_cost, final_operation, final_cycle, final_vars = solve_operation_for_fixed_plan(best_worst_scenario, p_best, e_best)
storage_plan, storage_dispatch, system_dispatch, node_balance, energy_balance, branch_flow = make_result_tables(best_worst_scenario, y_best, p_best, e_best, final_vars)
summary = pd.DataFrame([
    ("objective", investment_best + final_cost),
    ("investment_cost", investment_best),
    ("worst_operation_cost", final_cost),
    ("worst_energy_operation_cost", final_operation),
    ("worst_cycle_cost", final_cycle),
    ("worst_scenario", best_worst_scenario),
    ("iterations", len(progress)),
    ("active_scenarios", progress.iloc[-1]["active_scenarios"]),
    ("built_buses", ",".join(str(b) for b in candidate_buses if y_best[b])),
    ("total_p_loss_mwh", system_dispatch["p_loss_mw"].sum()),
    ("total_q_loss_mvarh", system_dispatch["q_loss_mvar"].sum()),
    ("max_soc_gap", branch_flow["soc_gap"].max()),
    ("max_node_balance_residual_mw", node_balance["p_balance_residual_mw"].abs().max()),
    ("max_node_balance_residual_mvar", node_balance["q_balance_residual_mvar"].abs().max()),
    ("max_energy_balance_residual_mwh", energy_balance["energy_residual_mwh"].abs().max()),
], columns=["item", "value"])

excel_path = OUT_DIR / "ccg_storage_ieee33_summary.xlsx"
with pd.ExcelWriter(excel_path) as writer:
    summary.to_excel(writer, sheet_name="summary", index=False)
    scenario_pool.to_excel(writer, sheet_name="scenario_pool", index=False)
    scenario_multipliers.to_excel(writer, sheet_name="scenario_multipliers", index=False)
    progress.to_excel(writer, sheet_name="ccg_progress", index=False)
    scenario_costs.to_excel(writer, sheet_name="scenario_costs", index=False)
    storage_plan.to_excel(writer, sheet_name="storage_plan", index=False)
    storage_dispatch.to_excel(writer, sheet_name="worst_storage_dispatch", index=False)
    system_dispatch.to_excel(writer, sheet_name="worst_system_dispatch", index=False)
    node_balance.to_excel(writer, sheet_name="worst_node_balance", index=False)
    energy_balance.to_excel(writer, sheet_name="worst_energy_balance", index=False)
    branch_flow.to_excel(writer, sheet_name="worst_branch_flow", index=False)

save_plots(progress, scenario_costs, storage_plan, node_balance)

print()
print("IEEE 33 teaching CCG result")
print(summary.to_string(index=False))
print()
print(progress.round(6).to_string(index=False))
print()
print(storage_plan.loc[storage_plan["build"] == 1, ["bus", "p_cap_mw", "e_cap_mwh", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost", "duration_h"]].round(6).to_string(index=False))
print()
print(f"Excel: {excel_path}")
print(f"01 Convergence plot: {OUT_DIR / 'ccg_01_convergence.png'}")
print(f"02 Scenario costs plot: {OUT_DIR / 'ccg_02_scenario_costs.png'}")
print(f"03 Storage plan plot: {OUT_DIR / 'ccg_03_storage_plan.png'}")
print(f"04 Worst voltage plot: {OUT_DIR / 'ccg_04_worst_voltage.png'}")
print(f"05 Worst power balance plot: {OUT_DIR / 'ccg_05_worst_power_balance.png'}")
