# 规划模型：储能选址定容与投切 MISOCP

## 1. 从 OPF 到规划

当前 OPF 问题是：

```text
已知网架、负荷、DG 和设备容量，求每个小时的最优运行。
```

储能规划进一步把“设备是否建设、建在哪里、建多大”也作为决策：

```text
min 投资成本 + 代表日运行成本

s.t.
    每个小时满足 DistFlow-SOCP 潮流约束
    储能选址、容量、充放电和 SOC 约束
    电压、支路容量、电源出力边界
```

因此它不是单纯的 OPF，而是：

```text
投资变量 + 多时段运行 OPF
```

## 2. 投资变量

候选储能节点为：

```text
3, 4, 5, 6
```

二进制变量：

```text
y_i ∈ {0,1}
```

含义：

```text
y_i = 1：在节点 i 建设储能
y_i = 0：不建设
```

当前小算例为了突出“选址”含义，限制最多建设一个储能站：

```text
sum_i y_i <= 1
```

功率容量和能量容量为连续变量：

```text
0 <= P_i^cap <= P_i^max y_i
0 <= E_i^cap <= E_i^max y_i
```

所以如果 `y_i=0`，该节点储能容量自动为 0。

储能时长约束为：

```text
T_min P_i^cap <= E_i^cap <= T_max P_i^cap
```

它保证容量组合具有合理的小时数含义。

## 3. 运行变量

每个候选节点和每个小时有：

```text
P_i,t^ch  >= 0      充电功率
P_i,t^dis >= 0      放电功率
E_i,t     >= 0      储能电量
u_i,t^ch  ∈ {0,1}   充电状态
u_i,t^dis ∈ {0,1}   放电状态
```

功率边界：

```text
P_i,t^ch  <= P_i^cap
P_i,t^dis <= P_i^cap
```

投切互斥：

```text
P_i,t^ch  <= P_i^max u_i,t^ch
P_i,t^dis <= P_i^max u_i,t^dis
u_i,t^ch + u_i,t^dis <= y_i
```

这表示：

```text
未建设时不能运行；
建设后同一小时不能同时充电和放电。
```

这部分二进制变量是规划模型变成混合整数模型的主要原因。

## 4. SOC 递推

时间步长取 1 小时，储能能量平衡为：

```text
E_i,t+1 = E_i,t + eta_ch P_i,t^ch - P_i,t^dis / eta_dis
```

SOC 边界为：

```text
SOC_min E_i^cap <= E_i,t <= E_i^cap
```

代表日起始 SOC 固定为容量的 50%：

```text
E_i,0 = 0.5 E_i^cap
```

最后一小时连接回第 0 小时：

```text
E_i,0 = E_i,23 + eta_ch P_i,23^ch - P_i,23^dis / eta_dis
```

这表示代表日循环运行，避免模型把初始电量免费用完。

## 5. 与 DistFlow-SOCP 的耦合

储能按单位功率因数运行，当前只参与有功平衡。

对非平衡节点 `j`，原 DistFlow 有功平衡为：

```text
P_ij,t = p_j,t^load - p_j,t^DG + sum_k P_jk,t + S_base r_ij ell_ij,t
```

加入储能后，充电是额外负荷，放电是额外电源：

```text
P_ij,t =
    p_j,t^load
  + P_j,t^ch
  - p_j,t^DG
  - P_j,t^dis
  + sum_k P_jk,t
  + S_base r_ij ell_ij,t
```

无功平衡暂不加入储能逆变器无功能力：

```text
Q_ij,t = q_j,t^load + sum_k Q_jk,t + S_base x_ij ell_ij,t
```

电压方程仍为：

```text
v_j,t = v_i,t - 2(r_ij P_ij,t/S_base + x_ij Q_ij,t/S_base)
        + (r_ij^2 + x_ij^2) ell_ij,t
```

SOCP 松弛仍发生在：

```text
(P_ij,t/S_base)^2 + (Q_ij,t/S_base)^2 <= v_i,t ell_ij,t
```

因此模型整体是：

```text
整数变量 + 线性约束 + 二阶锥约束
= MISOCP
```

## 6. 目标函数

当前 `planning/misocp_storage.py` 使用代表日成本：

```text
min
    sum_t c_t^grid P_t^grid
  + sum_t c^DG P_t^DG
  + sum_i (c_fixed y_i + c_P P_i^cap + c_E E_i^cap)
  + sum_i,t c_cycle (P_i,t^ch + P_i,t^dis)
```

其中：

```text
前两项：运行成本
第三项：储能日化投资成本
第四项：储能吞吐成本，用于表示循环损耗/寿命成本
```

## 7. 输出

运行：

```powershell
python -m planning.misocp_storage
```

输出：

```text
results/planning/misocp/planning_comparison.xlsx
results/planning/misocp/storage_planning.png
```

主要 sheet：

```text
summary
storage_plan
storage_dispatch
planning_dispatch
planning_voltage
planning_branch_flow
planning_model_info
```
