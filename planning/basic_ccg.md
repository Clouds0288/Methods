# IEEE 33 节点教学版 CCG 储能鲁棒规划计划

本文档的目标是在 `planning` 目录下，基于当前 IEEE 33 节点数据，实现一个**简单、标准、可教学**的 Column-and-Constraint Generation，简称 CCG，储能鲁棒规划模型。

目标脚本：

- `planning/ccg_storage_ieee33.py`

当前已有的 `planning/benders_standard_storage_ieee33.py` 继续保留，用作确定性标准 Benders 对照。新的 CCG 脚本不复用 Benders cut 逻辑，不引入对偶 cut，不引入 fallback，不引入负荷削减兜底变量。第一版只做有限场景集上的标准 CCG，重点展示 CCG 的主问题、最坏场景 oracle、上下界更新和场景逐步加入过程。

## 项目公式规范

数学公式必须使用 Markdown 可直接渲染的 LaTeX：

- 块公式使用 `$$ ... $$`。
- 行内公式使用 `$...$`。
- 目标函数、约束、CCG 主问题、oracle、UB/LB 更新都必须写成渲染后可读的公式。
- 不使用人眼难读的转义文本公式。
- 每个第一次出现的重要符号都必须解释含义。

## 为什么这里用有限场景 CCG

完整连续不确定集合下的 CCG 通常需要解一个 adversarial max-min 问题。例如：

$$
\max_{\xi\in\Xi} Q(x,\xi)
$$

其中 $x$ 是储能选址和容量，$\xi$ 是负荷、DG、电价等不确定参数，$Q(x,\xi)$ 是给定规划和场景后的运行最优值。

如果 $\Xi$ 是连续集合，且运行问题包含 DistFlow SOCP，那么最坏场景子问题会变成较复杂的鲁棒优化和对偶化问题，不适合作为第一版教学脚本。

因此本项目先采用**有限场景集 CCG**：

$$
\Xi=\{\xi^1,\xi^2,\dots,\xi^S\}
$$

每轮固定当前储能规划 $x^k$，对所有候选场景逐个求一次运行子问题：

$$
Q_s(x^k)=Q(x^k,\xi^s)
$$

然后选出运行成本最高的场景：

$$
s^k\in\arg\max_{s\in\{1,\dots,S\}} Q_s(x^k)
$$

这个场景就是当前规划下的“最坏场景”。如果它还没有被主问题充分考虑，就把它加入主问题。这样可以清楚展示 CCG 的本质：**主问题只维护少数关键场景，oracle 每轮寻找新的坏场景，直到没有场景能继续恶化当前解。**

## 当前数据基础

新脚本直接读取：

- `network/case33.py`

使用其中已有数据：

| 符号 | 代码变量 | 含义 |
|---|---|---|
| $\mathcal B$ | `buses` | IEEE 33 节点集合，节点 $1$ 为平衡节点 |
| $\mathcal C$ | `candidate_buses` | 储能候选节点，取 $\mathcal B\setminus\{1\}$ |
| $\mathcal L$ | `branches` | IEEE 33 径向支路集合 |
| $\mathcal H$ | `hours` | 24 小时集合，$\mathcal H=\{0,\dots,23\}$ |
| $\mathcal G$ | `dg_buses` | DG 节点集合，当前为 $\{18,33\}$ |
| $S_{\text{base}}$ | `S_base` | 功率基准，当前为 10 MVA |
| $V_{\min},V_{\max}$ | `V_min`, `V_max` | 电压幅值上下界 |
| $r_\ell,x_\ell$ | `branch_df` | 支路 $\ell$ 的 p.u. 电阻、电抗 |
| $\overline S_\ell$ | `branch_df` | 支路 $\ell$ 的视在容量上限 |
| $\hat p^{\text{load}}_{bh}$ | `p_load_mw` | 基准有功负荷 |
| $\hat q^{\text{load}}_{bh}$ | `q_load_mvar` | 基准无功负荷 |
| $\overline p^{\text{DG}}_g$ | `p_dg_max` | 基准 DG 有功出力上限 |

## 不确定场景集合

第一版 CCG 使用显式有限场景集：

$$
\Xi=\{\xi^1,\xi^2,\dots,\xi^S\}
$$

每个场景 $\xi^s$ 包含三类倍率：

$$
\xi^s=
\left(
\alpha^{\text{load}}_{sh},
\alpha^{\text{DG}}_{sh},
\alpha^{\text{price}}_{sh}
\right)_{h\in\mathcal H}
$$

其中：

- $\alpha^{\text{load}}_{sh}$ 是场景 $s$、小时 $h$ 的负荷倍率。
- $\alpha^{\text{DG}}_{sh}$ 是场景 $s$、小时 $h$ 的 DG 可用容量倍率。
- $\alpha^{\text{price}}_{sh}$ 是场景 $s$、小时 $h$ 的电价倍率。

场景 $s$ 下的输入数据为：

$$
p^{\text{load}}_{bhs}
=
\alpha^{\text{load}}_{sh}
\hat p^{\text{load}}_{bh}
$$

$$
q^{\text{load}}_{bhs}
=
\alpha^{\text{load}}_{sh}
\hat q^{\text{load}}_{bh}
$$

$$
\overline p^{\text{DG}}_{ghs}
=
\alpha^{\text{DG}}_{sh}
\overline p^{\text{DG}}_g
$$

$$
c^{\text{grid}}_{hs}
=
\alpha^{\text{price}}_{sh}
\hat c^{\text{grid}}_h
$$

教学版场景表固定写在脚本顶部，不使用随机数：

| 场景编号 | 场景名 | 负荷倍率 | DG 倍率 | 电价倍率 | 用途 |
|---:|---|---|---|---|---|
| 0 | `base` | 全时段 1.00 | 全时段 1.00 | 全时段 1.00 | 基准代表日 |
| 1 | `evening_peak` | 17-20 点 1.18，其余 1.05 | 17-20 点 0.70，其余 0.90 | 17-20 点 1.25，其余 1.00 | 晚高峰高负荷、低 DG、高电价 |
| 2 | `heavy_load` | 全时段 1.12 | 全时段 0.85 | 全时段 1.05 | 全天重负荷 |
| 3 | `low_dg_high_price` | 全时段 1.05 | 全时段 0.45 | 7-20 点 1.20，其余 1.00 | DG 不足且电价偏高 |
| 4 | `midday_reverse` | 10-15 点 0.88，其余 1.00 | 10-15 点 1.25，其余 1.00 | 10-15 点 0.90，其余 1.00 | 中午低负荷、高 DG，可观察潮流方向变化 |
| 5 | `night_load` | 0-6 点 1.15，其余 1.00 | 全时段 0.90 | 全时段 1.00 | 夜间负荷偏高 |

第一版不加入负荷削减、软约束或惩罚变量。若某个场景导致模型不可行，应让求解器直接报错，然后调整场景表；不要在代码中写自动恢复逻辑。

## 第一阶段变量

CCG 的第一阶段变量表示储能规划方案：

| 符号 | 代码变量 | 含义 |
|---|---|---|
| $y_b$ | `y[b]` | 是否在候选节点 $b$ 建储能，二进制变量 |
| $\overline P_b$ | `p_cap[b]` | 节点 $b$ 的储能功率容量，MW |
| $\overline E_b$ | `e_cap[b]` | 节点 $b$ 的储能能量容量，MWh |
| $\eta$ | `eta` | 当前已加入场景中的最坏运行成本上界 |

其中：

$$
y_b\in\{0,1\}
$$

$$
\overline P_b\ge 0
$$

$$
\overline E_b\ge 0
$$

$$
\eta\ge 0
$$

注意：这里的 $\eta$ 不是 Benders 里的运行成本下界变量 $\theta$。在 CCG 主问题中，$\eta$ 是对已经加入场景的最坏运行成本做 epigraph 表达：

$$
\eta\ge Q_s(x),\quad s\in\mathcal S_k
$$

其中 $\mathcal S_k$ 是第 $k$ 轮主问题中已经加入的场景集合。

## 第一阶段投资成本

令 $d_b$ 为节点 $b$ 到平衡节点的馈线深度。投资成本为：

$$
C^{\text{inv}}(y,\overline P,\overline E)
=
\sum_{b\in\mathcal C}
\left[
\left(C^{\text{fix}}+C^{\text{depth}}d_b\right)y_b
+C^P\overline P_b
+C^E\overline E_b
\right]
$$

含义：

- $C^{\text{fix}}$：建站固定成本。
- $C^{\text{depth}}d_b$：节点越深，接入施工成本越高。
- $C^P\overline P_b$：功率容量投资成本。
- $C^E\overline E_b$：能量容量投资成本。

## 第一阶段规划约束

最多建设 $N_{\max}$ 个储能站：

$$
\sum_{b\in\mathcal C} y_b\le N_{\max}
$$

不建站则容量为 0：

$$
0\le \overline P_b\le M^P y_b
$$

$$
0\le \overline E_b\le M^E y_b
$$

其中 $M^P$ 和 $M^E$ 只用于关闭容量变量，不代表人为设备上限。

储能持续时间约束：

$$
T^{\min}\overline P_b
\le
\overline E_b
\le
T^{\max}\overline P_b
$$

## 第二阶段运行变量

对每个被加入主问题的场景 $s\in\mathcal S_k$，主问题中都要新增一套运行变量。这就是 CCG 里的 “column”。

| 符号 | 代码变量 | 含义 |
|---|---|---|
| $P_{\ell hs}$ | `P[s, br, h]` | 支路 $\ell$ 首端有功潮流，MW |
| $Q_{\ell hs}$ | `Q[s, br, h]` | 支路 $\ell$ 首端无功潮流，MVAr |
| $v_{bhs}$ | `v[s, b, h]` | 节点电压幅值平方，p.u. |
| $\ell_{\ell hs}$ | `ell[s, br, h]` | 支路电流幅值平方，p.u. |
| $p^{\text{grid}}_{hs}$ | `p_grid[s, h]` | 上级电网有功购电，MW |
| $q^{\text{grid}}_{hs}$ | `q_grid[s, h]` | 上级电网无功购电，MVAr |
| $p^{\text{DG}}_{ghs}$ | `p_dg[s, g, h]` | DG 有功出力，MW |
| $p^{\text{ch}}_{bhs}$ | `p_ch[s, b, h]` | 储能充电功率，MW |
| $p^{\text{dis}}_{bhs}$ | `p_dis[s, b, h]` | 储能放电功率，MW |
| $e_{bhs}$ | `e_sto[s, b, h]` | 储能电量，MWh |

## 场景运行成本

场景 $s$ 的运行成本为：

$$
C^{\text{op}}_s
=
\sum_{h\in\mathcal H}
c^{\text{grid}}_{hs}
p^{\text{grid}}_{hs}
+
\sum_{h\in\mathcal H}
\sum_{g\in\mathcal G}
C^{\text{DG}}p^{\text{DG}}_{ghs}
$$

储能循环成本为：

$$
C^{\text{cyc}}_s
=
\sum_{h\in\mathcal H}
\sum_{b\in\mathcal C}
C^{\text{cyc}}
\left(
p^{\text{ch}}_{bhs}
+
p^{\text{dis}}_{bhs}
\right)
$$

场景总运行成本为：

$$
Q_s(x)
=
C^{\text{op}}_s
+
C^{\text{cyc}}_s
$$

## 场景运行约束

以下约束对每个场景 $s$、每个小时 $h$ 都成立。

平衡节点电压：

$$
v_{1hs}=1
$$

上级电网功率等于首支路潮流。令 $\ell_0$ 表示平衡节点下游第一条支路：

$$
p^{\text{grid}}_{hs}=P_{\ell_0hs}
$$

$$
q^{\text{grid}}_{hs}=Q_{\ell_0hs}
$$

上级电网容量：

$$
0\le p^{\text{grid}}_{hs}\le S_{\text{base}}
$$

$$
0\le q^{\text{grid}}_{hs}\le \overline Q^{\text{grid}}
$$

DG 出力上限：

$$
0\le p^{\text{DG}}_{ghs}
\le
\overline p^{\text{DG}}_{ghs}
$$

对支路 $\ell=(i,j)$，DistFlow 电压降为：

$$
v_{jhs}
=
v_{ihs}
-2
\left(
r_\ell\frac{P_{\ell hs}}{S_{\text{base}}}
+
x_\ell\frac{Q_{\ell hs}}{S_{\text{base}}}
\right)
+
\left(r_\ell^2+x_\ell^2\right)
\ell_{\ell hs}
$$

电流锥约束为：

$$
\left\|
\left(
2\frac{P_{\ell hs}}{S_{\text{base}}},
2\frac{Q_{\ell hs}}{S_{\text{base}}},
v_{ihs}-\ell_{\ell hs}
\right)
\right\|_2
\le
v_{ihs}+\ell_{\ell hs}
$$

等价于：

$$
\left(\frac{P_{\ell hs}}{S_{\text{base}}}\right)^2
+
\left(\frac{Q_{\ell hs}}{S_{\text{base}}}\right)^2
\le
v_{ihs}\ell_{\ell hs}
$$

支路视在容量约束：

$$
P_{\ell hs}^2+Q_{\ell hs}^2
\le
\overline S_\ell^2
$$

电流平方上界：

$$
0\le \ell_{\ell hs}
\le
\frac{
\left(\overline S_\ell/S_{\text{base}}\right)^2
}{
V_{\min}^2
}
$$

节点 $b\ne 1$ 的有功平衡。令 $\pi(b)$ 为进入节点 $b$ 的父支路，$\operatorname{ch}(b)$ 为从节点 $b$ 出发的子支路集合：

$$
P_{\pi(b)hs}
=
p^{\text{load}}_{bhs}
+
p^{\text{ch}}_{bhs}
-
p^{\text{DG}}_{bhs}
-
p^{\text{dis}}_{bhs}
+
\sum_{\ell\in\operatorname{ch}(b)}
P_{\ell hs}
+
S_{\text{base}}r_{\pi(b)}
\ell_{\pi(b)hs}
$$

若节点 $b$ 没有 DG，则 $p^{\text{DG}}_{bhs}=0$。

节点 $b\ne 1$ 的无功平衡：

$$
Q_{\pi(b)hs}
=
q^{\text{load}}_{bhs}
+
\sum_{\ell\in\operatorname{ch}(b)}
Q_{\ell hs}
+
S_{\text{base}}x_{\pi(b)}
\ell_{\pi(b)hs}
$$

储能功率约束：

$$
0\le p^{\text{ch}}_{bhs}\le \overline P_b
$$

$$
0\le p^{\text{dis}}_{bhs}\le \overline P_b
$$

$$
p^{\text{ch}}_{bhs}
+
p^{\text{dis}}_{bhs}
\le
\overline P_b
$$

储能电量约束：

$$
e_{b0s}=\rho^0\overline E_b
$$

$$
\rho^{\min}\overline E_b
\le
e_{bhs}
\le
\overline E_b
$$

储能电量递推：

$$
e_{b,h+1,s}
=
e_{bhs}
+
\eta^{\text{ch}}p^{\text{ch}}_{bhs}
-
\frac{p^{\text{dis}}_{bhs}}{\eta^{\text{dis}}}
$$

其中 $h+1$ 对 24 小时循环取模，最后一个小时回到第 0 小时。

## CCG 主问题

第 $k$ 轮 CCG 主问题记为 $MP(\mathcal S_k)$。它只包含已经被加入的场景集合：

$$
\mathcal S_k\subseteq\{1,\dots,S\}
$$

在代码中，$\mathcal S_k$ 对应：

```python
active_scenarios
```

第一轮初始化为：

```python
active_scenarios = ["base"]
```

也就是说，第 1 轮主问题只考虑 `base` 场景，并不知道后面还有 `heavy_load`、`evening_peak` 等其他场景。其他场景要靠 oracle 在主问题求完后再检查。

### 主问题决策变量

第 $k$ 轮主问题的决策变量分为两类。

第一类是第一阶段规划变量，也就是所有场景共享的储能建设方案：

| 数学符号 | 代码变量 | 变量类型 | 单位 | 含义 |
|---|---|---|---|---|
| $y_b$ | `y[b]` | 二进制变量 | 无 | 是否在候选节点 $b$ 建设储能 |
| $\overline P_b$ | `p_cap[b]` | 连续变量 | MW | 节点 $b$ 的储能功率容量 |
| $\overline E_b$ | `e_cap[b]` | 连续变量 | MWh | 节点 $b$ 的储能能量容量 |
| $\eta$ | `eta` | 连续变量 | 成本单位 | 当前已加入场景中的最坏运行成本 |

其中 $b\in\mathcal C$，$\mathcal C=\mathcal B\setminus\{1\}$，也就是除了平衡节点以外的所有候选节点。

第二类是第二阶段运行变量。对每个已经加入主问题的场景 $s\in\mathcal S_k$，主问题都会新增一整套运行变量：

| 数学符号 | 代码变量 | 单位 | 含义 |
|---|---|---|---|
| $P_{\ell hs}$ | `P[br,h]` | MW | 场景 $s$ 下，支路 $\ell$ 在小时 $h$ 的首端有功潮流 |
| $Q_{\ell hs}$ | `Q[br,h]` | MVAr | 场景 $s$ 下，支路 $\ell$ 在小时 $h$ 的首端无功潮流 |
| $\ell_{\ell hs}$ | `ell[br,h]` | p.u. | 场景 $s$ 下，支路 $\ell$ 的电流幅值平方 |
| $v_{bhs}$ | `v[b,h]` | p.u. | 场景 $s$ 下，节点 $b$ 的电压幅值平方 |
| $p^{\text{grid}}_{hs}$ | `p_grid[h]` | MW | 场景 $s$ 下，小时 $h$ 的上级电网有功购电 |
| $q^{\text{grid}}_{hs}$ | `q_grid[h]` | MVAr | 场景 $s$ 下，小时 $h$ 的上级电网无功购电 |
| $p^{\text{DG}}_{ghs}$ | `p_dg[g,h]` | MW | 场景 $s$ 下，DG 节点 $g$ 在小时 $h$ 的有功出力 |
| $p^{\text{ch}}_{bhs}$ | `p_ch[b,h]` | MW | 场景 $s$ 下，节点 $b$ 储能充电功率 |
| $p^{\text{dis}}_{bhs}$ | `p_dis[b,h]` | MW | 场景 $s$ 下，节点 $b$ 储能放电功率 |
| $e_{bhs}$ | `e_sto[b,h]` | MWh | 场景 $s$ 下，节点 $b$ 储能电量 |

这些运行变量不是所有场景一开始都建出来，而是只对 $\mathcal S_k$ 中已经加入的场景建出来。比如第 1 轮只有 `base`，主问题只含 $z^{\text{base}}$；第 2 轮加入 `heavy_load` 后，主问题才同时含 $z^{\text{base}}$ 和 $z^{\text{heavy\_load}}$。

### 主问题目标函数

第 $k$ 轮主问题目标函数为：

$$
\min_{y,\overline P,\overline E,\eta,\{z^s\}_{s\in\mathcal S_k}}
\quad
C^{\text{inv}}(y,\overline P,\overline E)
+
\eta
$$

其中投资成本为：

$$
C^{\text{inv}}(y,\overline P,\overline E)
=
\sum_{b\in\mathcal C}
\left[
\left(C^{\text{fix}}+C^{\text{depth}}d_b\right)y_b
+
C^P\overline P_b
+
C^E\overline E_b
\right]
$$

目标函数由两部分组成：

- $C^{\text{inv}}$：第一阶段储能投资成本，包含建站固定成本、馈线深度接入成本、功率容量成本、能量容量成本。
- $\eta$：当前已加入场景中的最坏运行成本。

所以主问题不是最小化某一个场景的运行成本，而是最小化：

$$
\text{投资成本}
+
\text{当前已加入场景中的最大运行成本}
$$

### 第一阶段规划约束

储能选址变量为二进制变量：

$$
y_b\in\{0,1\},
\quad b\in\mathcal C
$$

功率容量和能量容量非负：

$$
\overline P_b\ge 0,
\quad b\in\mathcal C
$$

$$
\overline E_b\ge 0,
\quad b\in\mathcal C
$$

$\eta$ 为非负运行成本上界变量：

$$
\eta\ge 0
$$

最多建设 $N_{\max}$ 个储能站：

$$
\sum_{b\in\mathcal C}y_b
\le
N_{\max}
$$

当前代码中：

$$
N_{\max}=3
$$

未建站时功率容量必须为 0：

$$
\overline P_b
\le
M^P y_b,
\quad b\in\mathcal C
$$

未建站时能量容量必须为 0：

$$
\overline E_b
\le
M^E y_b,
\quad b\in\mathcal C
$$

其中 $M^P$ 和 $M^E$ 只是容量关闭用的大 $M$。在当前代码里：

$$
M^P=10
$$

$$
M^E=60
$$

储能持续时间约束为：

$$
T^{\min}\overline P_b
\le
\overline E_b
\le
T^{\max}\overline P_b,
\quad b\in\mathcal C
$$

当前代码中：

$$
T^{\min}=2,
\quad
T^{\max}=6
$$

这条约束表示：如果建了一个储能站，那么能量容量至少要能支撑 2 小时额定功率，最多支撑 6 小时额定功率。

### 已加入场景的 epigraph 约束

对每个已经加入主问题的场景 $s\in\mathcal S_k$，主问题都有一条：

$$
\eta
\ge
Q_s(y,\overline P,\overline E)
$$

展开为：

$$
\eta
\ge
C^{\text{op}}_s(z^s)
+
C^{\text{cyc}}_s(z^s),
\quad s\in\mathcal S_k
$$

其中场景 $s$ 的运行成本为：

$$
C^{\text{op}}_s(z^s)
=
\sum_{h\in\mathcal H}
c^{\text{grid}}_{hs}
p^{\text{grid}}_{hs}
+
\sum_{h\in\mathcal H}
\sum_{g\in\mathcal G}
C^{\text{DG}}
p^{\text{DG}}_{ghs}
$$

储能循环成本为：

$$
C^{\text{cyc}}_s(z^s)
=
\sum_{h\in\mathcal H}
\sum_{b\in\mathcal C}
C^{\text{cyc}}
\left(
p^{\text{ch}}_{bhs}
+
p^{\text{dis}}_{bhs}
\right)
$$

因此 $\eta$ 的实际含义是：

$$
\eta
\ge
\max_{s\in\mathcal S_k}
\left[
C^{\text{op}}_s(z^s)
+
C^{\text{cyc}}_s(z^s)
\right]
$$

注意这里的最大值只覆盖已经加入主问题的场景 $\mathcal S_k$，不是完整场景集 $\Xi$。完整场景集要由 oracle 在主问题求完后检查。

### 已加入场景的运行约束

对每个 $s\in\mathcal S_k$，主问题都包含一套完整的 DistFlow SOCP 运行约束。下面把 $s$ 固定为某个已加入场景。

平衡节点电压固定为 1：

$$
v_{1hs}=1,
\quad h\in\mathcal H
$$

所有节点电压幅值平方满足上下界：

$$
V_{\min}^2
\le
v_{bhs}
\le
V_{\max}^2,
\quad b\in\mathcal B,\ h\in\mathcal H
$$

上级电网功率等于首支路潮流。令 $\ell_0$ 为从平衡节点出发的第一条支路：

$$
p^{\text{grid}}_{hs}
=
P_{\ell_0hs},
\quad h\in\mathcal H
$$

$$
q^{\text{grid}}_{hs}
=
Q_{\ell_0hs},
\quad h\in\mathcal H
$$

上级电网购电范围：

$$
0
\le
p^{\text{grid}}_{hs}
\le
S_{\text{base}},
\quad h\in\mathcal H
$$

$$
0
\le
q^{\text{grid}}_{hs}
\le
\overline Q^{\text{grid}},
\quad h\in\mathcal H
$$

DG 出力上限：

$$
0
\le
p^{\text{DG}}_{ghs}
\le
\overline p^{\text{DG}}_{ghs},
\quad g\in\mathcal G,\ h\in\mathcal H
$$

对每条支路 $\ell=(i,j)$，DistFlow 电压降为：

$$
v_{jhs}
=
v_{ihs}
-2
\left(
r_\ell\frac{P_{\ell hs}}{S_{\text{base}}}
+
x_\ell\frac{Q_{\ell hs}}{S_{\text{base}}}
\right)
+
\left(r_\ell^2+x_\ell^2\right)
\ell_{\ell hs}
$$

电流锥约束为：

$$
\left\|
\left(
2\frac{P_{\ell hs}}{S_{\text{base}}},
2\frac{Q_{\ell hs}}{S_{\text{base}}},
v_{ihs}-\ell_{\ell hs}
\right)
\right\|_2
\le
v_{ihs}
+
\ell_{\ell hs}
$$

等价写法为：

$$
\left(\frac{P_{\ell hs}}{S_{\text{base}}}\right)^2
+
\left(\frac{Q_{\ell hs}}{S_{\text{base}}}\right)^2
\le
v_{ihs}
\ell_{\ell hs}
$$

支路视在容量约束：

$$
P_{\ell hs}^2
+
Q_{\ell hs}^2
\le
\overline S_\ell^2
$$

支路电流平方上限：

$$
0
\le
\ell_{\ell hs}
\le
\frac{
\left(\overline S_\ell/S_{\text{base}}\right)^2
}{
V_{\min}^2
}
$$

对每个非平衡节点 $b\ne 1$，有功平衡为：

$$
P_{\pi(b)hs}
=
p^{\text{load}}_{bhs}
+
p^{\text{ch}}_{bhs}
-
p^{\text{DG}}_{bhs}
-
p^{\text{dis}}_{bhs}
+
\sum_{\ell\in\operatorname{ch}(b)}
P_{\ell hs}
+
S_{\text{base}}
r_{\pi(b)}
\ell_{\pi(b)hs}
$$

无功平衡为：

$$
Q_{\pi(b)hs}
=
q^{\text{load}}_{bhs}
+
\sum_{\ell\in\operatorname{ch}(b)}
Q_{\ell hs}
+
S_{\text{base}}
x_{\pi(b)}
\ell_{\pi(b)hs}
$$

储能充电功率上限：

$$
0
\le
p^{\text{ch}}_{bhs}
\le
\overline P_b,
\quad b\in\mathcal C,\ h\in\mathcal H
$$

储能放电功率上限：

$$
0
\le
p^{\text{dis}}_{bhs}
\le
\overline P_b,
\quad b\in\mathcal C,\ h\in\mathcal H
$$

同一变流器下，充电和放电合计不超过功率容量：

$$
p^{\text{ch}}_{bhs}
+
p^{\text{dis}}_{bhs}
\le
\overline P_b,
\quad b\in\mathcal C,\ h\in\mathcal H
$$

初始 SOC：

$$
e_{b0s}
=
\rho^0
\overline E_b,
\quad b\in\mathcal C
$$

SOC 上下界：

$$
\rho^{\min}
\overline E_b
\le
e_{bhs}
\le
\overline E_b,
\quad b\in\mathcal C,\ h\in\mathcal H
$$

SOC 递推：

$$
e_{b,h+1,s}
=
e_{bhs}
+
\eta^{\text{ch}}
p^{\text{ch}}_{bhs}
-
\frac{
p^{\text{dis}}_{bhs}
}{
\eta^{\text{dis}}
},
\quad b\in\mathcal C,\ h\in\mathcal H
$$

其中 $h+1$ 对 24 小时循环取模。

### 主问题的紧凑形式

把上面所有约束合在一起，第 $k$ 轮主问题可以写成：

$$
\begin{aligned}
\min
\quad&
C^{\text{inv}}(y,\overline P,\overline E)+\eta
\\
\text{s.t.}\quad&
y_b\in\{0,1\},
\quad b\in\mathcal C
\\
&
\sum_{b\in\mathcal C}y_b\le N_{\max}
\\
&
0\le \overline P_b\le M^P y_b,
\quad b\in\mathcal C
\\
&
0\le \overline E_b\le M^E y_b,
\quad b\in\mathcal C
\\
&
T^{\min}\overline P_b
\le
\overline E_b
\le
T^{\max}\overline P_b,
\quad b\in\mathcal C
\\
&
z^s\in Z(y,\overline P,\overline E,\xi^s),
\quad s\in\mathcal S_k
\\
&
\eta
\ge
C^{\text{op}}_s(z^s)
+
C^{\text{cyc}}_s(z^s),
\quad s\in\mathcal S_k
\end{aligned}
$$

其中 $Z(y,\overline P,\overline E,\xi^s)$ 就是上面展开的该场景 DistFlow SOCP 运行可行域。

### 第 1 轮主问题的实际结果

第 1 轮时：

$$
\mathcal S_1=\{\texttt{base}\}
$$

因此第 1 轮主问题实际求的是：

$$
\min
\quad
C^{\text{inv}}(y,\overline P,\overline E)
+
\eta
$$

$$
\text{s.t.}
\quad
\eta
\ge
Q_{\texttt{base}}(y,\overline P,\overline E)
$$

以及全部储能规划约束和 `base` 场景下的 DistFlow SOCP 运行约束。

第 1 轮主问题求得：

| 项目 | 数值 |
|---|---:|
| 已加入场景 $\mathcal S_1$ | `base` |
| 建设节点 | 2 |
| $y_2$ | 1 |
| 其他候选节点 $y_b$ | 0 |
| $\overline P_2$ | 7.669371 MW |
| $\overline E_2$ | 46.016227 MWh |
| 持续时间 $\overline E_2/\overline P_2$ | 6.000000 h |
| 投资成本 $C^{\text{inv}}$ | 710.243407 |
| 主问题 $\eta$ | 4779.345233 |
| 主问题目标值 $LB^1$ | 5489.588640 |

第 1 轮主问题目标值计算为：

$$
LB^1
=
710.243407
+
4779.345233
=
5489.588640
$$

这个结果的含义是：如果只考虑 `base` 场景，模型认为在节点 2 建一个 7.669371 MW、46.016227 MWh 的储能站已经足够好，对应的 `base` 场景运行成本由 $\eta$ 表示，为 4779.345233。

但这只是对 `base` 场景鲁棒，不代表对完整场景集合 $\Xi$ 鲁棒。因此主问题结束后，oracle 会固定这个方案，枚举全部 6 个场景。

第 1 轮 oracle 检查得到完整场景集最坏场景为：

$$
s^1=\texttt{heavy\_load}
$$

对应最坏运行成本为：

$$
Q_{\texttt{heavy\_load}}(x^1)
=
5691.649156
$$

所以第 1 轮完整场景集上界为：

$$
UB^1
=
C^{\text{inv}}(x^1)
+
Q_{\texttt{heavy\_load}}(x^1)
$$

$$
UB^1
=
710.243407
+
5691.649156
=
6401.892563
$$

第 1 轮场景违反量为：

$$
\operatorname{violation}^1
=
Q_{\texttt{heavy\_load}}(x^1)
-
\eta^1
$$

$$
\operatorname{violation}^1
=
5691.649156
-
4779.345233
=
912.303923
$$

因为：

$$
912.303923>0.01
$$

第 1 轮没有收敛，必须把 `heavy_load` 加入主问题：

$$
\mathcal S_2
=
\{\texttt{base},\texttt{heavy\_load}\}
$$

每加入一个新场景，主问题就新增：

- 一套运行变量 $z^s$。
- 一套 DistFlow SOCP 运行约束。
- 一条 epigraph 约束 $\eta\ge Q_s(x)$。

这就是 CCG 中的 “column” 和 “constraint”。

## 最坏场景 oracle

第 $k$ 轮主问题求出当前规划：

$$
x^k=
\left(
y^k,
\overline P^k,
\overline E^k
\right)
$$

然后 oracle 固定 $x^k$，对每个候选场景 $s\in\{1,\dots,S\}$ 求一次运行子问题：

$$
Q_s(x^k)
=
\min_{z^s}
\quad
C^{\text{op}}_s(z^s)
+
C^{\text{cyc}}_s(z^s)
$$

$$
\text{s.t.}
\quad
z^s\in Z(x^k,\xi^s)
$$

最坏场景为：

$$
s^k
\in
\arg\max_{s\in\{1,\dots,S\}}
Q_s(x^k)
$$

最坏运行成本为：

$$
Q^{\text{worst}}(x^k)
=
Q_{s^k}(x^k)
$$

教学版 oracle 直接枚举有限场景集，不做随机采样，不跳过场景，不做启发式筛选。

## 上下界和收敛判据

第 $k$ 轮主问题目标值是当前鲁棒问题的下界：

$$
LB^k
=
C^{\text{inv}}(x^k)
+
\eta^k
$$

固定当前规划 $x^k$ 后，对完整场景集 $\Xi$ 求到的真实最坏成本给出一个可行上界候选：

$$
UB^{\text{cand},k}
=
C^{\text{inv}}(x^k)
+
Q^{\text{worst}}(x^k)
$$

累计上界更新为：

$$
UB^k
=
\min
\left(
UB^{k-1},
UB^{\text{cand},k}
\right)
$$

绝对 gap：

$$
\operatorname{gap}^k
=
UB^k-LB^k
$$

相对 gap：

$$
\operatorname{relgap}^k
=
\frac{UB^k-LB^k}{\max(1,|UB^k|)}
$$

场景违反量：

$$
\operatorname{viol}^k
=
Q^{\text{worst}}(x^k)-\eta^k
$$

收敛条件：

$$
\operatorname{viol}^k\le \varepsilon
$$

等价地说：当前完整场景集中已经没有任何场景的运行成本超过主问题中的 $\eta^k$。此时当前方案对所有候选场景都已经鲁棒。

因为 $\Xi$ 是有限集合，且每轮至少加入一个新的违反场景，所以算法最多运行 $S$ 轮后收敛。

## CCG 迭代流程

初始化：

$$
\mathcal S_0=\{\texttt{base}\}
$$

第 $k$ 轮：

1. 求解主问题 $MP(\mathcal S_k)$。
2. 得到当前储能规划 $x^k$ 和 $\eta^k$。
3. 对所有候选场景 $s\in\Xi$ 求固定规划下的运行子问题 $Q_s(x^k)$。
4. 选出最坏场景 $s^k$。
5. 计算 $LB^k$、$UB^k$、$\operatorname{gap}^k$ 和 $\operatorname{viol}^k$。
6. 若 $\operatorname{viol}^k\le\varepsilon$，停止。
7. 否则令：

$$
\mathcal S_{k+1}
=
\mathcal S_k
\cup
\{s^k\}
$$

继续下一轮。

## 需要输出的迭代表

`ccg_progress` 至少包含：

| 列名 | 含义 |
|---|---|
| `iteration` | CCG 轮数 |
| `active_scenarios` | 当前主问题已加入场景 |
| `new_worst_scenario` | 本轮 oracle 找到的最坏场景 |
| `investment` | 当前储能投资成本 |
| `eta` | 主问题中的最坏运行成本变量 |
| `worst_operation` | oracle 得到的完整场景集最坏运行成本 |
| `LB` | 当前下界 |
| `UB` | 当前累计上界 |
| `gap` | 绝对 gap |
| `relgap` | 相对 gap |
| `violation` | $Q^{\text{worst}}(x^k)-\eta^k$ |
| `built_buses` | 当前建设的储能节点 |
| `p_cap_sum_mw` | 当前总功率容量 |
| `e_cap_sum_mwh` | 当前总能量容量 |

`scenario_costs` 至少包含：

| 列名 | 含义 |
|---|---|
| `iteration` | CCG 轮数 |
| `scenario` | 场景名 |
| `operation_cost` | 固定当前规划后的运行成本 |
| `is_worst` | 是否为本轮最坏场景 |
| `is_active` | 本轮求解主问题前是否已加入 |

## 需要输出的结果文件

Excel：

- `results/planning/ccg/ccg_storage_ieee33_summary.xlsx`

建议工作表：

- `summary`：最终鲁棒目标值、投资成本、最坏运行成本、最坏场景、迭代次数。
- `scenario_pool`：完整候选场景定义。
- `ccg_progress`：每轮 CCG 过程。
- `scenario_costs`：每轮每个场景的 oracle 运行成本。
- `storage_plan`：最终储能选址和容量。
- `worst_system_dispatch`：最终最坏场景的系统运行。
- `worst_node_balance`：最终最坏场景的节点平衡。
- `worst_branch_flow`：最终最坏场景的支路潮流和锥 gap。

图：

- `results/planning/ccg/ccg_01_convergence.png`：CCG 的 UB、LB、gap 收敛图。
- `results/planning/ccg/ccg_02_scenario_costs.png`：每轮各场景运行成本，突出最坏场景。
- `results/planning/ccg/ccg_03_storage_plan.png`：最终储能选址、功率容量、能量容量。
- `results/planning/ccg/ccg_04_worst_voltage.png`：最终最坏场景下 33 个节点 24 小时电压。
- `results/planning/ccg/ccg_05_worst_power_balance.png`：最终最坏场景下 33 个节点有功平衡图。

## 实现步骤

第一步：新建脚本。

- 新建 `planning/ccg_storage_ieee33.py`。
- 直接从 `network.case33` 导入 IEEE 33 数据。
- 复用当前成本参数、储能参数、DistFlow SOCP 公式。
- 不从 Benders 脚本 import 函数，避免两个实验脚本互相缠绕。

第二步：写固定场景表。

- 用一个紧凑的 `pd.DataFrame` 保存场景编号和名称。
- 用显式循环生成每个场景的 24 小时倍率。
- 不使用随机数。

第三步：写场景数据函数。

给定场景编号 $s$，生成：

$$
p^{\text{load}}_{bhs}
$$

$$
q^{\text{load}}_{bhs}
$$

$$
\overline p^{\text{DG}}_{ghs}
$$

$$
c^{\text{grid}}_{hs}
$$

该函数只做倍率相乘，不做兜底和自动修正。

第四步：写场景运行约束函数。

函数职责：

- 在模型中添加场景 $s$ 的运行变量。
- 添加储能运行约束。
- 添加 DG、节点平衡、DistFlow SOCP、电压和支路约束。
- 返回该场景运行成本表达式和运行变量。

建议函数名：

- `add_scenario_operation(m, s, y, p_cap, e_cap)`

其中主问题调用时，`p_cap` 和 `e_cap` 是变量；oracle 调用时，`p_cap` 和 `e_cap` 是固定数值。

第五步：写 CCG 主问题。

建议函数名：

- `build_master(active_scenarios)`

输入：

$$
\mathcal S_k
$$

输出：

- Gurobi 模型。
- 第一阶段变量。
- 每个 active scenario 的运行成本表达式。
- 每个 active scenario 的运行变量，供最终导出。

第六步：写 oracle。

建议函数名：

- `solve_operation_for_fixed_plan(s, y_bar, p_bar, e_bar)`

该函数固定当前规划，求单个场景的运行 SOCP：

$$
Q_s(x^k)
$$

CCG 每轮对所有场景调用一次该函数，选出最大者。

第七步：写 CCG 主循环。

伪代码：

```text
active_scenarios = ["base"]
UB = infinity

for k in range(max_iter):
    solve MP(active_scenarios)
    read x_k, eta_k, investment_k

    for s in all_scenarios:
        solve Q_s(x_k)

    worst_scenario = argmax_s Q_s(x_k)
    worst_operation = max_s Q_s(x_k)
    LB = investment_k + eta_k
    UB = min(UB, investment_k + worst_operation)
    violation = worst_operation - eta_k

    save progress row

    if violation <= tol:
        break

    active_scenarios.add(worst_scenario)
```

第八步：导出最终结果。

最终结果应该使用最终规划 $x^\star$，并对最终最坏场景重新求一次运行，导出：

- 储能选址和容量。
- 系统运行。
- 节点平衡。
- 支路潮流。
- 锥 gap。

第九步：绘图。

绘图只使用导出的表，不重新求解模型。

重点检查：

$$
\text{soc\_gap}_{\ell hs}
=
v_{ihs}\ell_{\ell hs}
-
\left(\frac{P_{\ell hs}}{S_{\text{base}}}\right)^2
-
\left(\frac{Q_{\ell hs}}{S_{\text{base}}}\right)^2
$$

节点有功平衡残差：

$$
\text{res}^{P}_{bhs}
=
p^{\text{in}}_{bhs}
-
p^{\text{loss}}_{bhs}
-
p^{\text{out}}_{bhs}
-
p^{\text{load}}_{bhs}
-
p^{\text{ch}}_{bhs}
+
p^{\text{DG}}_{bhs}
+
p^{\text{dis}}_{bhs}
$$

储能电量残差：

$$
\text{res}^{E}_{bhs}
=
e_{b,h+1,s}
-
e_{bhs}
-
\eta^{\text{ch}}p^{\text{ch}}_{bhs}
+
\frac{p^{\text{dis}}_{bhs}}{\eta^{\text{dis}}}
$$

## 与当前 Benders 脚本的区别

当前 Benders 脚本求解的是确定性问题：

$$
\min_x
\quad
C^{\text{inv}}(x)+Q(x)
$$

其中只有一个基准运行场景。

新的 CCG 脚本求解的是有限场景鲁棒问题：

$$
\min_x
\quad
C^{\text{inv}}(x)
+
\max_{s\in\Xi}Q_s(x)
$$

Benders 的核心是用 cut 近似运行成本函数 $Q(x)$。CCG 的核心是逐步加入场景，每个加入的场景都带来一整套运行变量和运行约束。

因此新脚本中：

- 不使用 $\theta$。
- 不使用 Benders optimality cut。
- 不读取 SOCP 对偶变量生成 cut。
- 使用 $\eta$ 表示已加入场景的最坏运行成本。
- 使用 oracle 寻找完整场景集中的最坏场景。

## 教学时应该重点解释的结果

第一，为什么第一轮只考虑 `base` 场景。因为 CCG 不一开始加载所有场景，而是让主问题先给出一个便宜的初始规划。

第二，为什么 oracle 会找到新场景。因为当前规划可能只对 `base` 场景便宜，对 `evening_peak` 或 `low_dg_high_price` 并不鲁棒。

第三，为什么加入新场景后投资容量可能增加。因为主问题现在必须同时满足更多场景，并让 $\eta$ 覆盖这些场景的运行成本。

第四，为什么收敛时不一定所有场景都被加入。因为只要未加入场景的运行成本都不超过当前 $\eta$，它们就不会改变鲁棒最优解。

第五，为什么有限场景 CCG 是确定性的。因为候选场景表固定，oracle 每轮枚举所有场景，没有随机抽样。

## 不允许加入的内容

第一版教学 CCG 不加入以下内容：

- 不加负荷削减变量。
- 不加电压越限惩罚变量。
- 不加场景不可行自动修复。
- 不加随机场景生成。
- 不加连续不确定集合的对偶化。
- 不加多层类封装。
- 不加配置文件系统。
- 不加和 CCG 无关的网络图重构。

如果求解失败，直接暴露 Gurobi 状态和报错，按研究项目方式修改场景表或模型公式。

## 如何学习这份 CCG 代码

建议按下面的顺序阅读 `planning/ccg_storage_ieee33.py`。

第一步，先看场景集合。

对应代码：

- `build_scenario_pool()`
- `scenario_data(scenario)`

这里定义的是有限不确定集合：

$$
\Xi=\{\texttt{base},\texttt{evening\_peak},\texttt{heavy\_load},\texttt{low\_dg\_high\_price},\texttt{midday\_reverse},\texttt{night\_load}\}
$$

`build_scenario_pool()` 只定义每个场景的倍率：

$$
\alpha^{\text{load}}_{sh},
\alpha^{\text{DG}}_{sh},
\alpha^{\text{price}}_{sh}
$$

`scenario_data(scenario)` 把倍率变成模型数据：

$$
p^{\text{load}}_{bhs}
=
\alpha^{\text{load}}_{sh}
\hat p^{\text{load}}_{bh}
$$

$$
\overline p^{\text{DG}}_{ghs}
=
\alpha^{\text{DG}}_{sh}
\overline p^{\text{DG}}_g
$$

$$
c^{\text{grid}}_{hs}
=
\alpha^{\text{price}}_{sh}
\hat c^{\text{grid}}_h
$$

第二步，看一个场景的运行模型。

对应代码：

- `add_scenario_operation(m, scenario, p_cap, e_cap, tag)`

这个函数是整个 CCG 里最重要的建模函数。它向模型中加入一个场景 $s$ 的完整运行变量：

$$
z^s=
\left(
P_{\ell hs},
Q_{\ell hs},
v_{bhs},
\ell_{\ell hs},
p^{\text{grid}}_{hs},
p^{\text{DG}}_{ghs},
p^{\text{ch}}_{bhs},
p^{\text{dis}}_{bhs},
e_{bhs}
\right)
$$

并加入这个场景的全部运行约束：

- DistFlow 电压方程。
- SOCP 电流锥。
- 支路视在容量约束。
- 节点有功、无功平衡。
- DG 出力上限。
- 储能充放电功率约束。
- 储能 SOC 递推约束。

这个函数被重复使用两次：

- 在主问题中，`p_cap` 和 `e_cap` 是第一阶段容量变量。
- 在 oracle 中，`p_cap` 和 `e_cap` 是已经固定的容量数值。

这就是教学版代码最关键的简化：同一套物理运行约束，同时服务主问题和 oracle。

第三步，看 CCG 主问题。

对应代码：

- `build_master(active_scenarios)`

第 $k$ 轮主问题只包含已经加入的场景集合 $\mathcal S_k$：

$$
\mathcal S_k\subseteq\Xi
$$

主问题变量包括：

$$
y_b,\quad \overline P_b,\quad \overline E_b,\quad \eta,\quad z^s,\ s\in\mathcal S_k
$$

主问题目标为：

$$
\min
\quad
C^{\text{inv}}(y,\overline P,\overline E)
+
\eta
$$

每加入一个场景 $s$，主问题就新增一套运行变量 $z^s$ 和一条 epigraph 约束：

$$
\eta\ge Q_s(y,\overline P,\overline E)
$$

这里的 $\eta$ 含义非常重要：它不是 Benders 的 $\theta$。$\eta$ 表示当前已经加入场景中的最坏运行成本。

第四步，看最坏场景 oracle。

对应代码：

- `solve_operation_for_fixed_plan(scenario, p_bar, e_bar)`

主问题求完后，会得到当前规划：

$$
x^k=
\left(
y^k,\overline P^k,\overline E^k
\right)
$$

oracle 固定这个规划，对每个候选场景求运行问题：

$$
Q_s(x^k)
=
\min_{z^s}
\quad
C^{\text{op}}_s(z^s)
+
C^{\text{cyc}}_s(z^s)
$$

然后枚举全部场景并选最大者：

$$
s^k
\in
\arg\max_{s\in\Xi}
Q_s(x^k)
$$

这一步回答的问题是：当前储能规划在所有候选场景里，最怕哪一个？

第五步，看主循环。

对应代码从：

- `active_scenarios = ["base"]`

开始。

每一轮执行：

1. 求解只含 `active_scenarios` 的主问题。
2. 读取当前储能规划 $x^k$。
3. 固定 $x^k$，对完整场景集 $\Xi$ 逐个求运行成本。
4. 找到最坏场景 $s^k$。
5. 计算：

$$
LB^k
=
\text{master objective}
$$

$$
UB^{\text{cand},k}
=
C^{\text{inv}}(x^k)
+
\max_{s\in\Xi}Q_s(x^k)
$$

$$
UB^k
=
\min(UB^{k-1},UB^{\text{cand},k})
$$

$$
\operatorname{violation}^k
=
\max_{s\in\Xi}Q_s(x^k)-\eta^k
$$

6. 如果 $\operatorname{violation}^k\le\varepsilon$，说明所有候选场景都已经被当前 $\eta^k$ 覆盖，算法停止。
7. 否则把最坏场景加入 `active_scenarios`。

第六步，理解为什么它叫 Column-and-Constraint Generation。

当发现新场景 $s^k$ 后，下一轮主问题会新增：

$$
z^{s^k}
$$

这是一组新的运行变量，所以叫生成 column。

同时新增：

$$
z^{s^k}\in Z(x,\xi^{s^k})
$$

和：

$$
\eta\ge Q_{s^k}(x)
$$

这些是新的约束，所以叫生成 constraint。

所以 CCG 的名字不是抽象名词，而是代码中真实发生的动作：每发现一个最坏场景，就把这个场景的一整套变量和约束加进主问题。

## 当前执行结果

当前已经按本文档实现：

- `planning/ccg_storage_ieee33.py`
- `results/planning/ccg/ccg_storage_ieee33_summary.xlsx`
- `results/planning/ccg/ccg_01_convergence.png`
- `results/planning/ccg/ccg_02_scenario_costs.png`
- `results/planning/ccg/ccg_03_storage_plan.png`
- `results/planning/ccg/ccg_04_worst_voltage.png`
- `results/planning/ccg/ccg_05_worst_power_balance.png`

本次 CCG 使用 6 个候选场景：

- `base`
- `evening_peak`
- `heavy_load`
- `low_dg_high_price`
- `midday_reverse`
- `night_load`

迭代过程如下：

| 轮次 | 主问题已加入场景 | oracle 找到的最坏场景 | 投资成本 | $\eta$ | 完整场景集最坏运行成本 | $LB$ | $UB$ | gap | violation |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `base` | `heavy_load` | 710.243407 | 4779.345233 | 5691.649156 | 5489.588640 | 6401.892563 | 912.303923 | 912.303923 |
| 2 | `base,heavy_load` | `heavy_load` | 856.717338 | 5529.769484 | 5529.770942 | 6386.486822 | 6386.488280 | 0.001458 | 0.001458 |

第 1 轮主问题只考虑 `base`，因此得到的是基准日下便宜的储能方案。oracle 枚举全部 6 个场景后发现 `heavy_load` 的运行成本最高，因此把 `heavy_load` 加入主问题。

第 2 轮主问题同时考虑 `base` 和 `heavy_load`，此时 oracle 再次枚举全部场景，最坏场景仍然是 `heavy_load`，且违反量已经降到 0.001458，小于教学版 CCG 收敛容差 0.01，因此停止。

最终鲁棒规划结果：

| 指标 | 数值 |
|---|---:|
| 鲁棒目标值 | 6386.488280 |
| 投资成本 | 856.717338 |
| 最坏场景运行成本 | 5529.770942 |
| 最坏场景 | `heavy_load` |
| 建设节点 | 2 |
| 功率容量 | 9.296859 MW |
| 能量容量 | 55.781156 MWh |
| 持续时间 | 6.000000 h |

第 2 轮固定最终规划后，完整场景集运行成本排序为：

| 场景 | 运行总成本 |
|---|---:|
| `heavy_load` | 5529.770942 |
| `low_dg_high_price` | 5182.626822 |
| `evening_peak` | 5112.001106 |
| `night_load` | 4743.662987 |
| `base` | 4640.912667 |
| `midday_reverse` | 4380.893925 |

最终最坏场景校验：

| 校验项 | 数值 |
|---|---:|
| 最大有功节点平衡残差 | $5.01\times 10^{-7}$ MW |
| 最大无功节点平衡残差 | $6.92\times 10^{-8}$ MVAr |
| 最大储能电量递推残差 | $5.92\times 10^{-7}$ MWh |
| 最小锥 gap | $3.61\times 10^{-8}$ |
| 最大锥 gap | $1.36\times 10^{-6}$ |
