import time

import numpy as np
import pandas as pd
import cvxpy as cp

from network.case6 import (
    OUT_DIR, S_base, V_min, V_max, hours,
    buses, branch_df, p_load_mw, q_load_mvar,
    p_dg_max, q_grid_max,
)
from opf.opf_report import write_sheets


OUT_DIR.mkdir(parents=True, exist_ok=True)
grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))  # 电网购电单价，按小时给定
dg_cost = 85.0  # 分布式电源有功出力成本
bus_idx = {b: k for k, b in enumerate(buses)}  # 把母线编号映射为矩阵下标，便于写 Y、W 矩阵
n = len(buses)  # 母线数，也是节点电压向量 V 的维度

Y = np.zeros((n, n), dtype=complex)  # 节点导纳矩阵，满足注入电流 I=YV
for _, f, t, r, x, _ in branch_df.itertuples(index=False, name=None):
    i, j = bus_idx[f], bus_idx[t]
    y = 1 / complex(r, x)  # 支路串联导纳，r、x 已经是 p.u.，因此 y 也是 p.u.
    Y[i, i] += y  # 无并联导纳时，自导纳等于所有相连支路串联导纳之和
    Y[j, j] += y
    Y[i, j] -= y  # 互导纳为负的支路导纳，对应 I_i 中的 y(V_i-V_j)
    Y[j, i] -= y


def load_at(df, h, b):
    return float(df.loc[h, b]) if b in df.columns else 0.0  # 负荷表只列有负荷母线；未列母线表示该时刻负荷为 0


def s_from_w(W, f, t, y):
    i, j = bus_idx[f], bus_idx[t]
    return np.conj(y) * (W[i, i] - W[i, j])  # S_ij=V_i*conj(y(V_i-V_j))=conj(y)*(W_ii-W_ij)，p.u.


dispatch_rows, voltage_rows, branch_rows, rank_rows, status_rows = [], [], [], [], []  # 分别保存调度、电压、支路、秩诊断、求解状态
t_start = time.time()

for h in hours:
    W = cp.Variable((n, n), hermitian=True, name=f"W_{h}")  # SDP 变量 W=V V^H；原 AC OPF 要求 rank(W)=1
    p_grid = cp.Variable(nonneg=True, name=f"p_grid_{h}")  # 平衡节点从上级电网购入的有功，MW
    q_grid = cp.Variable(nonneg=True, name=f"q_grid_{h}")  # 平衡节点从上级电网购入的无功，MVAr
    p_dg = cp.Variable(nonneg=True, name=f"p_dg_{h}")  # 6 号节点分布式电源有功，MW

    constraints = [
        W >> 0,  # 半正定约束 W>=0；这是保留 W=V V^H 的必要条件，但去掉了非凸的 rank(W)=1
        cp.real(W[bus_idx[1], bus_idx[1]]) == 1.0,  # 平衡节点电压幅值固定为 1.0 p.u.，即 |V_1|^2=1
        cp.imag(W[bus_idx[1], bus_idx[1]]) == 0.0,  # W 的对角线理论上是实数；显式约束可减少数值漂移
    ]
    constraints += [p_grid <= 6.0, q_grid <= q_grid_max, p_dg <= p_dg_max]  # 设备容量约束，仍使用 MW/MVAr 原单位

    for b in buses:
        i = bus_idx[b]
        constraints += [
            cp.real(W[i, i]) >= V_min**2,  # W_ii=|V_i|^2，所以电压下限要平方后施加
            cp.real(W[i, i]) <= V_max**2,  # W_ii=|V_i|^2，所以电压上限也写成平方形式
            cp.imag(W[i, i]) == 0.0,  # Hermitian 矩阵对角线应为实数；这里把物理含义直接写进模型
        ]

        s_inj = cp.sum(cp.multiply(np.conj(Y[i, :]), W[i, :]))  # S_i=V_i*conj(I_i)=sum_j conj(Y_ij) W_ij，p.u.
        p_net = ((p_grid if b == 1 else 0) + (p_dg if b == 6 else 0) - load_at(p_load_mw, h, b)) / S_base  # 净有功注入，MW 除以 S_base 变成 p.u.
        q_net = ((q_grid if b == 1 else 0) - load_at(q_load_mvar, h, b)) / S_base  # 净无功注入，MVAr 除以 S_base 变成 p.u.
        constraints += [
            cp.real(s_inj) == p_net,  # 有功平衡：矩阵 W 写出的网络注入等于电源减负荷
            cp.imag(s_inj) == q_net,  # 无功平衡：同一个复功率平衡式取虚部
        ]

    for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
        y = 1 / complex(r, x)  # 用同一条支路导纳计算两端视在功率
        s_ft = s_from_w(W, f, t, y)  # f 端流向 t 端的复功率，p.u.
        s_tf = s_from_w(W, t, f, y)  # t 端流向 f 端的复功率，p.u.；有损耗时不等于 -s_ft
        constraints += [cp.norm(cp.hstack([cp.real(s_ft), cp.imag(s_ft)]), 2) <= smax / S_base]  # |S_ft|<=Smax，MVA 除以 S_base 得 p.u.
        constraints += [cp.norm(cp.hstack([cp.real(s_tf), cp.imag(s_tf)]), 2) <= smax / S_base]  # 两端都检查容量，避免只限制单侧功率

    problem = cp.Problem(cp.Minimize(grid_price[h] * p_grid + dg_cost * p_dg), constraints)  # 逐小时 OPF；目标仍用 MW 原单位计费
    problem.solve(solver=cp.SCS, eps=1e-6, max_iters=100000, verbose=False)  # SCS 求解半正定锥模型；eps 控制一阶法精度
    if problem.status != cp.OPTIMAL:
        raise RuntimeError(f"SDP relaxation hour {h} status: {problem.status}")  # 研究脚本让异常直接暴露，避免悄悄使用坏结果

    W_val = (W.value + W.value.conj().T) / 2  # 数值解可能有极小非 Hermitian 误差，后处理前做一次对称化
    diag_v = {b: max(W_val[bus_idx[b], bus_idx[b]].real, 0.0) for b in buses}  # W_ii=|V_i|^2；截断极小负数只处理数值噪声
    voltage_rows.append((h, *[diag_v[b] ** 0.5 for b in buses]))  # 输出电压幅值 |V_i|，不是电压平方
    dispatch_rows.append((h, p_grid.value, p_dg.value, q_grid.value, min(diag_v.values()) ** 0.5, max(diag_v.values()) ** 0.5))  # 调度与电压范围

    eig = np.linalg.eigvalsh(W_val)  # 如果松弛精确，W 应接近 rank-1，即只有一个显著特征值
    eig = np.sort(np.maximum(eig, 0.0))[::-1]  # 半正定矩阵的负小特征值视为数值误差，并按从大到小排列
    rank_rows.append((
        h,
        eig[0],
        eig[1] if len(eig) > 1 else 0.0,
        eig[1:].sum(),
        eig[1] / eig[0] if eig[0] > 1e-10 else np.nan,
        eig[1:].sum() / eig[0] if eig[0] > 1e-10 else np.nan,
    ))  # lambda2/lambda1 越小，说明 W 越接近 rank-1，越容易恢复原 AC 电压相量
    status_rows.append((h, problem.status, problem.value, problem.solver_stats.solve_time, len(constraints), sum(var.size for var in problem.variables())))  # 记录每小时求解规模和状态

    for br, f, t, r, x, smax in branch_df.itertuples(index=False, name=None):
        y = 1 / complex(r, x)
        s_ft = s_from_w(W_val, f, t, y) * S_base  # p.u. 乘 S_base 还原为 MW/MVAr
        s_tf = s_from_w(W_val, t, f, y) * S_base
        branch_rows.append((
            h, br, f, t,
            s_ft.real, s_ft.imag,
            s_tf.real, s_tf.imag,
            abs(s_ft), abs(s_tf), smax,
            s_ft.real + s_tf.real,
            s_ft.imag + s_tf.imag,
        ))  # 两端有功之和是该支路有功损耗，两端无功之和是等效无功损耗/消耗


opf = pd.DataFrame(dispatch_rows, columns=["hour", "p_grid_mw", "p_dg_mw", "q_grid_mvar", "v_min_pu", "v_max_pu"]).set_index("hour")  # 每小时电源调度结果
v_pu = pd.DataFrame(voltage_rows, columns=["hour", *buses]).set_index("hour")  # 每小时各母线电压幅值
rank_diag = pd.DataFrame(rank_rows, columns=["hour", "lambda_1", "lambda_2", "tail_eigen_sum", "lambda2_over_lambda1", "tail_over_lambda1"])  # SDP 松弛是否接近 rank-1 的诊断
solver_status = pd.DataFrame(status_rows, columns=["hour", "status", "objective", "solve_time_sec", "constraints", "scalar_variables"])  # 求解器状态与规模

branch_flow = pd.DataFrame(
    branch_rows,
    columns=["hour", "branch", "from_bus", "to_bus", "p_from_mw", "q_from_mvar", "p_to_mw", "q_to_mvar", "s_from_mva", "s_to_mva", "s_max_mva", "p_loss_mw", "q_loss_mvar"],
)  # SDP 直接由 W 计算支路两端复功率，不需要另设支路功率变量
branch_flow["loading_from_pct"] = 100 * branch_flow["s_from_mva"] / branch_flow["s_max_mva"]  # from 端容量利用率
branch_flow["loading_to_pct"] = 100 * branch_flow["s_to_mva"] / branch_flow["s_max_mva"]  # to 端容量利用率
branch_flow["loading_pct"] = branch_flow[["loading_from_pct", "loading_to_pct"]].max(axis=1)  # 报告时取两端较大值

model_info = pd.DataFrame(
    [
        ("objective", sum(row[2] for row in status_rows)),  # 各小时目标值相加，得到全天购电与 DG 成本
        ("solver", "SCS"),
        ("hours", len(list(hours))),
        ("total_wall_time_sec", time.time() - t_start),
        ("max_lambda2_over_lambda1", rank_diag["lambda2_over_lambda1"].max()),  # 全日最差的 rank-1 接近程度
        ("max_tail_over_lambda1", rank_diag["tail_over_lambda1"].max()),  # 除最大特征值外的总能量占比
    ],
    columns=["metric", "value"],
)

write_sheets([
    ("sdp_model_info", model_info, False),
    ("sdp_dispatch", opf, True),
    ("sdp_voltage", v_pu, True),
    ("sdp_branch_flow", branch_flow, False),
    ("sdp_rank", rank_diag, False),
    ("sdp_solver_status", solver_status, False),
])  # 写入 comparison.xlsx 的 SDP 相关 sheet

print("Model: sdp_relaxation_opf_6bus")
print(f"Objective: {(pd.Series(grid_price) * opf['p_grid_mw'] + dg_cost * opf['p_dg_mw']).sum():.4f}")
print(f"Solver: SCS")
print(f"Maximum lambda2/lambda1: {rank_diag['lambda2_over_lambda1'].max():.2e}")
print()
print(opf.head().round(4))
print(f"Minimum voltage: {v_pu.min().min():.4f} pu")
print(f"Maximum branch loading: {branch_flow['loading_pct'].max():.2f}%")
print(f"Total active loss: {branch_flow['p_loss_mw'].sum():.4f} MWh")
