# 当前配电网优化模型说明

本文档按“问题变量定义、真正的 AC 电力系统原始模型、DC 潮流近似、SDP 松弛、非凸 DistFlow OPF、DistFlow SOCP 松弛、LinDistFlow 线性化近似”的顺序说明当前仓库中的五份优化代码：

- `opf/opf_ac.py`：用矩形坐标 $e,f$ 直接求解节点导纳形式的非凸 AC OPF。
- `opf/opf_dc.py`：进一步忽略无功、电压幅值和损耗，只保留有功-相角关系的 DC 潮流近似。
- `opf/opf_sdp.py`：把 $W=\tilde V\tilde V^H$ 作为变量，删除 rank-1 约束得到 SDP 凸松弛。
- `opf/opf_distflow.py`：由非凸 DistFlow OPF 做二阶锥松弛得到的连续 SOCP/凸 QCP。
- `opf/opf_lindistflow.py`：在 DistFlow 基础上忽略线路损耗和电流平方项得到的线性化近似模型。

当前项目已经删除电容器投切变量，因此没有二进制变量，不是 MISOCP，也不是 MILP。

## 1. 问题变量定义

当前算例是 6 节点径向配电网，1 号节点为平衡节点，支路方向从上游到下游。

| 支路 | 起点 | 终点 | $r_\ell$ | $x_\ell$ | $\bar S_\ell$ MVA |
| --- | ---: | ---: | ---: | ---: | ---: |
| L12 | 1 | 2 | 0.010 | 0.030 | 6.0 |
| L23 | 2 | 3 | 0.012 | 0.025 | 4.5 |
| L34 | 3 | 4 | 0.010 | 0.020 | 4.0 |
| L45 | 4 | 5 | 0.011 | 0.022 | 3.5 |
| L56 | 5 | 6 | 0.009 | 0.018 | 3.0 |

集合和参数：

- 时段集合：$\mathcal T=\{0,1,\dots,23\}$。
- 节点集合：$\mathcal B=\{1,2,3,4,5,6\}$。
- 非平衡节点集合：$\mathcal B^+=\mathcal B\setminus\{1\}$。
- 支路集合：$\mathcal E$。
- 支路 $\ell$ 的首端和末端分别为 $f(\ell)$、$t(\ell)$。
- 非平衡节点 $i$ 的父支路为 $\pi(i)$。
- 从节点 $i$ 出发的子支路集合为 $\mathcal C(i)$。
- 基准容量：$S_{\text{base}}=10.0$ MVA。
- 电压范围：$V_{\min}=0.95$，$V_{\max}=1.05$。
- 6 号节点 DG 出力范围：$0\le p_t^{DG}\le 0.8$ MW。
- 变电站有功购电范围：$0\le p_t^{grid}\le 6.0$ MW。
- 变电站无功注入范围：$0\le q_t^{grid}\le 1.5$ MVAr。

负荷由基值和 24 小时倍率生成。负荷功率因数固定为 0.95：

$$
\bar q_i^L=\bar p_i^L\tan(\arccos(0.95)).
$$

若节点 $i$ 的负荷类型为 $c_i$，小时 $t$ 的倍率为 $\alpha_{c_i,t}$，则：

$$
p_{i,t}^L=\bar p_i^L\alpha_{c_i,t},\qquad
q_{i,t}^L=\bar q_i^L\alpha_{c_i,t}.
$$

当前代码为了让输出结果直观，潮流和注入变量保留工程单位：

- $P_{\ell,t}$：支路有功潮流，MW。
- $Q_{\ell,t}$：支路无功潮流，MVAr。
- $p_t^{grid}$：变电站有功购电，MW。
- $q_t^{grid}$：变电站无功注入，MVAr。
- $p_t^{DG}$：6 号节点 DG 有功出力，MW。
- $v_{i,t}$：节点电压幅值平方，p.u. squared。
- $\ell_{\ell,t}$：支路电流幅值平方，p.u. current squared，仅 DistFlow 模型使用。

DistFlow 的电压方程和电流关系通常写在 p.u. 系统中，因此代码内部使用：

$$
p_{\ell,t}=\frac{P_{\ell,t}}{S_{\text{base}}},\qquad
q_{\ell,t}=\frac{Q_{\ell,t}}{S_{\text{base}}}.
$$

这里 $p_{\ell,t}$ 和 $q_{\ell,t}$ 是 p.u. 有功、无功。$S_{\text{base}}$ 的作用不是改变物理功率，而是把 MW/MVAr 数值转换到和 $r_\ell$、$x_\ell$、$v_{i,t}$、$\ell_{\ell,t}$ 一致的 p.u. 尺度。

五份模型使用相同目标函数：

$$
\min \sum_{t\in\mathcal T}
\left(c_t^{grid}p_t^{grid}+c^{DG}p_t^{DG}\right),
\qquad c^{DG}=85.0.
$$

购电电价 $c_t^{grid}$ 为：

| 小时 | 电价 |
| --- | ---: |
| 0-6 | 45 |
| 7-11 | 70 |
| 12-16 | 90 |
| 17-20 | 120 |
| 21-23 | 75 |

## 2. 原始模型：AC 电力系统原始 OPF

真正的电力系统原始模型通常从节点复电压、线路阻抗和基尔霍夫电流定律开始建立，也就是 AC 潮流/AC OPF。它直接描述每个节点的电压相量、注入电流和注入复功率，尚未引入 DistFlow 的支路功率、电压平方、电流平方变量。

下面先用 p.u. 系统推导网络方程。代码中的 $p^{grid}$、$q^{grid}$、$p^{DG}$、$p^L$、$q^L$ 仍以 MW/MVAr 记录，因此进入 AC 方程时需要除以 $S_{\text{base}}$。

### 2.1 节点电压相量

每个节点 $i$ 在小时 $t$ 的电压不是单独一个实数，而是一个复数相量：

$$
\tilde V_{i,t}=V_{i,t}e^{\mathrm j\theta_{i,t}},
\qquad i\in\mathcal B,\ t\in\mathcal T.
$$

其中 $V_{i,t}$ 是电压幅值，$\theta_{i,t}$ 是电压相角。也可以写成直角坐标形式：

$$
\tilde V_{i,t}=e_{i,t}+\mathrm jf_{i,t}.
$$

除平衡节点固定参考外，AC 潮流的状态变量本质上就是节点电压幅值和相角：

$$
\{V_{i,t},\theta_{i,t}\}_{i\in\mathcal B}.
$$

平衡节点用于给出相角参考，并通常固定电压幅值：

$$
\theta_{1,t}=0,\qquad V_{1,t}=1.0.
$$

### 2.2 线路阻抗和导纳

对一条线路 $(i,j)$，已知线路阻抗：

$$
z_{ij}=r_{ij}+\mathrm jx_{ij}.
$$

忽略线路并联电纳时，串联导纳为：

$$
y_{ij}=\frac{1}{z_{ij}}=g_{ij}+\mathrm jb_{ij}.
$$

当前算例的数据就是线路 $r$、$x$。AC 原始模型会先由这些线路参数组装节点导纳矩阵 $Y$：

$$
\mathcal N(i)=\{j\mid i\text{ 与 }j\text{ 之间有线路连接}\}.
$$

$$
Y_{ij}=
\begin{cases}
-y_{ij}, & i\ne j,\ j\in\mathcal N(i),\\
0, & i\ne j,\ j\notin\mathcal N(i),\\
\sum_{k\in\mathcal N(i)}y_{ik}, & i=j.
\end{cases}
$$

记：

$$
Y=G+\mathrm jB.
$$

其中 $G_{ij}$ 是电导矩阵元素，$B_{ij}$ 是电纳矩阵元素。

### 2.3 从欧姆定律到节点电流方程

对线路 $(i,j)$，从节点 $i$ 流向节点 $j$ 的电流为：

$$
\tilde I_{ij,t}=y_{ij}(\tilde V_{i,t}-\tilde V_{j,t}).
$$

节点 $i$ 向网络注入的总电流等于所有相邻线路电流之和：

$$
\tilde I_{i,t}^{inj}=\sum_{j\in\mathcal N(i)}\tilde I_{ij,t}.
$$

把上面的线路电流代入，并用节点导纳矩阵整理，就得到节点电流方程：

$$
\tilde I_{i,t}^{inj}
=\sum_{j\in\mathcal B}Y_{ij}\tilde V_{j,t}.
$$

这一步只使用了欧姆定律和 KCL，仍然是线性的电压-电流关系。

### 2.4 从节点电流到节点复功率

电力系统优化通常给定和约束的是功率，而不是电流。节点注入复功率定义为：

$$
\tilde S_{i,t}^{inj}
=P_{i,t}^{inj}+\mathrm jQ_{i,t}^{inj}
=\tilde V_{i,t}\left(\tilde I_{i,t}^{inj}\right)^*.
$$

注意这里是电流共轭，因为交流复功率定义为 $\tilde S=\tilde V\tilde I^*$。

把节点电流方程代入：

$$
\tilde S_{i,t}^{inj}
=\tilde V_{i,t}
\left(\sum_{j\in\mathcal B}Y_{ij}\tilde V_{j,t}\right)^*
=\tilde V_{i,t}
\sum_{j\in\mathcal B}Y_{ij}^*\tilde V_{j,t}^*.
$$

到这里，非线性已经出现：功率是电压和电压共轭的乘积。

### 2.5 展开成有功和无功潮流方程

令：

$$
\delta_{ij,t}=\theta_{i,t}-\theta_{j,t}.
$$

因为：

$$
Y_{ij}^*=G_{ij}-\mathrm jB_{ij},
\qquad
\tilde V_{i,t}\tilde V_{j,t}^*
=V_{i,t}V_{j,t}e^{\mathrm j(\theta_{i,t}-\theta_{j,t})},
$$

所以：

$$
Y_{ij}^*\tilde V_{i,t}\tilde V_{j,t}^*
=V_{i,t}V_{j,t}
(G_{ij}-\mathrm jB_{ij})
(\cos\delta_{ij,t}+\mathrm j\sin\delta_{ij,t}).
$$

继续展开实部和虚部：

$$
(G_{ij}-\mathrm jB_{ij})
(\cos\delta_{ij,t}+\mathrm j\sin\delta_{ij,t})
=
\left(G_{ij}\cos\delta_{ij,t}+B_{ij}\sin\delta_{ij,t}\right)
+\mathrm j\left(G_{ij}\sin\delta_{ij,t}-B_{ij}\cos\delta_{ij,t}\right).
$$

因此节点注入有功为复功率实部：

$$
P_{i,t}^{inj}
=
V_{i,t}\sum_{j\in\mathcal B}V_{j,t}
\left(G_{ij}\cos(\theta_{i,t}-\theta_{j,t})
+B_{ij}\sin(\theta_{i,t}-\theta_{j,t})\right).
$$

节点注入无功为复功率虚部：

$$
Q_{i,t}^{inj}
=
V_{i,t}\sum_{j\in\mathcal B}V_{j,t}
\left(G_{ij}\sin(\theta_{i,t}-\theta_{j,t})
-B_{ij}\cos(\theta_{i,t}-\theta_{j,t})\right).
$$

这两条方程就是 AC OPF 中最核心的有功、无功潮流方程。它们不是凭空给出的，而是由“线路阻抗 $\rightarrow$ 线路导纳 $\rightarrow$ 节点导纳矩阵 $\rightarrow$ KCL 电流方程 $\rightarrow$ 复功率定义”逐步得到的。

### 2.6 当前算例的节点功率注入

对当前 6 节点算例，节点注入由变电站、DG 和负荷组成。用 p.u. 写为：

$$
P_{i,t}^{inj}
=\frac{\mathbf 1_{\{i=1\}}p_t^{grid}
+\mathbf 1_{\{i=6\}}p_t^{DG}
-p_{i,t}^L}{S_{\text{base}}},
$$

$$
Q_{i,t}^{inj}
=\frac{\mathbf 1_{\{i=1\}}q_t^{grid}
-q_{i,t}^L}{S_{\text{base}}}.
$$

其中负荷为负注入，变电站购电和 DG 出力为正注入。当前模型没有设置 DG 无功出力，所以 $Q_{i,t}^{inj}$ 中只有变电站无功和负荷无功。

因此，AC 功率平衡就是要求每个节点的设备净注入等于由网络电压计算出来的 AC 注入：

$$
\frac{\mathbf 1_{\{i=1\}}p_t^{grid}
+\mathbf 1_{\{i=6\}}p_t^{DG}
-p_{i,t}^L}{S_{\text{base}}}
=
V_{i,t}\sum_{j\in\mathcal B}V_{j,t}
\left(G_{ij}\cos(\theta_{i,t}-\theta_{j,t})
+B_{ij}\sin(\theta_{i,t}-\theta_{j,t})\right),
$$

$$
\frac{\mathbf 1_{\{i=1\}}q_t^{grid}
-q_{i,t}^L}{S_{\text{base}}}
=
V_{i,t}\sum_{j\in\mathcal B}V_{j,t}
\left(G_{ij}\sin(\theta_{i,t}-\theta_{j,t})
-B_{ij}\cos(\theta_{i,t}-\theta_{j,t})\right).
$$

### 2.7 AC OPF 完整模型

AC 原始 OPF 的目标函数仍是运行成本最小：

$$
\min \sum_{t\in\mathcal T}
\left(c_t^{grid}p_t^{grid}+c^{DG}p_t^{DG}\right).
$$

主要约束包括 AC 有功/无功功率平衡、平衡节点参考、电压幅值边界、设备出力边界和线路容量约束：

$$
\theta_{1,t}=0,\qquad V_{1,t}=1.0.
$$

$$
V_{\min}\le V_{i,t}\le V_{\max}.
$$

$$
0\le p_t^{grid}\le 6.0,\qquad
0\le q_t^{grid}\le 1.5,\qquad
0\le p_t^{DG}\le 0.8.
$$

线路容量可以由线路两端复功率定义。对支路 $(i,j)$：

$$
\tilde I_{ij,t}=y_{ij}(\tilde V_{i,t}-\tilde V_{j,t}),\qquad
\tilde S_{ij,t}=\tilde V_{i,t}\tilde I_{ij,t}^*.
$$

$$
\tilde I_{ji,t}=y_{ij}(\tilde V_{j,t}-\tilde V_{i,t}),\qquad
\tilde S_{ji,t}=\tilde V_{j,t}\tilde I_{ji,t}^*.
$$

若 $\tilde S_{ij,t}$ 用 p.u. 表示，则容量约束为：

$$
|\tilde S_{ij,t}|\le \frac{\bar S_{ij}}{S_{\text{base}}},
\qquad
|\tilde S_{ji,t}|\le \frac{\bar S_{ij}}{S_{\text{base}}}.
$$

若用工程单位表示，则为：

$$
|\tilde S_{ij,t}^{MW/MVAr}|\le \bar S_{ij},
\qquad
|\tilde S_{ji,t}^{MW/MVAr}|\le \bar S_{ij}.
$$

这个模型才是电力系统意义上的“原始模型”。它的非凸性来自 $V_iV_j$ 的乘积、$\sin(\theta_i-\theta_j)$、$\cos(\theta_i-\theta_j)$，以及由复电压计算线路功率时产生的二次项。当前 `opf/opf_ac.py` 用矩形坐标 $e_i,f_i$ 避开三角函数，直接求解等价的非凸二次 AC OPF；`opf/opf_distflow.py` 和 `opf/opf_lindistflow.py` 则针对径向配电网使用 DistFlow 分支潮流表达。

## 3. DC 潮流模型：只保留有功-相角关系

DC 潮流不是直流电网模型，而是 AC 潮流在高压输电网常用的一种有功线性近似。它不是从节点功率平衡公式直接跳出来的，而是从 AC 支路有功潮流一步步删去次要物理量得到的。

### 3.1 从 AC 支路功率开始

对支路 $(i,j)$，AC 支路电流为：

$$
\tilde I_{ij}=y_{ij}(\tilde V_i-\tilde V_j),
\qquad
y_{ij}=g_{ij}+\mathrm jb_{ij}.
$$

支路首端复功率为：

$$
\tilde S_{ij}
=P_{ij}+\mathrm jQ_{ij}
=\tilde V_i\tilde I_{ij}^*.
$$

把 $\tilde V_i=V_ie^{\mathrm j\theta_i}$ 代入，可得到支路有功潮流：

$$
p_{ij}
=g_{ij}V_i^2
-V_iV_j\left(g_{ij}\cos(\theta_i-\theta_j)+b_{ij}\sin(\theta_i-\theta_j)\right).
$$

这还是完整 AC 支路有功公式，里面仍然有电压幅值、线路电导、电纳和三角函数。

### 3.2 忽略线路电阻

DC 潮流通常面向输电网，近似认为线路电阻远小于电抗：

$$
r_{ij}\ll x_{ij}.
$$

于是线路近似为纯电抗：

$$
z_{ij}\approx \mathrm jx_{ij},
\qquad
y_{ij}=\frac{1}{\mathrm jx_{ij}}=-\mathrm j\frac{1}{x_{ij}}.
$$

因此：

$$
g_{ij}\approx0,\qquad b_{ij}\approx-\frac{1}{x_{ij}}.
$$

把它代入 AC 支路有功公式：

$$
p_{ij}
\approx
-V_iV_j\left(-\frac{1}{x_{ij}}\sin(\theta_i-\theta_j)\right)
=
\frac{V_iV_j}{x_{ij}}\sin(\theta_i-\theta_j).
$$

这一步的物理含义是：忽略电阻后，线路不再产生有功损耗，线路有功主要由两端相角差驱动。

### 3.3 固定电压幅值并使用小角度近似

DC 潮流进一步假设电压幅值接近 1 p.u.：

$$
V_i\approx1,\qquad V_j\approx1.
$$

于是：

$$
p_{ij}
\approx
\frac{1}{x_{ij}}\sin(\theta_i-\theta_j).
$$

在正常运行中，相邻节点相角差通常较小，因此：

$$
\sin(\theta_i-\theta_j)\approx\theta_i-\theta_j.
$$

最终得到 DC 潮流核心方程：

$$
p_{ij}
=\frac{\theta_i-\theta_j}{x_{ij}}.
$$

代码中支路有功 $P_{ij}$ 仍用 MW，因此写成：

$$
P_{ij}
=S_{\text{base}}\frac{\theta_i-\theta_j}{x_{ij}}.
$$

### 3.4 节点有功平衡

DC 潮流不再计算无功平衡，也不再计算电压幅值。每个节点只保留有功注入平衡：

$$
\mathbf 1_{\{i=1\}}p_t^{grid}
+\mathbf 1_{\{i=6\}}p_t^{DG}
-p_{i,t}^L
=
\sum_{\ell\in\mathcal C(i)}P_{\ell,t}
-\sum_{\ell:\,t(\ell)=i}P_{\ell,t}.
$$

左边是节点 $i$ 的净有功注入；右边是从节点 $i$ 流出的有功减去流入节点 $i$ 的有功。因为 DC 潮流忽略线路损耗，所以全网购电量会等于总负荷减去 DG 出力。

平衡节点相角为：

$$
\theta_{1,t}=0.
$$

支路容量在 DC 模型里只能近似成有功限制，因为无功 $Q$ 已经不建模：

$$
-\bar S_\ell\le P_{\ell,t}\le \bar S_\ell.
$$

所以 `opf/opf_dc.py` 不计算无功、电压幅值、电流平方和线路损耗；它适合做“最快、最粗”的有功调度基线。对配电网而言，DC 潮流通常比 LinDistFlow 更粗，因为配电网 $r/x$ 不一定很小，电压幅值和无功也更重要。

## 4. SDP 松弛模型：把电压乘积提升成矩阵变量

SDP 松弛的出发点仍然是 AC OPF。它不先丢掉无功、电压或损耗，而是观察到 AC OPF 的非凸项主要来自电压乘积：

$$
\tilde V_i\tilde V_j^*.
$$

### 4.1 从复电压向量到矩阵变量

把所有节点电压写成向量：

$$
\tilde V_t=
\begin{bmatrix}
\tilde V_{1,t}\\
\tilde V_{2,t}\\
\vdots\\
\tilde V_{n,t}
\end{bmatrix}.
$$

定义提升矩阵：

$$
W_t=\tilde V_t\tilde V_t^H.
$$

其中 $H$ 表示共轭转置。矩阵元素为：

$$
(W_t)_{ij}=\tilde V_{i,t}\tilde V_{j,t}^*.
$$

因此，AC 潮流里所有电压乘积都可以被 $W_{ij}$ 替代。

### 4.2 原始 AC 约束如何写成 $W$

节点注入复功率原本为：

$$
\tilde S_{i,t}^{inj}
=\tilde V_{i,t}
\left(\sum_{j\in\mathcal B}Y_{ij}\tilde V_{j,t}\right)^*.
$$

展开后：

$$
\tilde S_{i,t}^{inj}
=
\sum_{j\in\mathcal B}Y_{ij}^*\tilde V_{i,t}\tilde V_{j,t}^*.
$$

代入 $W_{ij,t}=\tilde V_{i,t}\tilde V_{j,t}^*$：

$$
\tilde S_{i,t}^{inj}
=
\sum_{j\in\mathcal B}Y_{ij}^*W_{ij,t}.
$$

这样节点有功、无功平衡变成了 $W$ 的线性等式：

$$
P_{i,t}^{inj}
=
\operatorname{Re}\left(\sum_{j\in\mathcal B}Y_{ij}^*W_{ij,t}\right),
$$

$$
Q_{i,t}^{inj}
=
\operatorname{Im}\left(\sum_{j\in\mathcal B}Y_{ij}^*W_{ij,t}\right).
$$

电压幅值约束也变成对角元素约束：

$$
V_{\min}^2\le W_{ii,t}\le V_{\max}^2.
$$

支路 $(i,j)$ 的首端复功率为：

$$
\tilde S_{ij,t}
=\tilde V_{i,t}\left(y_{ij}(\tilde V_{i,t}-\tilde V_{j,t})\right)^*
=y_{ij}^*(W_{ii,t}-W_{ij,t}).
$$

所以线路容量可以写成：

$$
\left|
y_{ij}^*(W_{ii,t}-W_{ij,t})
\right|
\le
\frac{\bar S_{ij}}{S_{\text{base}}}.
$$

这是关于 $W$ 的二阶锥约束。

### 4.3 唯一被松弛的地方：秩约束

如果 $W_t$ 真的是由某个电压向量 $\tilde V_t$ 生成的，那么它必须满足：

$$
W_t=\tilde V_t\tilde V_t^H.
$$

这等价于两个条件：

$$
W_t\succeq0,
\qquad
\operatorname{rank}(W_t)=1.
$$

其中 $W_t\succeq0$ 表示半正定。原因是对任意向量 $a$：

$$
a^HW_ta
=a^H\tilde V_t\tilde V_t^Ha
=|\tilde V_t^Ha|^2
\ge0.
$$

真正困难的是：

$$
\operatorname{rank}(W_t)=1.
$$

这个秩约束是非凸的。SDP 松弛就是保留半正定约束，删除秩约束：

$$
W_t\succeq0,
\qquad
\text{drop }\operatorname{rank}(W_t)=1.
$$

因此，SDP 不是忽略物理损耗，也不是删除无功方程；它是在更高维空间里放宽“$W$ 必须来自一个电压向量”这件事。

### 4.4 SDP 解如何判断是否精确

如果求解后 $W_t$ 近似 rank-1，就可以恢复近似 AC 电压相量。代码中记录：

$$
\frac{\lambda_2(W_t)}{\lambda_1(W_t)}.
$$

若这个比值接近 0，说明 $W_t$ 几乎只有一个主特征值，SDP 松弛很紧；若这个比值明显偏大，则说明 SDP 解可能不对应某个真实 AC 电压相量。

`opf/opf_sdp.py` 使用 CVXPY 和 SCS 逐小时求解 SDP 松弛，并输出 `sdp_rank` sheet。当前算例中最大 $\lambda_2/\lambda_1$ 约为 $10^{-6}$，说明 SDP 解几乎是 rank-1，与 AC OPF 基本重合。

## 5. 非凸 DistFlow OPF

非凸 DistFlow OPF 不是凭空写出的另一套潮流方程，而是把第 2 节的 AC OPF 从“节点电压相量 + 节点导纳矩阵”的形式，改写成更适合径向配电网的“支路功率 + 电压平方 + 电流平方”形式。下面从 AC 支路关系一步一步推到 DistFlow。

### 5.1 从 AC 节点方程转到支路方程

AC OPF 的节点形式是：

$$
\tilde S_{i,t}^{inj}
=\tilde V_{i,t}
\left(\sum_{j\in\mathcal B}Y_{ij}\tilde V_{j,t}\right)^*.
$$

这条式子把所有相邻节点通过 $Y$ 矩阵混在一起。对于径向网，更自然的写法是沿着每条线路看电压、电流和功率。对支路 $\ell=(i,j)$，方向取为从上游节点 $i=f(\ell)$ 到下游节点 $j=t(\ell)$。AC 原始支路关系为：

$$
\tilde I_{\ell,t}
=y_\ell(\tilde V_{i,t}-\tilde V_{j,t}),
\qquad
\tilde V_{j,t}
=\tilde V_{i,t}-z_\ell\tilde I_{\ell,t}.
$$

支路首端送出的复功率为：

$$
\tilde S_{\ell,t}
=p_{\ell,t}+\mathrm jq_{\ell,t}
=\tilde V_{i,t}\tilde I_{\ell,t}^*.
$$

到这里仍然是 AC 模型，只是从节点导纳矩阵写法换成了支路电流写法。

### 5.2 引入 DistFlow 变量

DistFlow 的关键是把 AC 中的复电压和复电流，换成下面三个实数变量：

$$
v_{i,t}=|\tilde V_{i,t}|^2,
\qquad
\ell_{\ell,t}=|\tilde I_{\ell,t}|^2,
\qquad
\tilde S_{\ell,t}=p_{\ell,t}+\mathrm jq_{\ell,t}.
$$

也就是说：

- AC OPF 直接优化 $V_{i,t}$ 和 $\theta_{i,t}$。
- DistFlow 不显式写相角，而是使用 $v_{i,t}$、$\ell_{\ell,t}$、$p_{\ell,t}$、$q_{\ell,t}$。

这一步不是松弛，只是变量改写。非凸性还没有消失，只是会被集中到后面的电流-功率-电压等式里。

### 5.3 从 AC 功率守恒推出 DistFlow 功率平衡

先看一条支路 $\ell=(i,j)$。支路首端送出功率为：

$$
\tilde S_{\ell,t}=\tilde V_{i,t}\tilde I_{\ell,t}^*.
$$

支路末端收到的功率为：

$$
\tilde V_{j,t}\tilde I_{\ell,t}^*.
$$

两者的差就是线路损耗：

$$
\tilde S_{\ell,t}
-\tilde V_{j,t}\tilde I_{\ell,t}^*
=
(\tilde V_{i,t}-\tilde V_{j,t})\tilde I_{\ell,t}^*
=
z_\ell\tilde I_{\ell,t}\tilde I_{\ell,t}^*
=
z_\ell\ell_{\ell,t}.
$$

因此：

$$
\tilde V_{j,t}\tilde I_{\ell,t}^*
=\tilde S_{\ell,t}-z_\ell\ell_{\ell,t}.
$$

这句话的物理含义是：父支路首端送出的功率，扣掉线路损耗以后，才是到达下游节点 $j$ 的功率。

在节点 $j$，这部分到达功率要供应本节点净负荷，并继续送往所有子支路。为了先写出干净的 p.u. 推导，令节点 $j$ 的 p.u. 净负荷为：

$$
\tilde s_{j,t}^{pu}
=\frac{p_{j,t}^L-\mathbf 1_{\{j=6\}}p_t^{DG}}{S_{\text{base}}}
+\mathrm j\frac{q_{j,t}^L}{S_{\text{base}}}
=p_{j,t}^{d,pu}+\mathrm jq_{j,t}^{d,pu}.
$$

现在解释这条平衡式怎么来。设父支路 $\pi(j)$ 的电流方向是从父节点流入节点 $j$，子支路 $m\in\mathcal C(j)$ 的电流方向是从节点 $j$ 流向下游子节点。若把节点 $j$ 的本地净负荷看成一个等效电流 $\tilde I_{j,t}^{d}$，则节点 $j$ 处的 KCL 为：

$$
\tilde I_{\pi(j),t}
=\tilde I_{j,t}^{d}
+\sum_{m\in\mathcal C(j)}\tilde I_{m,t}.
$$

这句话只是说：从父支路流进节点 $j$ 的电流，要么被本节点负荷消耗，要么继续流向下游子支路。对 KCL 两边先取共轭，再同乘节点电压 $\tilde V_{j,t}$：

$$
\tilde V_{j,t}\tilde I_{\pi(j),t}^*
=\tilde V_{j,t}\left(\tilde I_{j,t}^{d}\right)^*
+\sum_{m\in\mathcal C(j)}\tilde V_{j,t}\tilde I_{m,t}^*.
$$

逐项看这个式子的物理意义：

- $\tilde V_{j,t}\tilde I_{\pi(j),t}^*$：父支路真正送到节点 $j$ 端口的复功率，也就是父支路末端接收功率。
- $\tilde V_{j,t}(\tilde I_{j,t}^{d})^*=\tilde s_{j,t}^{pu}$：节点 $j$ 本地净负荷吸收的复功率。
- $\tilde V_{j,t}\tilde I_{m,t}^*=\tilde S_{m,t}$：从节点 $j$ 送入子支路 $m$ 的复功率。

所以节点 $j$ 端口上的功率守恒先写成：

$$
\tilde V_{j,t}\tilde I_{\pi(j),t}^*
=
\tilde s_{j,t}^{pu}
+\sum_{m\in\mathcal C(j)}\tilde S_{m,t}.
$$

但 DistFlow 变量通常记录的是父支路首端送出功率 $\tilde S_{\pi(j),t}$，不是末端接收功率 $\tilde V_{j,t}\tilde I_{\pi(j),t}^*$。上一段已经推得：

$$
\tilde V_{j,t}\tilde I_{\pi(j),t}^*
=\tilde S_{\pi(j),t}-z_{\pi(j)}\ell_{\pi(j),t}.
$$

把它代入节点 $j$ 端口功率守恒，就得到 AC 支路功率守恒：

$$
\tilde S_{\pi(j),t}
-z_{\pi(j)}\ell_{\pi(j),t}
=
\tilde s_{j,t}^{pu}
+\sum_{m\in\mathcal C(j)}\tilde S_{m,t}.
$$

把损耗项移到右边，就得到 DistFlow 复功率平衡：

$$
\tilde S_{\pi(j),t}
=
\tilde s_{j,t}^{pu}
+\sum_{m\in\mathcal C(j)}\tilde S_{m,t}
+z_{\pi(j)}\ell_{\pi(j),t}.
$$

父支路首端送出的功率=节点 $j$ 本地净消耗功率+从节点 $j$ 继续送往所有下游子支路的功率+父支路 $\pi(j)$ 从上级节点传到节点 $j$ 这一段线路上的损耗

再把 $z=r+\mathrm jx$、$\tilde S=p+\mathrm jq$ 分开取实部和虚部，得到 p.u. 形式：

$$
p_{\pi(j),t}
=p_{j,t}^{d,pu}
+\sum_{m\in\mathcal C(j)}p_{m,t}
+r_{\pi(j)}\ell_{\pi(j),t},
$$

$$
q_{\pi(j),t}
=q_{j,t}^{d,pu}
+\sum_{m\in\mathcal C(j)}q_{m,t}
+x_{\pi(j)}\ell_{\pi(j),t}.
$$

这两条式子对应的 AC 来源是节点功率平衡和支路功率损耗关系。也就是说，AC OPF 中的节点注入方程没有被“删除”，而是被改写成了沿径向网络逐支路的功率守恒。

当前代码为了输出直观，把支路功率 $P,Q$ 保持为 MW/MVAr，而 $\ell$、$r$、$x$ 使用 p.u. 尺度。因此有功平衡写成：


$$
P_{\pi(j),t}
=p_{j,t}^L-\mathbf 1_{\{j=6\}}p_t^{DG}
+\sum_{m\in\mathcal C(j)}P_{m,t}
+S_{\text{base}}r_{\pi(j)}\ell_{\pi(j),t}.
$$

无功平衡写成：

$$
Q_{\pi(j),t}
=q_{j,t}^L
+\sum_{m\in\mathcal C(j)}Q_{m,t}
+S_{\text{base}}x_{\pi(j)}\ell_{\pi(j),t}.
$$

其中 $S_{\text{base}}r\ell$ 和 $S_{\text{base}}x\ell$ 分别是线路有功损耗和无功损耗，单位换回 MW/MVAr。

### 5.4 从 AC 电压相量方程推出 DistFlow 电压降

AC 支路电压关系为：

$$
\tilde V_{j,t}
=\tilde V_{i,t}-z_\ell\tilde I_{\ell,t}.
$$

DistFlow 不保留电压相角，而是对两边取模平方：

$$
v_{j,t}
=|\tilde V_{j,t}|^2
=|\tilde V_{i,t}-z_\ell\tilde I_{\ell,t}|^2.
$$

展开右边：

$$
|\tilde V_{i,t}-z_\ell\tilde I_{\ell,t}|^2
=|\tilde V_{i,t}|^2
-2\operatorname{Re}\left(z_\ell^*\tilde V_{i,t}\tilde I_{\ell,t}^*\right)
+|z_\ell|^2|\tilde I_{\ell,t}|^2.
$$

利用：

$$
\tilde V_{i,t}\tilde I_{\ell,t}^*
=\tilde S_{\ell,t}=p_{\ell,t}+\mathrm jq_{\ell,t},
\qquad
z_\ell^*=r_\ell-\mathrm jx_\ell,
$$

可以得到：

$$
\operatorname{Re}\left(z_\ell^*\tilde S_{\ell,t}\right)
=r_\ell p_{\ell,t}+x_\ell q_{\ell,t}.
$$

所以 AC 电压相量方程变成 DistFlow 电压平方方程：

$$
v_{j,t}
=v_{i,t}
-2\left(r_\ell p_{\ell,t}+x_\ell q_{\ell,t}\right)
+(r_\ell^2+x_\ell^2)\ell_{\ell,t}.
$$

这一步的变化很明确：AC OPF 中原本的复数电压关系 $\tilde V_j=\tilde V_i-zI$，被改写为只含电压平方 $v$、支路功率 $p,q$ 和电流平方 $\ell$ 的实数方程。

### 5.5 从 AC 复功率定义推出非凸等式

AC 支路复功率定义为：

$$
\tilde S_{\ell,t}
=\tilde V_{i,t}\tilde I_{\ell,t}^*.
$$

对两边取模平方：

$$
|\tilde S_{\ell,t}|^2
=|\tilde V_{i,t}|^2|\tilde I_{\ell,t}|^2.
$$

代入 DistFlow 变量定义：

$$
p_{\ell,t}^2+q_{\ell,t}^2
=v_{i,t}\ell_{\ell,t},
\qquad i=f(\ell).
$$

这就是非凸 DistFlow OPF 中最关键的一条约束。它来自 AC 的复功率定义 $\tilde S=\tilde V\tilde I^*$，不是额外假设。非凸性从 AC OPF 里的三角函数和电压乘积，转移到了这个双线性等式 $v\ell=p^2+q^2$ 上。

如果按代码中的工程单位写，因为：

$$
p_{\ell,t}=\frac{P_{\ell,t}}{S_{\text{base}}},
\qquad
q_{\ell,t}=\frac{Q_{\ell,t}}{S_{\text{base}}},
$$

所以：

$$
P_{\ell,t}^2+Q_{\ell,t}^2
=S_{\text{base}}^2v_{f(\ell),t}\ell_{\ell,t}.
$$

### 5.6 变电站、电压边界和容量约束

平衡节点电压固定为：

$$
v_{1,t}=1.0,\qquad \forall t\in\mathcal T.
$$

变电站注入由首条支路 L12 定义：

$$
p_t^{grid}=P_{\mathrm{L12},t},\qquad
q_t^{grid}=Q_{\mathrm{L12},t}.
$$

电压和设备边界为：

$$
V_{\min}^2\le v_{i,t}\le V_{\max}^2,\qquad
\ell_{\ell,t}\ge 0.
$$

$$
0\le p_t^{grid}\le 6.0,\qquad
0\le q_t^{grid}\le 1.5,\qquad
0\le p_t^{DG}\le 0.8.
$$

支路容量约束仍然来自 AC 的视在功率限制：

$$
|\tilde S_{\ell,t}|\le \frac{\bar S_\ell}{S_{\text{base}}}.
$$

写成 $p,q$ 就是：

$$
p_{\ell,t}^2+q_{\ell,t}^2
\le \left(\frac{\bar S_\ell}{S_{\text{base}}}\right)^2.
$$

代码中使用等价的工程单位形式：

$$
P_{\ell,t}^2+Q_{\ell,t}^2\le \bar S_\ell^2.
$$

### 5.7 从 AC OPF 到非凸 DistFlow OPF 的对应关系

把上面的推导压缩成一张对应表：

| AC OPF 中的式子 | DistFlow 中的式子 | 变化 |
| --- | --- | --- |
| $\tilde I_{ij}=y_{ij}(\tilde V_i-\tilde V_j)$ | $\tilde V_j=\tilde V_i-z_{ij}\tilde I_{ij}$ | 由导纳形式改成支路压降形式 |
| $\tilde S_{ij}=\tilde V_i\tilde I_{ij}^*$ | $p_{ij}^2+q_{ij}^2=v_i\ell_{ij}$ | 对复功率定义取模平方 |
| 节点功率平衡 $\tilde S_i^{inj}=\tilde V_i(\sum_jY_{ij}\tilde V_j)^*$ | $\tilde S_{\pi(i)}=\tilde s_i^{pu}+\sum_{\ell\in\mathcal C(i)}\tilde S_\ell+z_{\pi(i)}\ell_{\pi(i)}$ | 在径向树上改写成父支路供电等于本节点净负荷、子支路功率和线路损耗 |
| 复电压关系 $\tilde V_j=\tilde V_i-z_{ij}\tilde I_{ij}$ | $v_j=v_i-2(rp+xq)+(r^2+x^2)\ell$ | 对电压相量方程取模平方 |
| 线路容量 $|\tilde S_{ij}|\le \bar S/S_{\text{base}}$ | $p_{ij}^2+q_{ij}^2\le(\bar S/S_{\text{base}})^2$ | 改写成支路功率平方约束 |

因此，非凸 DistFlow OPF 可以概括为：它把 AC OPF 从节点相量模型改写为径向支路模型；在径向、忽略线路并联电纳且相角可恢复时，这是 AC 支路潮流的等价改写，不是近似；功率平衡和电压降变成线性或仿射形式；非凸性集中在 $p^2+q^2=v\ell$ 这一条电流-功率-电压等式中。当前 `opf/opf_distflow.py` 并没有直接求解这个非凸等式模型，而是在下一节把这条等式松弛成二阶锥不等式。

## 6. DistFlow SOCP 模型：在哪个位置进行松弛

`opf/opf_distflow.py` 求解的是上面非凸 DistFlow OPF 的 SOCP 松弛。它没有改变目标函数，也没有改变功率平衡、电压降、支路容量和变量边界；优化处理只发生在下面这条 DistFlow 电流-功率-电压等式上。

松弛前：

$$
p_{\ell,t}^2+q_{\ell,t}^2
=v_{f(\ell),t}\ell_{\ell,t}.
$$

松弛后：

$$
p_{\ell,t}^2+q_{\ell,t}^2
\le v_{f(\ell),t}\ell_{\ell,t}.
$$

也就是说，SOCP 把“必须严格等于”改成“允许右边更大一些”。这样会扩大可行域：

$$
\mathcal F_{\text{DistFlow}}\subseteq \mathcal F_{\text{SOCP}}.
$$

在代码中，因为 $P,Q$ 保留 MW/MVAr 单位，松弛前后的工程单位形式分别是：

$$
P_{\ell,t}^2+Q_{\ell,t}^2
=S_{\text{base}}^2v_{f(\ell),t}\ell_{\ell,t}
\quad\Longrightarrow\quad
P_{\ell,t}^2+Q_{\ell,t}^2
\le S_{\text{base}}^2v_{f(\ell),t}\ell_{\ell,t}.
$$

对应代码就是：

```python
m.addQConstr(P[br, h] * P[br, h] + Q[br, h] * Q[br, h] <= S_base**2 * v[f, h] * ell[br, h], name=f"current_soc[{br},{h}]")
```

从二阶锥角度看，因为 $v_{f(\ell),t}\ge V_{\min}^2>0$ 且 $\ell_{\ell,t}\ge 0$，约束

$$
p_{\ell,t}^2+q_{\ell,t}^2\le v_{f(\ell),t}\ell_{\ell,t}
$$

是一个旋转二阶锥，可以写成：

$$
\left\|
\begin{bmatrix}
2p_{\ell,t}\\
2q_{\ell,t}\\
v_{f(\ell),t}-\ell_{\ell,t}
\end{bmatrix}
\right\|_2
\le
v_{f(\ell),t}+\ell_{\ell,t}.
$$

所以 Gurobi 可以把这个连续凸 QCP/SOCP 用 barrier 内点法等连续优化算法求解。因为当前没有整数变量，不会进入 MIP 的分支定界流程。

求解结果中 `dist_branch_flow` sheet 记录了松弛间隙：

$$
\text{soc\_gap}
=v_{f(\ell),t}\ell_{\ell,t}
-p_{\ell,t}^2
-q_{\ell,t}^2.
$$

如果 `soc_gap` 接近 0，说明 SOCP 松弛在数值上几乎回到了非凸 DistFlow 等式；如果明显大于 0，说明松弛给出了一个比非凸 DistFlow 更宽的解空间。

当前结果中最大 `soc_gap` 约为 $6\times 10^{-6}$，说明这个算例下松弛非常紧。

## 7. LinDistFlow 模型：进一步线性化近似

`opf/opf_lindistflow.py` 不是对非凸等式做锥松弛，而是在 DistFlow 物理方程上进一步忽略小量。它删除 $\ell_{\ell,t}$ 变量，同时忽略线路损耗和电压方程中的电流平方项。

有功平衡从非凸 DistFlow：

$$
P_{\pi(i),t}
=p_{i,t}^L-\mathbf 1_{\{i=6\}}p_t^{DG}
+\sum_{\ell\in\mathcal C(i)}P_{\ell,t}
+S_{\text{base}}r_{\pi(i)}\ell_{\pi(i),t}
$$

变成 LinDistFlow：

$$
P_{\pi(i),t}
=p_{i,t}^L-\mathbf 1_{\{i=6\}}p_t^{DG}
+\sum_{\ell\in\mathcal C(i)}P_{\ell,t}.
$$

无功平衡从非凸 DistFlow：

$$
Q_{\pi(i),t}
=q_{i,t}^L
+\sum_{\ell\in\mathcal C(i)}Q_{\ell,t}
+S_{\text{base}}x_{\pi(i)}\ell_{\pi(i),t}
$$

变成 LinDistFlow：

$$
Q_{\pi(i),t}
=q_{i,t}^L
+\sum_{\ell\in\mathcal C(i)}Q_{\ell,t}.
$$

电压方程从非凸 DistFlow：

$$
v_{j,t}
=v_{i,t}
-2\left(r_\ell p_{\ell,t}+x_\ell q_{\ell,t}\right)
+(r_\ell^2+x_\ell^2)\ell_{\ell,t}
$$

变成 LinDistFlow：

$$
v_{j,t}
=v_{i,t}
-2\left(r_\ell p_{\ell,t}+x_\ell q_{\ell,t}\right).
$$

同时，LinDistFlow 不再使用 DistFlow 电流关系：

$$
p_{\ell,t}^2+q_{\ell,t}^2=v_{f(\ell),t}\ell_{\ell,t}.
$$

因为 $\ell_{\ell,t}$ 已经被删除，这条约束在 LinDistFlow 中不存在。

不过当前代码仍保留支路容量约束：

$$
P_{\ell,t}^2+Q_{\ell,t}^2\le \bar S_\ell^2.
$$

因此当前 LinDistFlow 代码严格说是“线性潮流方程 + 支路容量二阶锥约束”的连续凸模型。若把支路容量约束也改成线性近似或删掉，它才会变成纯 LP；但当前实现仍是连续 SOCP/凸 QCP。

六种形式的关系可以这样看：

| 项目 | AC 原始 OPF | DC 潮流 | SDP 松弛 | 非凸 DistFlow OPF | DistFlow SOCP | LinDistFlow |
| --- | --- | --- | --- | --- | --- | --- |
| 基本变量 | 复电压幅值和相角 | 节点相角 $\theta$、支路有功 $P$ | 电压乘积矩阵 $W$ | 支路 $P,Q$、电压平方 $v$、电流平方 $\ell$ | 同非凸 DistFlow | 支路 $P,Q$、电压平方 $v$ |
| 网络方程 | 节点导纳矩阵 AC 潮流 | $P_{ij}=S_{\text{base}}(\theta_i-\theta_j)/x_{ij}$ | $S_i=\sum_jY_{ij}^*W_{ij}$ | 径向 branch-flow 潮流 | 同非凸 DistFlow | 线性化 branch-flow 潮流 |
| 线路有功损耗 | 由 AC 潮流自然包含 | 忽略 | 保留 | 保留 $S_{\text{base}}r\ell$ | 保留 $S_{\text{base}}r\ell$ | 忽略 |
| 线路无功损耗 | 由 AC 潮流自然包含 | 不建模 | 保留 | 保留 $S_{\text{base}}x\ell$ | 保留 $S_{\text{base}}x\ell$ | 忽略 |
| 电压方程 | 复电压非线性关系 | 固定 $V\approx1$，不建模电压约束 | $V_i^2=W_{ii}$ | 保留 $(r^2+x^2)\ell$ | 保留 $(r^2+x^2)\ell$ | 忽略 $(r^2+x^2)\ell$ |
| 电流关系 | 由 $\tilde I=Y\tilde V$ 给出 | 不建模 | 由 $W$ 计算支路功率 | $p^2+q^2=v\ell$ | $p^2+q^2\le v\ell$ | 删除 |
| 主要近似或松弛 | 无近似，原始 AC 非凸 | 忽略无功、损耗、电压幅值，使用小角度近似 | 删除 $\operatorname{rank}(W)=1$ | 支路变量重写，仍非凸 | 把等式松弛为不等式 | 忽略损耗和电流平方项 |
| 模型性质 | 非凸 NLP/AC OPF | LP | SDP/SOCP 凸松弛 | 非凸 | 凸 SOCP/凸 QCP | 连续凸 SOCP/凸 QCP |
| 当前代码 | `opf/opf_ac.py` | `opf/opf_dc.py` | `opf/opf_sdp.py` | 未直接求解 | `opf/opf_distflow.py` | `opf/opf_lindistflow.py` |

直观上，AC 原始 OPF 是物理上最直接的节点电压相量模型；DC 潮流进一步只保留有功和相角，速度最快，但对配电网物理最粗；SDP 松弛保留 AC 的功率平衡和损耗物理，但放宽了 $W$ 的 rank-1 要求；非凸 DistFlow OPF 是径向网络上的支路潮流重写；DistFlow SOCP 主要是在“电流-功率-电压非凸等式”上做松弛，尽量保留损耗和电压物理；LinDistFlow 把损耗和电流相关项直接省略。

## 8. 当前脚本输出和结果读法

运行顺序：

```powershell
python main.py
```

`main.py` 会先检查当前解释器是否来自 `methods` conda 环境；如果不是，会自动用下面的方式重启：

```powershell
conda run -n methods python main.py
```

因此项目默认运行环境是 `methods`。如果需要重新创建环境，可使用仓库中的 `environment.yml`：

```powershell
conda env create -f environment.yml
```

`main.py` 会依次运行：

```text
network/case6.py -> opf/opf_ac.py -> opf/opf_dc.py -> opf/opf_sdp.py -> opf/opf_distflow.py -> opf/opf_lindistflow.py -> opf/opf_report.py
```

表格结果统一写入：

```text
results/opf/comparison.xlsx
```

主要 sheet：

| Sheet | 内容 |
| --- | --- |
| `bus` | 节点数据 |
| `branch` | 支路参数 |
| `load_base` | 负荷基值 |
| `load_timeseries` | 逐小时节点负荷 |
| `total_load` | 逐小时总负荷 |
| `ac_dispatch` | AC OPF 每小时购电、DG、无功和最低/最高电压 |
| `ac_branch_flow` | AC OPF 支路两端潮流、损耗和负载率 |
| `ac_voltage` | AC OPF 节点电压幅值 |
| `ac_angle_deg` | AC OPF 节点电压相角，单位 degree |
| `dc_dispatch` | DC 潮流每小时购电、DG、有功-only 调度结果 |
| `dc_angle_deg` | DC 潮流节点相角，单位 degree |
| `dc_branch_flow` | DC 潮流支路有功潮流和近似负载率 |
| `sdp_dispatch` | SDP 松弛每小时购电、DG、无功和最低/最高电压 |
| `sdp_voltage` | SDP 松弛节点电压幅值 |
| `sdp_branch_flow` | SDP 松弛支路两端潮流、损耗和负载率 |
| `sdp_rank` | SDP 松弛矩阵 $W$ 的 rank-1 紧性诊断 |
| `dist_dispatch` | DistFlow 每小时购电、DG、无功和最低电压 |
| `dist_branch_flow` | DistFlow 支路潮流、损耗、电流平方和 SOCP gap |
| `lin_dispatch` | LinDistFlow 每小时购电、DG、无功和最低电压 |
| `lin_branch_flow` | LinDistFlow 支路潮流和负载率 |
| `summary` | 五种已求解模型的总体指标对比 |
| `hourly_comparison` | 五种已求解模型的逐小时对比 |

当前数据的一次求解结果为：

| 指标 | AC OPF | DC 潮流 | SDP 松弛 | DistFlow SOCP | LinDistFlow | DC - AC | SDP - AC | Dist - AC | Lin - AC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 目标函数 | 4847.116133 | 4823.600000 | 4847.117373 | 4847.116928 | 4823.600000 | -23.516133 | 0.001240 | 0.000795 | -23.516133 |
| 总购电量 MWh | 55.003824 | 54.696000 | 55.003852 | 55.003842 | 54.696000 | -0.307824 | 0.000028 | 0.000018 | -0.307824 |
| DG 总出力 MWh | 7.200001 | 7.200000 | 7.200000 | 7.200000 | 7.200000 | -0.000001 | -0.000001 | -0.000001 | -0.000001 |
| 变电站总无功 MVArh | 21.122169 | 不建模 | 21.119171 | 21.122185 | 20.344231 | 不适用 | -0.002999 | 0.000015 | -0.777938 |
| 最低电压 pu | 0.982522 | 1.000000 | 0.982521 | 0.982522 | 0.982768 | 0.017478 | -0.000001 | 0.000000 | 0.000246 |
| 最大支路负载率 % | 64.042665 | 60.355556 | 64.043541 | 64.042667 | 63.532164 | -3.687109 | 0.000876 | 0.000003 | -0.510501 |
| 总有功损耗 MWh | 0.307835 | 0.000000 | 0.307850 | 0.307842 | 0.000000 | -0.307835 | 0.000015 | 0.000007 | -0.307835 |
| 总无功损耗 MVArh | 0.777938 | 不建模 | 0.774941 | 0.777953 | 0.000000 | 不适用 | -0.002997 | 0.000015 | -0.777938 |
| SDP 最大 $\lambda_2/\lambda_1$ | 0.000000 | 不适用 | 0.000001 | 不适用 | 不适用 | 不适用 | 0.000001 | 不适用 | 不适用 |
| DistFlow 最大 SOCP gap | 0.000000 | 不适用 | 不适用 | 0.000006 | 不适用 | 不适用 | 不适用 | 0.000006 | 不适用 |

这组结果说明：DC 潮流和 LinDistFlow 在当前算例的有功调度上相同，因为二者都忽略有功损耗；但 DC 潮流不建模无功和电压，只能作为有功调度的粗基线。SDP 松弛与 AC OPF 几乎重合，最大 $\lambda_2/\lambda_1$ 约为 $10^{-6}$，说明 $W$ 基本是 rank-1。LinDistFlow 因为忽略线路损耗，低估了约 0.307824 MWh 的变电站购电量和约 0.777938 MVArh 的变电站无功需求；DistFlow SOCP 与 AC OPF 也几乎重合，最大 SOCP gap 接近 0，说明当前算例下锥松弛很紧。
