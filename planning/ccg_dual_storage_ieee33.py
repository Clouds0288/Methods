"""IEEE 33 节点储能规划 dual CCG：用二阶段 LP 对偶 oracle 搜索最坏扰动。"""

from pathlib import Path
import sys

import gurobipy as gp
import matplotlib.pyplot as plt
import pandas as pd
from gurobipy import GRB


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))  # 允许直接运行脚本时导入项目包

from network.case33 import ROOT_DIR, S_base, hours, buses, branch_df, p_load_mw, dg_buses, p_dg_max  # noqa: E402


OUT_DIR = ROOT_DIR / "results" / "planning" / "ccg_dual"
OUT_DIR.mkdir(parents=True, exist_ok=True)

grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))  # 基准购电价，货币/MWh
dg_cost = 85.0  # 可调 DG 出力成本，货币/MWh
candidate_buses = buses[1:]  # 储能候选节点：除平衡节点 1 以外的所有节点
max_storage_sites = 3  # 最多建设 3 个储能站；聚合 LP 下通常只需要最浅层节点
duration_min, duration_max = 2.0, 6.0  # 储能持续时间约束
p_cap_site_max = S_base  # 单站功率容量大 M，仅用于 y_b=0 时关闭容量
e_cap_site_max = duration_max * p_cap_site_max  # 单站能量容量大 M
eta_ch, eta_dis = 0.95, 0.95  # 储能充放电效率
soc_min_frac, soc_init_frac = 0.10, 0.50  # 最小 SOC 和初始 SOC，按能量容量比例给定
storage_fixed_cost = 15.0  # 储能固定建站成本
storage_depth_cost = 5.0  # 储能接入施工成本系数，按馈线深度计
storage_power_cost = 18.0  # 储能功率容量成本，货币/(MW 日)
storage_energy_cost = 12.0  # 储能能量容量成本，货币/(MWh 日)
storage_cycle_cost = 1.0  # 储能充放电吞吐成本，货币/MWh
rho_load = 0.12  # 负荷上浮比例
rho_dg = 0.45  # DG 可用容量下调比例；mu 的 big-M 推导要求 rho_dg < 1
gamma_load = 4  # 最多选 4 个高负荷小时
gamma_dg = 4  # 最多选 4 个低 DG 小时
tol = 1e-4  # CCG 场景违反量收敛容差
dual_check_tol = 1e-4  # dual oracle 与固定场景 primal LP 的目标一致性容差
max_iter = 20  # 预算不确定集很大，教学算例通常数轮收敛
n_hours = len(list(hours))

bus_depth = {1: 0}
for _, f, t, _, _, _ in branch_df.itertuples(index=False, name=None):
    bus_depth[t] = bus_depth[f] + 1  # 节点到平衡节点的支路层数，用于接入施工成本

env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)
env.start()


def base_data():
    load_hat = {h: sum(p_load_mw.loc[h, b] for b in candidate_buses) for h in hours}  # 基准总有功负荷
    load_delta = {h: rho_load * load_hat[h] for h in hours}  # 负荷上浮量
    dg_hat = {g: p_dg_max[g] for g in dg_buses}  # DG 基准可用容量
    dg_delta = {g: rho_dg * dg_hat[g] for g in dg_buses}  # DG 下调量
    mu_big_m = {(g, h): max(0.0, grid_price[h] - dg_cost) for g in dg_buses for h in hours}  # 有效上界，见 ccg_dual.md
    return load_hat, load_delta, dg_hat, dg_delta, mu_big_m


load_hat, load_delta, dg_hat, dg_delta, mu_big_m = base_data()


def scenario_from_bits(name, u_load, v_dg, added_iteration):
    return {
        "name": name,
        "added_iteration": added_iteration,
        "u_load": dict(u_load),
        "v_dg": dict(v_dg),
        "load": {h: load_hat[h] + load_delta[h] * u_load[h] for h in hours},
        "dg_cap": {(g, h): dg_hat[g] - dg_delta[g] * v_dg[h] for g in dg_buses for h in hours},
    }


def scenario_signature(scenario):
    return tuple(scenario["u_load"][h] for h in hours), tuple(scenario["v_dg"][h] for h in hours)


def selected_hours(bits):
    hours_text = [str(h) for h in hours if bits[h]]
    return ",".join(hours_text) if hours_text else "-"


def investment_expr(y, p_cap, e_cap):
    return gp.quicksum((storage_fixed_cost + storage_depth_cost * bus_depth[b]) * y[b] + storage_power_cost * p_cap[b] + storage_energy_cost * e_cap[b] for b in candidate_buses)  # 第一阶段投资成本


def add_operation_primal(m, scenario, p_cap, e_cap, tag):
    p_grid = m.addVars(hours, lb=0, name=f"p_grid[{tag}]")  # 上级电网购电，MW
    p_dg = m.addVars(dg_buses, hours, lb=0, name=f"p_dg[{tag}]")  # DG 有功出力，MW
    p_ch = m.addVars(candidate_buses, hours, lb=0, name=f"p_ch[{tag}]")  # 储能充电，MW
    p_dis = m.addVars(candidate_buses, hours, lb=0, name=f"p_dis[{tag}]")  # 储能放电，MW
    e_sto = m.addVars(candidate_buses, hours, lb=0, name=f"e_sto[{tag}]")  # 储能电量，MWh

    for h in hours:
        m.addConstr(p_grid[h] + gp.quicksum(p_dg[g, h] for g in dg_buses) + gp.quicksum(p_dis[b, h] for b in candidate_buses) - gp.quicksum(p_ch[b, h] for b in candidate_buses) >= scenario["load"][h], name=f"p_balance[{tag},{h}]")  # 聚合有功平衡
        for g in dg_buses:
            m.addConstr(p_dg[g, h] <= scenario["dg_cap"][g, h], name=f"dg_cap[{tag},{g},{h}]")  # 当前扰动下 DG 可用容量
        for b in candidate_buses:
            h_next = (h + 1) % n_hours
            m.addConstr(p_ch[b, h] <= p_cap[b], name=f"charge_cap[{tag},{b},{h}]")  # 充电功率上界
            m.addConstr(p_dis[b, h] <= p_cap[b], name=f"discharge_cap[{tag},{b},{h}]")  # 放电功率上界
            m.addConstr(p_ch[b, h] + p_dis[b, h] <= p_cap[b], name=f"converter_cap[{tag},{b},{h}]")  # 共用变流器容量
            m.addConstr(e_sto[b, h] >= soc_min_frac * e_cap[b], name=f"soc_min[{tag},{b},{h}]")  # SOC 下界
            m.addConstr(e_sto[b, h] <= e_cap[b], name=f"soc_max[{tag},{b},{h}]")  # SOC 上界
            m.addConstr(e_sto[b, h_next] == e_sto[b, h] + eta_ch * p_ch[b, h] - p_dis[b, h] / eta_dis, name=f"soc_balance[{tag},{b},{h}]")  # 代表日循环 SOC
            if h == 0:
                m.addConstr(e_sto[b, h] == soc_init_frac * e_cap[b], name=f"initial_soc[{tag},{b}]")  # 初始 SOC

    operation = gp.quicksum(grid_price[h] * p_grid[h] + gp.quicksum(dg_cost * p_dg[g, h] for g in dg_buses) for h in hours)  # 购电和 DG 成本
    cycle = gp.quicksum(storage_cycle_cost * (p_ch[b, h] + p_dis[b, h]) for b in candidate_buses for h in hours)  # 储能吞吐成本
    return operation + cycle, operation, cycle, {"p_grid": p_grid, "p_dg": p_dg, "p_ch": p_ch, "p_dis": p_dis, "e_sto": e_sto}


def build_master(active_scenarios):
    m = gp.Model("ieee33_storage_dual_ccg_master", env=env)
    m.Params.MIPGap = 1e-9
    y = m.addVars(candidate_buses, vtype=GRB.BINARY, name="y_storage")  # 第一阶段选址变量
    p_cap = m.addVars(candidate_buses, lb=0, ub=p_cap_site_max, name="p_cap")  # 第一阶段功率容量
    e_cap = m.addVars(candidate_buses, lb=0, ub=e_cap_site_max, name="e_cap")  # 第一阶段能量容量
    eta = m.addVar(lb=0, name="eta")  # 已激活场景中的最坏运行成本
    m.addConstr(gp.quicksum(y[b] for b in candidate_buses) <= max_storage_sites, name="max_storage_sites")  # 储能站数量上限
    for b in candidate_buses:
        m.addConstr(p_cap[b] <= p_cap_site_max * y[b], name=f"p_cap_install[{b}]")  # 未建设时功率容量为 0
        m.addConstr(e_cap[b] <= e_cap_site_max * y[b], name=f"e_cap_install[{b}]")  # 未建设时能量容量为 0
        m.addConstr(e_cap[b] >= duration_min * p_cap[b], name=f"duration_min[{b}]")  # 最短持续时间
        m.addConstr(e_cap[b] <= duration_max * p_cap[b], name=f"duration_max[{b}]")  # 最长持续时间
    scenario_cost = {}
    scenario_vars = {}
    for scenario in active_scenarios:
        total_cost, operation, cycle, variables = add_operation_primal(m, scenario, p_cap, e_cap, scenario["name"])
        m.addConstr(eta >= total_cost, name=f"eta_epigraph[{scenario['name']}]")  # eta 覆盖当前激活场景
        scenario_cost[scenario["name"]] = (total_cost, operation, cycle)
        scenario_vars[scenario["name"]] = variables
    investment = investment_expr(y, p_cap, e_cap)
    m.setObjective(investment + eta, GRB.MINIMIZE)
    return m, y, p_cap, e_cap, eta, investment, scenario_cost, scenario_vars


def solve_operation_primal(scenario, p_bar, e_bar):
    m = gp.Model(f"ieee33_storage_primal_{scenario['name']}", env=env)
    m.Params.OptimalityTol = 1e-9
    total_cost, operation, cycle, variables = add_operation_primal(m, scenario, p_bar, e_bar, scenario["name"])
    m.setObjective(total_cost, GRB.MINIMIZE)
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Operation primal status for {scenario['name']}: {m.Status}")
    return m, m.ObjVal, operation.getValue(), cycle.getValue(), variables


def solve_dual_oracle(p_bar, e_bar):
    m = gp.Model("ieee33_storage_dual_oracle", env=env)
    m.Params.MIPGap = 1e-9
    u = m.addVars(hours, vtype=GRB.BINARY, name="u_load")  # 负荷高值小时
    v = m.addVars(hours, vtype=GRB.BINARY, name="v_dg")  # DG 低值小时
    lam = m.addVars(hours, lb=0, name="lambda")  # 聚合有功平衡对偶价
    mu = m.addVars(dg_buses, hours, lb=0, name="mu")  # DG 容量约束对偶价
    alpha = m.addVars(candidate_buses, hours, lb=0, name="alpha")  # 充电功率上界对偶价
    beta = m.addVars(candidate_buses, hours, lb=0, name="beta")  # 放电功率上界对偶价
    gamma = m.addVars(candidate_buses, hours, lb=0, name="gamma")  # 变流器合计功率上界对偶价
    delta = m.addVars(candidate_buses, hours, lb=0, name="delta")  # SOC 下界对偶价
    zeta = m.addVars(candidate_buses, hours, lb=0, name="zeta")  # SOC 上界对偶价
    kappa = m.addVars(candidate_buses, lb=-GRB.INFINITY, name="kappa")  # 初始 SOC 等式对偶价
    tau = m.addVars(candidate_buses, hours, lb=-GRB.INFINITY, name="tau")  # SOC 递推等式对偶价
    omega_l = m.addVars(hours, lb=0, name="omega_load")  # lambda_h u_h
    omega_g = m.addVars(dg_buses, hours, lb=0, name="omega_dg")  # mu_gh v_h

    m.addConstr(gp.quicksum(u[h] for h in hours) <= gamma_load, name="budget_load")  # 负荷扰动预算
    m.addConstr(gp.quicksum(v[h] for h in hours) <= gamma_dg, name="budget_dg")  # DG 扰动预算
    for h in hours:
        m.addConstr(lam[h] <= grid_price[h], name=f"dual_grid[{h}]")  # p_grid 对偶约束
        m.addConstr(omega_l[h] <= grid_price[h] * u[h], name=f"omega_l_ub_binary[{h}]")  # big-M: omega=lambda*u
        m.addConstr(omega_l[h] <= lam[h], name=f"omega_l_ub_lambda[{h}]")
        m.addConstr(omega_l[h] >= lam[h] - grid_price[h] * (1 - u[h]), name=f"omega_l_lb[{h}]")
        for g in dg_buses:
            m.addConstr(lam[h] - mu[g, h] <= dg_cost, name=f"dual_dg[{g},{h}]")  # p_dg 对偶约束
            m.addConstr(mu[g, h] <= mu_big_m[g, h], name=f"mu_big_m[{g},{h}]")  # 有效上界，供 omega 线性化
            m.addConstr(omega_g[g, h] <= mu_big_m[g, h] * v[h], name=f"omega_g_ub_binary[{g},{h}]")
            m.addConstr(omega_g[g, h] <= mu[g, h], name=f"omega_g_ub_mu[{g},{h}]")
            m.addConstr(omega_g[g, h] >= mu[g, h] - mu_big_m[g, h] * (1 - v[h]), name=f"omega_g_lb[{g},{h}]")
        for b in candidate_buses:
            m.addConstr(-lam[h] - alpha[b, h] - gamma[b, h] - eta_ch * tau[b, h] <= storage_cycle_cost, name=f"dual_charge[{b},{h}]")  # p_ch 对偶约束
            m.addConstr(lam[h] - beta[b, h] - gamma[b, h] + tau[b, h] / eta_dis <= storage_cycle_cost, name=f"dual_discharge[{b},{h}]")  # p_dis 对偶约束
            h_prev = (h - 1) % n_hours
            initial_term = kappa[b] if h == 0 else 0
            m.addConstr(delta[b, h] - zeta[b, h] + initial_term + tau[b, h_prev] - tau[b, h] <= 0, name=f"dual_energy[{b},{h}]")  # e_sto 对偶约束

    obj = gp.quicksum(load_hat[h] * lam[h] + load_delta[h] * omega_l[h] for h in hours)
    obj += gp.quicksum(-dg_hat[g] * mu[g, h] + dg_delta[g] * omega_g[g, h] for g in dg_buses for h in hours)
    obj += gp.quicksum(-(alpha[b, h] + beta[b, h] + gamma[b, h]) * p_bar[b] + (soc_min_frac * delta[b, h] - zeta[b, h]) * e_bar[b] for b in candidate_buses for h in hours)
    obj += gp.quicksum(soc_init_frac * kappa[b] * e_bar[b] for b in candidate_buses)
    m.setObjective(obj, GRB.MAXIMIZE)
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Dual oracle status: {m.Status}")

    u_bar = {h: int(round(u[h].X)) for h in hours}
    v_bar = {h: int(round(v[h].X)) for h in hours}
    hour_detail = pd.DataFrame([
        (h, u_bar[h], v_bar[h], load_hat[h], load_delta[h], load_hat[h] + load_delta[h] * u_bar[h], lam[h].X, sum(mu[g, h].X for g in dg_buses), sum(dg_hat[g] - dg_delta[g] * v_bar[h] for g in dg_buses))
        for h in hours
    ], columns=["hour", "u_load", "v_dg", "base_load_mw", "load_delta_mw", "scenario_load_mw", "lambda", "mu_sum", "dg_cap_total_mw"])
    dg_detail = pd.DataFrame([
        (h, g, v_bar[h], dg_hat[g], dg_delta[g], dg_hat[g] - dg_delta[g] * v_bar[h], mu[g, h].X)
        for h in hours for g in dg_buses
    ], columns=["hour", "dg_bus", "v_dg", "base_dg_cap_mw", "dg_delta_mw", "scenario_dg_cap_mw", "mu"])
    return m.ObjVal, u_bar, v_bar, hour_detail, dg_detail


def read_plan(y, p_cap, e_cap):
    y_bar = {b: int(round(y[b].X)) for b in candidate_buses}
    p_bar = {b: p_cap[b].X for b in candidate_buses}
    e_bar = {b: e_cap[b].X for b in candidate_buses}
    return y_bar, p_bar, e_bar


def make_storage_plan(y_bar, p_bar, e_bar):
    return pd.DataFrame([
        (b, y_bar[b], p_bar[b], e_bar[b], e_bar[b] / p_bar[b] if p_bar[b] > 1e-9 else pd.NA, storage_fixed_cost * y_bar[b], storage_depth_cost * bus_depth[b] * y_bar[b], storage_power_cost * p_bar[b], storage_energy_cost * e_bar[b])
        for b in candidate_buses
    ], columns=["bus", "build", "p_cap_mw", "e_cap_mwh", "duration_h", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost"])


def make_dispatch_tables(scenario, variables):
    p_grid, p_dg = variables["p_grid"], variables["p_dg"]
    p_ch, p_dis, e_sto = variables["p_ch"], variables["p_dis"], variables["e_sto"]
    final_dispatch = pd.DataFrame([
        (
            h, scenario["u_load"][h], scenario["v_dg"][h], scenario["load"][h],
            sum(scenario["dg_cap"][g, h] for g in dg_buses), p_grid[h].X,
            sum(p_dg[g, h].X for g in dg_buses), sum(p_ch[b, h].X for b in candidate_buses),
            sum(p_dis[b, h].X for b in candidate_buses), sum(e_sto[b, h].X for b in candidate_buses),
        )
        for h in hours
    ], columns=["hour", "u_load", "v_dg", "load_mw", "dg_cap_mw", "p_grid_mw", "p_dg_mw", "p_ch_mw", "p_dis_mw", "e_sto_mwh"])
    storage_dispatch = pd.DataFrame([
        (h, b, p_ch[b, h].X, p_dis[b, h].X, e_sto[b, h].X)
        for h in hours for b in candidate_buses
    ], columns=["hour", "bus", "p_ch_mw", "p_dis_mw", "e_sto_mwh"])
    return final_dispatch, storage_dispatch


def make_active_scenarios(active_scenarios):
    return pd.DataFrame([
        (scenario["name"], scenario["added_iteration"], h, scenario["u_load"][h], scenario["v_dg"][h], scenario["load"][h], sum(scenario["dg_cap"][g, h] for g in dg_buses))
        for scenario in active_scenarios for h in hours
    ], columns=["scenario", "added_iteration", "hour", "u_load", "v_dg", "load_mw", "dg_cap_total_mw"])


def save_plots(progress, final_oracle_detail, storage_plan, final_dispatch):
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(progress["iteration"], progress["LB"], marker="o", color="#cf3e28", label="LB")
    ax1.plot(progress["iteration"], progress["UB"], marker="s", color="#2766b0", label="UB")
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Objective")
    ax1.grid(alpha=0.3)
    ax2 = ax1.twinx()
    ax2.bar(progress["iteration"], progress["violation"], color="#8c8c8c", alpha=0.25, label="Violation")
    ax2.set_ylabel("Violation")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ccg_dual_01_convergence.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(final_oracle_detail["hour"] - 0.18, final_oracle_detail["u_load"], width=0.36, color="#cf3e28", label="High load")
    ax1.bar(final_oracle_detail["hour"] + 0.18, -final_oracle_detail["v_dg"], width=0.36, color="#2766b0", label="Low DG")
    ax1.set_xlabel("Hour")
    ax1.set_ylabel("Selected perturbation")
    ax1.set_yticks([-1, 0, 1])
    ax1.grid(axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(final_oracle_detail["hour"], final_oracle_detail["lambda"], color="black", marker="o", label="lambda")
    ax2.plot(final_oracle_detail["hour"], final_oracle_detail["mu_sum"], color="#ef9b20", marker="s", label="sum mu")
    ax2.set_ylabel("Dual price")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, ncol=4, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ccg_dual_02_worst_uncertainty.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    built = storage_plan.loc[storage_plan["build"] == 1].sort_values("bus")
    fig, ax = plt.subplots(figsize=(8, 5))
    if built.empty:
        ax.text(0.5, 0.5, "No storage built", ha="center", va="center", transform=ax.transAxes)
    else:
        x = range(len(built))
        ax.bar([i - 0.18 for i in x], built["p_cap_mw"], width=0.36, color="#2766b0", label="Power")
        ax.bar([i + 0.18 for i in x], built["e_cap_mwh"], width=0.36, color="#ef9b20", label="Energy")
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"Bus {int(b)}" for b in built["bus"]])
        ax.legend(frameon=False)
    ax.set_ylabel("MW / MWh")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ccg_dual_03_storage_plan.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(final_dispatch["hour"], final_dispatch["load_mw"], color="black", lw=2.0, label="Load")
    ax.plot(final_dispatch["hour"], final_dispatch["p_grid_mw"], marker="o", label="Grid")
    ax.plot(final_dispatch["hour"], final_dispatch["p_dg_mw"], marker="s", label="DG")
    ax.plot(final_dispatch["hour"], final_dispatch["p_ch_mw"], marker="v", label="Charge")
    ax.plot(final_dispatch["hour"], final_dispatch["p_dis_mw"], marker="^", label="Discharge")
    ax.set_xlabel("Hour")
    ax.set_ylabel("MW")
    ax.grid(alpha=0.25)
    ax.legend(ncol=5, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ccg_dual_04_dispatch.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


base = scenario_from_bits("base", {h: 0 for h in hours}, {h: 0 for h in hours}, 0)
active_scenarios = [base]
active_signatures = {scenario_signature(base)}
UB = GRB.INFINITY
progress_rows = []
oracle_hour_tables = []
oracle_dg_tables = []
last_oracle_detail = None
last_scenario = None
last_plan = None

print("IEEE 33 dual CCG with LP recourse")
print("iter  active  load_hours   dg_hours     invest      eta         oracle     LB          UB          gap         violation")

for it in range(1, max_iter + 1):
    master, y, p_cap, e_cap, eta, investment, _, _ = build_master(active_scenarios)
    master.optimize()
    if master.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Master status at iteration {it}: {master.Status}")

    y_bar, p_bar, e_bar = read_plan(y, p_cap, e_cap)
    investment_bar = investment.getValue()
    oracle_obj, u_bar, v_bar, hour_detail, dg_detail = solve_dual_oracle(p_bar, e_bar)
    scenario = scenario_from_bits(f"dual_{it:02d}", u_bar, v_bar, it)
    _, primal_obj, primal_operation, primal_cycle, primal_vars = solve_operation_primal(scenario, p_bar, e_bar)
    if abs(primal_obj - oracle_obj) > dual_check_tol:
        raise RuntimeError(f"Primal-dual mismatch at iteration {it}: primal={primal_obj:.8f}, dual={oracle_obj:.8f}")

    LB = master.ObjVal
    UB = min(UB, investment_bar + primal_obj)
    gap = max(0.0, UB - LB)
    violation = max(0.0, primal_obj - eta.X)
    load_hours = selected_hours(u_bar)
    dg_hours = selected_hours(v_bar)
    active_text = ",".join(s["name"] for s in active_scenarios)
    progress_rows.append((it, active_text, load_hours, dg_hours, investment_bar, eta.X, oracle_obj, primal_obj, primal_operation, primal_cycle, LB, UB, gap, gap / max(1.0, abs(UB)), violation, ",".join(str(b) for b in candidate_buses if y_bar[b]) or "-", sum(p_bar.values()), sum(e_bar.values())))
    hour_detail.insert(0, "iteration", it)
    dg_detail.insert(0, "iteration", it)
    oracle_hour_tables.append(hour_detail)
    oracle_dg_tables.append(dg_detail)
    last_oracle_detail = hour_detail
    last_scenario = scenario
    last_plan = (y_bar, p_bar, e_bar)
    print(f"{it:>4}  {len(active_scenarios):>6}  {load_hours:<11}  {dg_hours:<11}  {investment_bar:>10.6f}  {eta.X:>10.6f}  {oracle_obj:>10.6f}  {LB:>10.6f}  {UB:>10.6f}  {gap:>10.6f}  {violation:>10.6f}")

    signature = scenario_signature(scenario)
    if violation <= tol:
        break
    if signature in active_signatures:
        raise RuntimeError(f"Oracle returned an already active scenario with violation {violation:.8f}")
    active_scenarios.append(scenario)
    active_signatures.add(signature)
else:
    raise RuntimeError(f"Dual CCG did not converge within {max_iter} iterations")

progress = pd.DataFrame(progress_rows, columns=["iteration", "active_scenarios", "load_hours", "dg_hours", "investment", "eta", "oracle_dual_obj", "oracle_primal_obj", "oracle_operation_cost", "oracle_cycle_cost", "LB", "UB", "gap", "relgap", "violation", "built_buses", "p_cap_sum_mw", "e_cap_sum_mwh"])
oracle_detail = pd.concat(oracle_hour_tables, ignore_index=True)
oracle_dg_detail = pd.concat(oracle_dg_tables, ignore_index=True)
y_best, p_best, e_best = last_plan
_, final_obj, final_operation, final_cycle, final_vars = solve_operation_primal(last_scenario, p_best, e_best)
storage_plan = make_storage_plan(y_best, p_best, e_best)
final_dispatch, storage_dispatch = make_dispatch_tables(last_scenario, final_vars)
active_scenario_table = make_active_scenarios(active_scenarios)
summary = pd.DataFrame([
    ("objective", progress.iloc[-1]["investment"] + final_obj),
    ("investment_cost", progress.iloc[-1]["investment"]),
    ("worst_operation_cost", final_obj),
    ("worst_energy_operation_cost", final_operation),
    ("worst_cycle_cost", final_cycle),
    ("iterations", len(progress)),
    ("final_load_hours", progress.iloc[-1]["load_hours"]),
    ("final_dg_hours", progress.iloc[-1]["dg_hours"]),
    ("built_buses", progress.iloc[-1]["built_buses"]),
    ("total_p_cap_mw", storage_plan["p_cap_mw"].sum()),
    ("total_e_cap_mwh", storage_plan["e_cap_mwh"].sum()),
    ("final_gap", progress.iloc[-1]["gap"]),
    ("final_violation", progress.iloc[-1]["violation"]),
], columns=["item", "value"])

excel_path = OUT_DIR / "ccg_dual_storage_ieee33_summary.xlsx"
with pd.ExcelWriter(excel_path) as writer:
    summary.to_excel(writer, sheet_name="summary", index=False)
    progress.to_excel(writer, sheet_name="ccg_dual_progress", index=False)
    oracle_detail.to_excel(writer, sheet_name="dual_oracle_detail", index=False)
    oracle_dg_detail.to_excel(writer, sheet_name="dual_dg_detail", index=False)
    active_scenario_table.to_excel(writer, sheet_name="active_scenarios", index=False)
    storage_plan.to_excel(writer, sheet_name="storage_plan", index=False)
    final_dispatch.to_excel(writer, sheet_name="final_dispatch", index=False)
    storage_dispatch.to_excel(writer, sheet_name="storage_dispatch", index=False)

save_plots(progress, last_oracle_detail, storage_plan, final_dispatch)

print()
print("IEEE 33 dual CCG result")
print(summary.to_string(index=False))
print()
print(storage_plan.loc[storage_plan["build"] == 1, ["bus", "p_cap_mw", "e_cap_mwh", "duration_h", "fixed_cost", "depth_connection_cost", "power_cost", "energy_cost"]].round(6).to_string(index=False))
print()
print(f"Excel: {excel_path}")
print(f"01 Convergence plot: {OUT_DIR / 'ccg_dual_01_convergence.png'}")
print(f"02 Worst uncertainty plot: {OUT_DIR / 'ccg_dual_02_worst_uncertainty.png'}")
print(f"03 Storage plan plot: {OUT_DIR / 'ccg_dual_03_storage_plan.png'}")
print(f"04 Dispatch plot: {OUT_DIR / 'ccg_dual_04_dispatch.png'}")
