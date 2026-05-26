# IEEE 33 储能 dual CCG 计划

本文档用于审阅新脚本的建模路线。目标脚本为：

```text
planning/ccg_dual_storage_ieee33.py
```

该脚本不替换已有的 `planning/ccg_storage_ieee33.py`。已有脚本展示的是有限场景 CCG：固定当前储能规划后，逐个枚举候选场景并求运行原问题。新脚本要展示的是 dual CCG oracle：把下层运行 LP 对偶化，把最坏场景搜索从

$$
\max_d \min_z
$$

改写为

$$
\max_{d,\pi}
$$

从而直观看到“对偶变量如何把下层运行问题翻到上层”。

## 0. 审阅结论和本次修正

本文档的主线可执行：第一版应保留 IEEE 33 的 24 小时负荷、DG、储能投资变量和 CCG 主问题结构，但把二阶段运行问题明确收缩为聚合有功调度 LP，从而避免 conic dual。

本次审阅后需要补强四点：

1. 本脚本中的二阶段 LP 是教学版聚合有功模型，不包含节点电压、支路潮流、无功和网损，因此输出不能与 `ccg_storage_ieee33.py` 的 DistFlow-SOCP 鲁棒规划结果直接比较优劣。
2. 对偶 oracle 中 $\mu_{gh}$ 的 big-M 上界不是原始对偶可行域的天然上界，而是在 $\rho_G<1$ 时，由“最优对偶会取满足约束的最小 $\mu_{gh}$”得到的有效上界。脚本需要把这个假设写在常数附近。
3. 每轮 oracle 求得最坏扰动后，需要再用二阶段 primal LP 固定该扰动求一次 $Q(x^k,d^{k+1})$，校验 primal 和 dual 目标一致，再用该值更新违反量和 UB。
4. 如果 oracle 返回的扰动已经在主问题场景集中，但违反量仍大于容差，应直接报错，因为这说明对偶模型、primal 校验或场景转换存在不一致。

## 1. 为什么不直接对偶化当前 SOCP 版本

`planning/ccg_storage_ieee33.py` 的二阶段运行模型包含 DistFlow SOCP 约束，例如电流锥、支路视在容量锥：

$$
P_{\ell h}^2+Q_{\ell h}^2\le \overline S_\ell^2
$$

以及

$$
P_{\ell h}^2+Q_{\ell h}^2\le v_{fh}\ell_{\ell h}
$$

如果直接对这个二阶段问题做对偶，得到的是 conic dual，而不是前面讨论的简单 LP 对偶：

$$
W^\top\pi\le q
$$

这会让第一版脚本的重点从 CCG dual oracle 转移到锥对偶细节，不适合教学。

因此第一版 `ccg_dual_storage_ieee33.py` 保留 IEEE 33 节点的负荷、DG、24 小时、储能候选节点和投资变量，但把二阶段运行模型简化为线性有功调度 LP。这样可以清楚展示：

$$
Q(x,d)=\min_z\{q^\top z\mid Wz\ge h(d)-Tx,\ z\ge0\}
$$

以及：

$$
Q(x,d)=\max_\pi\{\pi^\top(h(d)-Tx)\mid W^\top\pi\le q,\ \pi\ge0\}
$$

## 2. 总体鲁棒规划问题

第一阶段决定储能规划：

$$
x=(y,\overline P,\overline E)
$$

其中：

| 符号 | 代码变量 | 含义 |
|---|---|---|
| $y_b$ | `y[b]` | 是否在节点 $b$ 建储能 |
| $\overline P_b$ | `p_cap[b]` | 储能功率容量，MW |
| $\overline E_b$ | `e_cap[b]` | 储能能量容量，MWh |
| $\eta$ | `eta` | 主问题中已加入场景的最坏运行成本 |

鲁棒目标为：

$$
\min_x
\quad
C^{\text{inv}}(x)+\max_{d\in\Xi}Q(x,d)
$$

其中 $d$ 是负荷和 DG 可用容量的不确定扰动，$Q(x,d)$ 是固定储能规划和扰动后的最小运行成本。

## 3. 第一阶段投资模型

沿用当前 CCG 脚本的储能投资成本：

$$
C^{\text{inv}}(y,\overline P,\overline E)
=
\sum_{b\in\mathcal C}
\left[
(C^{\text{fix}}+C^{\text{depth}}d_b)y_b
+C^P\overline P_b
+C^E\overline E_b
\right]
$$

约束为：

$$
\sum_{b\in\mathcal C}y_b\le N_{\max}
$$

$$
0\le\overline P_b\le M^P y_b
$$

$$
0\le\overline E_b\le M^E y_b
$$

$$
D_{\min}\overline P_b\le\overline E_b\le D_{\max}\overline P_b
$$

这些约束与当前 `ccg_storage_ieee33.py` 保持一致。

## 4. 不确定集合

第一版只让负荷和 DG 可用容量不确定，电价保持基准值。原因是电价进入二阶段目标系数，如果同时把目标系数也设为不确定，dual oracle 里会出现更多双线性项，不利于第一版看清主线。

脚本第一版固定使用：

| 参数 | 代码变量 | 含义 |
|---|---|---|
| $\rho_L$ | `rho_load` | 负荷上浮比例 |
| $\rho_G$ | `rho_dg` | DG 可用容量下调比例，要求 $0<\rho_G<1$ |
| $\Gamma_L$ | `gamma_load` | 最多选几个高负荷小时 |
| $\Gamma_G$ | `gamma_dg` | 最多选几个低 DG 小时 |

负荷上浮扰动：

$$
\alpha_h^{L}=1+\rho_L u_h
$$

DG 下调扰动：

$$
\alpha_h^{G}=1-\rho_G v_h
$$

其中：

$$
u_h\in\{0,1\},\quad v_h\in\{0,1\}
$$

预算约束为：

$$
\sum_{h\in\mathcal H}u_h\le\Gamma_L
$$

$$
\sum_{h\in\mathcal H}v_h\le\Gamma_G
$$

场景数据为：

$$
P^L_h(d)=
\sum_{b\in\mathcal C}\hat p^L_{bh}(1+\rho_Lu_h)
$$

$$
\overline P^G_{gh}(d)=
\hat P^G_g(1-\rho_Gv_h)
$$

这里 $u_h=1$ 表示小时 $h$ 负荷取高值，$v_h=1$ 表示小时 $h$ DG 可用容量取低值。

## 5. 二阶段线性运行原问题

固定第一阶段规划 $x^k=(\overline P^k,\overline E^k)$ 和不确定扰动 $d=(u,v)$ 后，运行变量为：

| 符号 | 代码变量 | 含义 |
|---|---|---|
| $p^{grid}_h$ | `p_grid[h]` | 从上级电网购电 |
| $p^{DG}_{gh}$ | `p_dg[g,h]` | DG 有功出力 |
| $p^{ch}_{bh}$ | `p_ch[b,h]` | 储能充电功率 |
| $p^{dis}_{bh}$ | `p_dis[b,h]` | 储能放电功率 |
| $e_{bh}$ | `e_sto[b,h]` | 储能电量 |

所有运行变量都非负。二阶段 LP 采用只含线性约束的有功调度模型：

$$
Q(x^k,d)
=
\min_z
\sum_{h\in\mathcal H}c^{grid}_h p^{grid}_h
+
\sum_{g,h}c^{DG}p^{DG}_{gh}
+
\sum_{b,h}c^{cyc}(p^{ch}_{bh}+p^{dis}_{bh})
$$

令：

$$
\widehat L_h=\sum_{b\in\mathcal C}\hat p^L_{bh}
$$

$$
\Delta L_h=\rho_L\widehat L_h
$$

则场景负荷为：

$$
L_h(u)=\widehat L_h+\Delta L_hu_h
$$

令：

$$
\widehat G_g=\overline P^G_g
$$

$$
\Delta G_g=\rho_G\widehat G_g
$$

则场景 DG 可用容量为：

$$
G_{gh}(v)=\widehat G_g-\Delta G_gv_h
$$

为了直接写出对偶，所有不等式统一写成 $\ge$ 形式，等式保持等式。

系统总有功平衡：

$$
p^{grid}_h+\sum_g p^{DG}_{gh}+\sum_b p^{dis}_{bh}-\sum_b p^{ch}_{bh}
\ge
L_h(u)
$$

DG 可用容量上界写成 $\ge$ 形式：

$$
-p^{DG}_{gh}\ge -G_{gh}(v)
$$

储能功率容量上界写成 $\ge$ 形式：

$$
-p^{ch}_{bh}\ge -\overline P^k_b
$$

$$
-p^{dis}_{bh}\ge -\overline P^k_b
$$

$$
-p^{ch}_{bh}-p^{dis}_{bh}\ge -\overline P^k_b
$$

储能电量容量：

$$
e_{bh}\ge SOC_{\min}\overline E^k_b
$$

$$
-e_{bh}\ge -\overline E^k_b
$$

SOC 递推：

$$
e_{b,h^+}-e_{bh}-\eta^{ch}p^{ch}_{bh}
+
\frac{p^{dis}_{bh}}{\eta^{dis}}
=0
$$

其中 $h^+=(h+1)\bmod 24$。

初始 SOC：

$$
e_{b0}=SOC_0\overline E^k_b
$$

这个模型刻意不加入电压、支路潮流、无功和 SOCP 约束。它不是替代当前 IEEE33 CCG，而是用于展示 dual oracle 的最小线性版本。

## 6. 二阶段 LP 的完整对偶化

上一节的原问题是一个最小化 LP：

$$
\min_z q^\top z
$$

$$
\text{s.t.}
\quad
A_{\ge}z\ge r(d,x^k)
$$

$$
A_{=}z=r^{=}(x^k)
$$

$$
z\ge0
$$

因此它的对偶是：

$$
\max_{\pi,\sigma}
\quad
r(d,x^k)^\top\pi+r^{=}(x^k)^\top\sigma
$$

$$
\text{s.t.}
\quad
A_{\ge}^\top\pi+A_{=}^\top\sigma\le q
$$

$$
\pi\ge0,\quad \sigma\text{ free}
$$

这里 $\pi$ 对应 $\ge$ 约束，非负；$\sigma$ 对应等式约束，自由。

### 6.1 对偶变量

给每类二阶段约束配对偶变量：

| 原约束 | 对偶变量 | 符号限制 | 含义 |
|---|---|---|---|
| 系统有功平衡 | $\lambda_h$ | $\lambda_h\ge0$ | 小时 $h$ 多 1 MW 负荷的边际运行成本 |
| DG 可用容量 | $\mu_{gh}$ | $\mu_{gh}\ge0$ | 节点 $g$、小时 $h$ 多 1 MW DG 可用容量的价值 |
| 充电功率上界 | $\alpha_{bh}$ | $\alpha_{bh}\ge0$ | 充电功率容量影子价格 |
| 放电功率上界 | $\beta_{bh}$ | $\beta_{bh}\ge0$ | 放电功率容量影子价格 |
| 变流器合计功率上界 | $\gamma_{bh}$ | $\gamma_{bh}\ge0$ | 充放电共用功率容量影子价格 |
| SOC 下界 | $\delta_{bh}$ | $\delta_{bh}\ge0$ | 最小 SOC 要求的影子价格 |
| SOC 上界 | $\zeta_{bh}$ | $\zeta_{bh}\ge0$ | 储能能量容量上界影子价格 |
| 初始 SOC 等式 | $\kappa_b$ | free | 初始电量绑定的边际价值 |
| SOC 递推等式 | $\tau_{bh}$ | free | 储能跨时段能量转移价值 |

### 6.2 对偶目标

固定 $x^k$ 和扰动 $d=(u,v)$ 时，对偶目标为：

$$
\begin{aligned}
Q(x^k,d)=
\max\quad
&
\sum_h \lambda_h L_h(u)
-
\sum_{g,h}\mu_{gh}G_{gh}(v)
-
\sum_{b,h}(\alpha_{bh}+\beta_{bh}+\gamma_{bh})\overline P^k_b\\
&
+
\sum_{b,h}(SOC_{\min}\delta_{bh}-\zeta_{bh})\overline E^k_b
+
\sum_b SOC_0\kappa_b\overline E^k_b
\end{aligned}
$$

其中 SOC 递推等式右端为 0，所以 $\tau_{bh}$ 不直接出现在目标里。

把不确定项展开：

$$
\sum_h \lambda_h L_h(u)
=
\sum_h \lambda_h\widehat L_h
+
\sum_h \Delta L_h\lambda_h u_h
$$

$$
-
\sum_{g,h}\mu_{gh}G_{gh}(v)
=
-
\sum_{g,h}\mu_{gh}\widehat G_g
+
\sum_{g,h}\Delta G_g\mu_{gh}v_h
$$

因此 dual oracle 的双线性只来自：

$$
\lambda_hu_h
$$

和：

$$
\mu_{gh}v_h
$$

### 6.3 对偶约束

每个原变量对应一条对偶约束。

对 $p^{grid}_h$：

$$
\lambda_h\le c^{grid}_h
$$

对 $p^{DG}_{gh}$：

$$
\lambda_h-\mu_{gh}\le c^{DG}
$$

对 $p^{ch}_{bh}$：

$$
-\lambda_h-\alpha_{bh}-\gamma_{bh}-\eta^{ch}\tau_{bh}
\le c^{cyc}
$$

对 $p^{dis}_{bh}$：

$$
\lambda_h-\beta_{bh}-\gamma_{bh}
+
\frac{\tau_{bh}}{\eta^{dis}}
\le c^{cyc}
$$

对 $e_{bh}$：

$$
\delta_{bh}-\zeta_{bh}
+
\mathbf 1_{\{h=0\}}\kappa_b
+
\tau_{b,h^-}
-
\tau_{bh}
\le0
$$

其中 $h^-=(h-1)\bmod 24$。

对偶变量符号约束为：

$$
\lambda,\mu,\alpha,\beta,\gamma,\delta,\zeta\ge0
$$

$$
\kappa,\tau\text{ free}
$$

这些式子就是新脚本里 `solve_dual_oracle` 要写出来的核心数学模型。

只要二阶段 LP 可行且有有限最优值，强对偶保证：

$$
\min_z\{q^\top z\mid z\text{ 满足二阶段原问题}\}
=
\max_{\lambda,\mu,\alpha,\beta,\gamma,\delta,\zeta,\kappa,\tau}
\{\text{二阶段对偶目标}\}
$$

因此在 oracle 中替换下层 $\min_z$ 是精确等价，不是近似。

## 7. CCG 主问题

第 $k$ 轮主问题只包含已经发现的扰动场景集合：

$$
\mathcal S_k=\{d^1,\dots,d^k\}
$$

主问题为：

$$
\min_{x,\eta,z^s}
\quad
C^{\text{inv}}(x)+\eta
$$

$$
\text{s.t.}
\quad
x\text{ 满足第一阶段投资约束}
$$

$$
\eta\ge q^\top z^s,\quad s\in\mathcal S_k
$$

$$
z^s\text{ 满足场景 }d^s\text{ 下的二阶段运行约束},\quad s\in\mathcal S_k
$$

这仍然是 CCG 的 column-and-constraint 结构：每加入一个新场景，就加入一套该场景的运行变量 $z^s$ 和运行约束。

## 8. dual oracle

固定主问题得到的当前储能规划 $x^k$，oracle 要求：

$$
\max_{d\in\Xi}Q(x^k,d)
$$

二阶段原问题是 LP，因此可用第 6 节的对偶模型替换：

$$
Q(x^k,d)
=
\max_{\lambda,\mu,\alpha,\beta,\gamma,\delta,\zeta,\kappa,\tau}
\quad
\text{二阶段对偶目标}
$$

$$
\text{s.t.}
\quad
\text{二阶段对偶约束}
$$

$$
d=(u,v)\in\Xi
$$

将第 6 节的对偶目标代入不确定集合后，oracle 的 MILP 目标写成：

$$
\begin{aligned}
\max\quad
&
\sum_h \widehat L_h\lambda_h
+
\sum_h \Delta L_h\omega^L_h
-
\sum_{g,h}\widehat G_g\mu_{gh}
+
\sum_{g,h}\Delta G_g\omega^G_{gh}\\
&
-
\sum_{b,h}(\alpha_{bh}+\beta_{bh}+\gamma_{bh})\overline P^k_b
+
\sum_{b,h}(SOC_{\min}\delta_{bh}-\zeta_{bh})\overline E^k_b
+
\sum_b SOC_0\kappa_b\overline E^k_b
\end{aligned}
$$

其中：

$$
\omega^L_h=\lambda_hu_h
$$

$$
\omega^G_{gh}=\mu_{gh}v_h
$$

预算不确定集合为：

$$
u_h\in\{0,1\},\quad v_h\in\{0,1\}
$$

$$
\sum_h u_h\le\Gamma_L
$$

$$
\sum_h v_h\le\Gamma_G
$$

oracle 还必须包含第 6 节全部对偶约束和符号约束。

### 8.1 big-M 线性化

负荷扰动乘积：

$$
\omega^L_h=\lambda_hu_h
$$

使用：

$$
0\le\omega^L_h\le M^\lambda_hu_h
$$

$$
\omega^L_h\le\lambda_h
$$

$$
\omega^L_h\ge\lambda_h-M^\lambda_h(1-u_h)
$$

由于对偶约束里有：

$$
\lambda_h\le c^{grid}_h
$$

所以第一版取：

$$
M^\lambda_h=c^{grid}_h
$$

DG 扰动乘积：

$$
\omega^G_{gh}=\mu_{gh}v_h
$$

使用：

$$
0\le\omega^G_{gh}\le M^\mu_{gh}v_h
$$

$$
\omega^G_{gh}\le\mu_{gh}
$$

$$
\omega^G_{gh}\ge\mu_{gh}-M^\mu_{gh}(1-v_h)
$$

对 $\mu_{gh}$ 使用显式建模上界：

$$
0\le\mu_{gh}\le M^\mu_{gh}
$$

第一版取：

$$
M^\mu_{gh}=\max\{0,\ c^{grid}_h-c^{DG}\}
$$

这个上界来自对偶约束 $\lambda_h-\mu_{gh}\le c^{DG}$ 和 $\lambda_h\le c^{grid}_h$ 的边际价格解释：当 DG 比电网便宜时，DG 可用容量的最高价值不超过电网购电和 DG 出力的单位成本差；当 DG 不比电网便宜时，DG 可用容量没有正影子价值。

更严格地说，这个上界依赖 $\rho_G<1$。oracle 目标中与 $\mu_{gh}$ 相关的净系数为：

$$
-\widehat G_g\mu_{gh}+\Delta G_g\omega^G_{gh}
$$

当 $v_h=1$ 且 $\omega^G_{gh}=\mu_{gh}$ 时，净系数为：

$$
-(1-\rho_G)\widehat G_g\mu_{gh}<0
$$

当 $v_h=0$ 时，净系数为 $-\widehat G_g\mu_{gh}<0$。因此在最优解中，$\mu_{gh}$ 会取满足 $\lambda_h-\mu_{gh}\le c^{DG}$ 的最小非负值：

$$
\mu_{gh}^\star=\max\{0,\lambda_h-c^{DG}\}
$$

又因为 $\lambda_h\le c^{grid}_h$，所以：

$$
\mu_{gh}^\star\le \max\{0,\ c^{grid}_h-c^{DG}\}
$$

脚本使用这个界来线性化 $\mu_{gh}v_h$，并在 oracle 后用 primal LP 校验目标值，避免上界推导错误被静默带入结果。

### 8.2 oracle 输出的场景

求解 dual oracle 后，读取：

$$
u_h^\star,\quad v_h^\star
$$

生成下一轮主问题要加入的固定场景：

$$
L_h^{k+1}=\widehat L_h+\Delta L_hu_h^\star
$$

$$
G_{gh}^{k+1}=\widehat G_g-\Delta G_gv_h^\star
$$

这个场景再回到主问题中，用原始二阶段运行 LP 加入，而不是用对偶形式加入。也就是说：

$$
\text{oracle 用对偶找场景，master 用原问题加入场景。}
$$

这样最符合 CCG 的 column-and-constraint 直觉。

### 8.3 primal 校验

每轮 oracle 得到 $d^{k+1}$ 后，脚本立即固定 $x^k$ 和 $d^{k+1}$ 求解二阶段 primal LP：

$$
Q^{P}(x^k,d^{k+1})
=
\min_z\{q^\top z\mid z\text{ 满足第 5 节运行约束}\}
$$

并检查：

$$
|Q^{P}(x^k,d^{k+1})-Q^{D}(x^k,d^{k+1})|\le \epsilon_{\text{dual}}
$$

其中 $Q^D$ 是 dual oracle 的目标值。通过校验后，用 $Q^{P}$ 更新：

$$
\text{violation}=Q^{P}(x^k,d^{k+1})-\eta^k
$$

$$
UB_k=\min\{UB_{k-1},\ C^{\text{inv}}(x^k)+Q^{P}(x^k,d^{k+1})\}
$$

## 9. 对偶价格的物理含义

新脚本的输出表会保留关键对偶价格，便于检查 oracle 为什么选择某些小时作为最坏扰动：

| 对偶变量 | 通俗含义 |
|---|---|
| $\lambda_h$ | 小时 $h$ 多 1 MW 负荷会让运行成本增加多少 |
| $\mu_{gh}$ | 节点 $g$ 小时 $h$ 多 1 MW DG 可用容量能让成本降低多少 |
| $\alpha,\beta,\gamma$ | 储能功率容量在充电、放电、共用变流器约束上的价值 |
| $\delta,\zeta$ | 储能能量容量和 SOC 边界的价值 |
| $\tau_{bh}$ | 储能跨时段搬运能量的时间价值 |

所以 dual oracle 选择 $u_h=1$ 的小时，通常是 $\lambda_h$ 高的小时；选择 $v_h=1$ 的小时，通常是 $\mu_{gh}$ 高的小时。

这正是对偶在 CCG 中的作用：它不只告诉我们最坏成本是多少，还告诉我们哪个负荷小时、哪个 DG 小时最有破坏力。

## 10. 算法流程

初始化：

$$
\mathcal S_1=\{d^{base}\}
$$

第 $k$ 轮：

1. 解主问题，得到 $x^k,\eta^k$。
2. 固定 $x^k$，解 dual oracle，得到最坏扰动 $d^{k+1}$ 和最坏运行成本 $Q(x^k,d^{k+1})$。
3. 计算违反量：

$$
\text{violation}
=
Q(x^k,d^{k+1})-\eta^k
$$

4. 如果：

$$
\text{violation}\le \epsilon
$$

则停止。

5. 否则把 $d^{k+1}$ 加入 $\mathcal S_k$，下一轮主问题加入该场景的运行变量和约束。

上下界更新：

$$
LB_k=C^{\text{inv}}(x^k)+\eta^k
$$

$$
UB_k=\min\{UB_{k-1},\ C^{\text{inv}}(x^k)+Q(x^k,d^{k+1})\}
$$

## 11. 新脚本结构

计划保持单文件脚本，不拆辅助模块：

```text
planning/ccg_dual_storage_ieee33.py
```

建议函数如下：

| 函数 | 作用 |
|---|---|
| `investment_expr` | 第一阶段投资成本 |
| `base_data` | 聚合 IEEE33 的 24 小时总负荷、DG 上限和电价 |
| `add_operation_primal` | 给主问题加入一个固定扰动场景的二阶段 LP |
| `build_master` | 构造 CCG 主问题 |
| `solve_dual_oracle` | 固定 $x^k$，求 dual oracle |
| `scenario_from_oracle` | 把 oracle 的 $u_h,v_h$ 转成主问题可用的固定场景数据 |
| `solve_operation_primal` | 固定规划和扰动，求二阶段 primal LP，并校验 oracle |

这些函数只服务本脚本，不做通用库。变量命名尽量贴近公式。

## 12. 输出内容

脚本运行后输出：

| 输出 | 含义 |
|---|---|
| `ccg_dual_progress` | 每轮 LB、UB、violation、最坏小时扰动 |
| `dual_oracle_detail` | oracle 中 $u_h,v_h$、平衡对偶价格、DG 对偶价格 |
| `active_scenarios` | 每轮加入主问题的扰动场景 |
| `storage_plan` | 最终储能选址、功率容量、能量容量 |
| `final_dispatch` | 收敛方案在最终最坏扰动下的聚合运行调度 |

保存位置沿用：

```text
results/planning/ccg_dual/
```

文件名计划为：

```text
ccg_dual_storage_ieee33_summary.xlsx
ccg_dual_01_convergence.png
ccg_dual_02_worst_uncertainty.png
ccg_dual_03_storage_plan.png
ccg_dual_04_dispatch.png
```

## 13. 已确认的建模取舍

本轮审阅已确认四件事：

1. 第一版先使用线性有功调度 LP，并在文档中给出完整二阶段原问题和对偶模型。
2. 不确定集合先只包含负荷上浮和 DG 下调，暂不包含电价扰动。
3. dual oracle 使用二进制预算扰动和显式 big-M 线性化，得到一个可直接由 Gurobi 求解的 MILP oracle。
4. 每轮 oracle 后必须求 primal LP 校验 dual 目标，并用 primal 目标更新违反量和 UB。

本计划对应的脚本为 `planning/ccg_dual_storage_ieee33.py`。执行后应检查 primal-dual 校验未报错，并确认 `results/planning/ccg_dual/ccg_dual_storage_ieee33_summary.xlsx` 与 `ccg_dual_*.png` 已生成。
