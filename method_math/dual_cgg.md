# 从对偶到 CCG 的 max-min oracle

本文把前面讨论过的内容串成一条完整逻辑链：

1. 为什么会想到“把约束乘上非负权重再加起来”。
2. 对偶问题是如何自然长出来的。
3. 影子价格和互补松弛是什么意思。
4. 为什么 CCG 的内层运行问题可以替换成对偶问题。
5. 抽象式 $Wy\ge h(d)-Tx^k$ 到底从哪里来。
6. 用电热补救例子理解 $q,W,h(d),T$ 和对偶变量。
7. 对偶化之后，max-min oracle 如何变成单层最大化问题。

配套 notebook：

```text
method_math/dual_cgg.ipynb
```

文件名使用 `dual_cgg`，正文里仍然称算法为 CCG。

## 1. 先从“证明上界”开始

考虑一个生产计划问题：

$$
\begin{aligned}
\max_{x_1,x_2}
\quad & 3x_1+2x_2 \\
\text{s.t.}
\quad & x_1+x_2\le4 \\
& 2x_1+x_2\le5 \\
& x_1,x_2\ge0
\end{aligned}
$$

其中：

| 符号 | 含义 |
|---|---|
| $x_1$ | 产品 1 的产量 |
| $x_2$ | 产品 2 的产量 |
| $3x_1+2x_2$ | 总利润 |
| $x_1+x_2\le4$ | 资源 1 的上限 |
| $2x_1+x_2\le5$ | 资源 2 的上限 |

原问题问的是：

$$
\text{在资源有限时，最大利润是多少？}
$$

但是我们也可以换一个角度问：

$$
\text{能不能用资源约束证明利润不可能超过某个数？}
$$

这就是对偶的起点。

## 2. 为什么把约束乘上非负权重再加起来

我们手里已经确定为真的不等式只有资源约束：

$$
x_1+x_2\le4
$$

$$
2x_1+x_2\le5
$$

如果我们想证明：

$$
3x_1+2x_2\le \text{某个上界}
$$

最自然的方法就是从这些已经为真的不等式出发，构造一个新的仍然为真的不等式。

取非负权重：

$$
y_1\ge0,\quad y_2\ge0
$$

第一条约束乘以 $y_1$：

$$
y_1x_1+y_1x_2\le4y_1
$$

第二条约束乘以 $y_2$：

$$
2y_2x_1+y_2x_2\le5y_2
$$

因为 $y_1,y_2$ 非负，所以不等号方向不变。再把两条加起来：

$$
(y_1+2y_2)x_1+(y_1+y_2)x_2
\le
4y_1+5y_2
$$

这条新不等式对所有原问题可行解都成立。

现在如果让新不等式左边的系数覆盖原目标函数的系数：

$$
y_1+2y_2\ge3
$$

$$
y_1+y_2\ge2
$$

又因为：

$$
x_1,x_2\ge0
$$

所以：

$$
3x_1+2x_2
\le
(y_1+2y_2)x_1+(y_1+y_2)x_2
$$

再结合前面的组合约束：

$$
(y_1+2y_2)x_1+(y_1+y_2)x_2
\le
4y_1+5y_2
$$

得到：

$$
3x_1+2x_2\le4y_1+5y_2
$$

因此，只要 $y_1,y_2$ 满足这些条件，$4y_1+5y_2$ 就是原问题最大利润的一个上界。

## 3. 对偶问题就是“找最紧的上界证明”

既然 $4y_1+5y_2$ 是上界，我们自然希望这个上界尽可能紧。

于是得到：

$$
\begin{aligned}
\min_{y_1,y_2}
\quad & 4y_1+5y_2 \\
\text{s.t.}
\quad & y_1+2y_2\ge3 \\
& y_1+y_2\ge2 \\
& y_1,y_2\ge0
\end{aligned}
$$

这就是原问题的对偶问题。

所以对偶不是凭空定义出来的。它来自一个非常自然的问题：

$$
\text{如何用原问题约束，构造一个最紧的目标上界？}
$$

一般形式为：

$$
\begin{aligned}
\max_x
\quad & c^\top x \\
\text{s.t.}
\quad & Ax\le b \\
& x\ge0
\end{aligned}
$$

取非负乘子 $y\ge0$，组合约束：

$$
y^\top Ax\le y^\top b
$$

如果：

$$
A^\top y\ge c
$$

那么：

$$
c^\top x\le y^\top Ax\le y^\top b
$$

于是 $b^\top y$ 是原问题目标的上界。找最紧上界得到对偶：

$$
\begin{aligned}
\min_y
\quad & b^\top y \\
\text{s.t.}
\quad & A^\top y\ge c \\
& y\ge0
\end{aligned}
$$

## 4. 影子价格

对偶变量 $y_i$ 可以理解为第 $i$ 个资源约束的影子价格。

影子价格的含义是：

$$
\text{如果第 }i\text{ 个约束右端多给 1 单位，最优目标值大约改善多少。}
$$

在本例中：

$$
y_1=\text{资源 1 的影子价格}
$$

$$
y_2=\text{资源 2 的影子价格}
$$

对偶目标：

$$
4y_1+5y_2
$$

就是把资源总量按照影子价格估值。

对偶约束：

$$
y_1+2y_2\ge3
$$

表示产品 1 消耗的资源价值必须至少覆盖它的单位利润。

对偶约束：

$$
y_1+y_2\ge2
$$

表示产品 2 消耗的资源价值必须至少覆盖它的单位利润。

## 5. 互补松弛

原问题和对偶问题的最优解满足互补松弛：

$$
y_i(b_i-A_i x)=0,\quad \forall i
$$

$$
x_j((A^\top y)_j-c_j)=0,\quad \forall j
$$

第一条的含义是：

$$
\text{资源影子价格}\times\text{资源剩余量}=0
$$

也就是：

| 情况 | 结论 |
|---|---|
| $b_i-A_i x>0$ | 资源没用完，所以 $y_i=0$ |
| $y_i>0$ | 资源有正价格，所以 $b_i-A_i x=0$，资源一定用满 |

第二条的含义是：

$$
\text{产品产量}\times\text{产品资源估值冗余}=0
$$

也就是：

| 情况 | 结论 |
|---|---|
| $x_j>0$ | 产品真的生产，所以它的资源估值刚好等于利润 |
| $(A^\top y)_j-c_j>0$ | 产品资源估值高于利润，所以不生产该产品 |

在例子里，最优解为：

$$
x_1=1,\quad x_2=3
$$

$$
y_1=1,\quad y_2=1
$$

两个资源都用满：

$$
x_1+x_2=4
$$

$$
2x_1+x_2=5
$$

两个产品都生产，所以两个对偶约束取等号：

$$
y_1+2y_2=3
$$

$$
y_1+y_2=2
$$

## 6. 从生产计划转向二阶段运行问题

在 CCG 中，主问题给出当前投资方案：

$$
x^k
$$

然后 oracle 要判断当前投资方案在最坏场景下的运行成本。

设不确定场景是：

$$
d
$$

运行变量是：

$$
y
$$

那么二阶段运行问题可以写成：

$$
Q(x^k,d)
=
\min_y
\quad
q^\top y
$$

$$
\text{s.t.}
\quad
Wy\ge h(d)-Tx^k
$$

$$
y\ge0
$$

其中：

| 符号 | 含义 |
|---|---|
| $x^k$ | 第 $k$ 轮主问题给出的固定投资方案 |
| $d$ | oracle 要选择的不确定场景 |
| $y$ | 二阶段运行变量 |
| $q^\top y$ | 运行成本 |
| $W$ | 运行变量在约束中的系数矩阵 |
| $h(d)$ | 不确定场景造成的需求压力 |
| $Tx^k$ | 第一阶段投资提供的能力或缓解项 |

这不是一条具体约束，而是很多条运行约束堆叠后的矩阵写法。

## 7. $Wy\ge h(d)-Tx^k$ 是怎么来的

先看最简单的单区域补救问题。

投资容量为：

$$
x
$$

需求为：

$$
d
$$

补救量为：

$$
y
$$

运行约束是：

$$
x+y\ge d
$$

改写为：

$$
y\ge d-x
$$

这就是：

$$
Wy\ge h(d)-Tx
$$

其中：

$$
W=1,\quad h(d)=d,\quad T=1
$$

所以：

$$
1\cdot y\ge d-1\cdot x
$$

再看两区域补救问题：

$$
y_1\ge d_1-x_1
$$

$$
y_2\ge d_2-x_2
$$

写成矩阵：

$$
\begin{bmatrix}
1&0\\
0&1
\end{bmatrix}
\begin{bmatrix}
y_1\\
y_2
\end{bmatrix}
\ge
\begin{bmatrix}
d_1\\
d_2
\end{bmatrix}
-
\begin{bmatrix}
1&0\\
0&1
\end{bmatrix}
\begin{bmatrix}
x_1\\
x_2
\end{bmatrix}
$$

也就是：

$$
Wy\ge h(d)-Tx
$$

在电力系统里，$y$ 可能包含：

$$
P_{ij,t},Q_{ij,t},v_{i,t},p^{grid}_t,p^{ch}_{i,t},p^{dis}_{i,t},SOC_{i,t},p^{shed}_{i,t}
$$

$d$ 可能包含：

$$
P^L_{i,t},P^{PV}_{i,t}
$$

节点功率平衡、线路潮流、电压约束、储能约束、切负荷约束等线性化后都可以堆叠进 $Wy\ge h(d)-Tx^k$。

## 8. 把内层优化问题替换成对偶问题

内层运行问题是：

$$
Q(x^k,d)
=
\min_y
\quad
q^\top y
$$

$$
\text{s.t.}
\quad
Wy\ge h(d)-Tx^k
$$

$$
y\ge0
$$

给约束：

$$
Wy\ge h(d)-Tx^k
$$

配对偶变量：

$$
\pi\ge0
$$

因为这是一个最小化问题中的 $\ge$ 约束，所以对偶变量非负。

对偶目标来自原问题右端：

$$
\pi^\top(h(d)-Tx^k)
$$

对偶约束来自原变量 $y\ge0$ 和目标系数 $q$：

$$
W^\top\pi\le q
$$

因此对偶问题为：

$$
Q(x^k,d)
=
\max_\pi
\quad
\pi^\top(h(d)-Tx^k)
$$

$$
\text{s.t.}
\quad
W^\top\pi\le q
$$

$$
\pi\ge0
$$

如果内层 LP 可行且有有限最优值，强对偶保证：

$$
\min_y
\left\{
q^\top y
\mid
Wy\ge h(d)-Tx^k,\ y\ge0
\right\}
=
\max_\pi
\left\{
\pi^\top(h(d)-Tx^k)
\mid
W^\top\pi\le q,\ \pi\ge0
\right\}
$$

所以替换是精确等价，不是近似。

## 9. 电热补救例子：看懂 $q,W,h(d),T$ 和 $\pi$

考虑一个很小的电热联合补救调度。第一阶段已经提前安排了电力和热力供应：

$$
x=
\begin{bmatrix}
x_E\\
x_H
\end{bmatrix}
$$

其中 $x_E$ 是提前安排的电力供应，$x_H$ 是提前安排的热力供应。

某个场景 $d$ 下，电负荷和热负荷为：

$$
h(d)=
\begin{bmatrix}
80\\
50
\end{bmatrix}
$$

第二阶段可以临时使用三类补救资源：

$$
y=
\begin{bmatrix}
y_G\\
y_B\\
y_C
\end{bmatrix}
$$

其中 $y_G$ 是燃气机发电，$y_B$ 是锅炉供热，$y_C$ 是 CHP 联产。

单位补救成本为：

$$
q=
\begin{bmatrix}
50\\
40\\
70
\end{bmatrix}
$$

所以：

$$
q^\top y=50y_G+40y_B+70y_C
$$

运行约束写成：

$$
\begin{bmatrix}
1&0&1\\
0&1&1
\end{bmatrix}
\begin{bmatrix}
y_G\\
y_B\\
y_C
\end{bmatrix}
\ge
\begin{bmatrix}
80\\
50
\end{bmatrix}
-
\begin{bmatrix}
1&0\\
0&1
\end{bmatrix}
\begin{bmatrix}
x_E\\
x_H
\end{bmatrix}
$$

也就是：

$$
W=
\begin{bmatrix}
1&0&1\\
0&1&1
\end{bmatrix},
\quad
T=
\begin{bmatrix}
1&0\\
0&1
\end{bmatrix}
$$

第一行是电力缺口约束：

$$
y_G+y_C\ge80-x_E
$$

第二行是热力缺口约束：

$$
y_B+y_C\ge50-x_H
$$

这里 $W$ 的每一列表示一种补救资源对电、热两条约束的贡献。CHP 的列是 $(1,1)^\top$，表示生产 1 单位 CHP 同时贡献 1 单位电和 1 单位热。

假设当前主问题给出的第一阶段方案为：

$$
x^k=
\begin{bmatrix}
30\\
10
\end{bmatrix}
$$

则剩余需求为：

$$
h(d)-Tx^k
=
\begin{bmatrix}
80\\
50
\end{bmatrix}
-
\begin{bmatrix}
30\\
10
\end{bmatrix}
=
\begin{bmatrix}
50\\
40
\end{bmatrix}
$$

内层原问题为：

$$
\begin{aligned}
Q(x^k,d)=
\min_{y_G,y_B,y_C}
\quad & 50y_G+40y_B+70y_C\\
\text{s.t.}
\quad & y_G+y_C\ge50\\
& y_B+y_C\ge40\\
& y_G,y_B,y_C\ge0
\end{aligned}
$$

一个最优补救方案是：

$$
y_G=10,\quad y_B=0,\quad y_C=40
$$

对应成本为：

$$
Q(x^k,d)=50\times10+70\times40=3300
$$

给电力缺口约束和热力缺口约束分别配对偶变量：

$$
\pi=
\begin{bmatrix}
\pi_E\\
\pi_H
\end{bmatrix}
\ge0
$$

对偶问题为：

$$
\begin{aligned}
Q(x^k,d)=
\max_{\pi_E,\pi_H}
\quad & 50\pi_E+40\pi_H\\
\text{s.t.}
\quad & \pi_E\le50\\
& \pi_H\le40\\
& \pi_E+\pi_H\le70\\
& \pi_E,\pi_H\ge0
\end{aligned}
$$

三条对偶约束分别来自三个补救变量：

| 原变量 | 对偶约束 | 含义 |
|---|---|---|
| $y_G$ | $\pi_E\le50$ | 1 单位电的影子价值不能超过燃气机单位发电成本 |
| $y_B$ | $\pi_H\le40$ | 1 单位热的影子价值不能超过锅炉单位供热成本 |
| $y_C$ | $\pi_E+\pi_H\le70$ | CHP 同时供电供热，二者影子价值之和不能超过 CHP 单位成本 |

一个最优对偶解是：

$$
\pi_E=50,\quad \pi_H=20
$$

于是：

$$
50\pi_E+40\pi_H=50\times50+40\times20=3300
$$

这与原问题最优补救成本相同。它的物理含义是：

| 对偶变量 | 含义 |
|---|---|
| $\pi_E=50$ | 电力缺口多 1 单位，最优补救成本大约增加 50 |
| $\pi_H=20$ | 热力缺口多 1 单位，最优补救成本大约增加 20 |

热力影子价格不是锅炉成本 40，而是 20。原因是当前方案里 CHP 和燃气机共同决定边际成本：多 1 单位热可以多用 1 单位 CHP，同时少用 1 单位燃气机，成本变化为 $70-50=20$。

如果把这个对偶解拿来生成 Benders 最优性割：

$$
\theta\ge{\pi^\star}^\top(h(d)-Tx)
$$

则：

$$
\theta
\ge
\begin{bmatrix}
50&20
\end{bmatrix}
\left(
\begin{bmatrix}
80\\
50
\end{bmatrix}
-
\begin{bmatrix}
x_E\\
x_H
\end{bmatrix}
\right)
$$

也就是：

$$
\theta\ge5000-50x_E-20x_H
$$

这里的割系数 $-50$ 和 $-20$ 表示：第一阶段多准备 1 单位电，二阶段成本大约少 50；第一阶段多准备 1 单位热，二阶段成本大约少 20。一般地，割对 $x$ 的系数就是：

$$
-T^\top\pi^\star
$$

## 10. 用最小补救问题看对偶替换

内层原问题：

$$
Q(x,d)
=
\min_y
\quad
5y
$$

$$
\text{s.t.}
\quad
y\ge d-x
$$

$$
y\ge0
$$

这里：

$$
q=5,\quad W=1,\quad h(d)=d,\quad T=1
$$

对偶变量为：

$$
\pi\ge0
$$

对偶问题为：

$$
Q(x,d)
=
\max_\pi
\quad
\pi(d-x)
$$

$$
\text{s.t.}
\quad
0\le\pi\le5
$$

如果：

$$
d-x>0
$$

则对偶目标 $\pi(d-x)$ 随 $\pi$ 增大而增大，所以：

$$
\pi^\star=5
$$

得到：

$$
Q(x,d)=5(d-x)
$$

如果：

$$
d-x<0
$$

则对偶目标 $\pi(d-x)$ 随 $\pi$ 增大而减小，所以：

$$
\pi^\star=0
$$

得到：

$$
Q(x,d)=0
$$

合起来：

$$
Q(x,d)=5\max(d-x,0)
$$

这和原问题完全一致。

## 11. 回到 CCG 的 max-min oracle

CCG 第 $k$ 轮主问题得到：

$$
x^k,\eta^k
$$

oracle 要找：

$$
d^{k+1}
\in
\arg\max_{d\in\Xi} Q(x^k,d)
$$

如果 $Q$ 是内层运行优化问题：

$$
Q(x^k,d)
=
\min_y
\left\{
q^\top y
\mid
Wy\ge h(d)-Tx^k,\ y\ge0
\right\}
$$

那么 oracle 是：

$$
\max_{d\in\Xi}
\min_y
\left\{
q^\top y
\mid
Wy\ge h(d)-Tx^k,\ y\ge0
\right\}
$$

这就是 max-min oracle。

对内层 $\min_y$ 做对偶：

$$
\min_y(\cdots)
=
\max_\pi
\left\{
\pi^\top(h(d)-Tx^k)
\mid
W^\top\pi\le q,\ \pi\ge0
\right\}
$$

所以：

$$
\max_{d\in\Xi}\min_y(\cdots)
=
\max_{d\in\Xi}\max_\pi(\cdots)
$$

两个最大化可以合并：

$$
\max_{d,\pi}
\quad
\pi^\top(h(d)-Tx^k)
$$

$$
\text{s.t.}
\quad
d\in\Xi
$$

$$
W^\top\pi\le q
$$

$$
\pi\ge0
$$

于是嵌套问题：

$$
\max_d\min_y
$$

变成单层问题：

$$
\max_{d,\pi}
$$

这就是对偶在 CCG 中最重要的作用。

## 12. 为什么对偶化后还会变难

如果：

$$
h(d)=h_0+Hd
$$

则对偶化 oracle 的目标为：

$$
\pi^\top(h_0+Hd-Tx^k)
$$

展开：

$$
\pi^\top(h_0-Tx^k)+\pi^\top H d
$$

其中：

$$
\pi^\top H d
$$

包含对偶变量 $\pi$ 和不确定变量 $d$ 的乘积。

这就是双线性项。

因此很多 CCG 论文里会出现：

| 技术 | 原因 |
|---|---|
| 强对偶 | 把内层 $\min_y$ 替换成对偶 $\max_\pi$ |
| KKT | 用最优性条件描述内层问题 |
| big-M | 线性化互补条件或离散逻辑 |
| McCormick 包络 | 线性化连续变量乘积 |
| 预算不确定集合 | 控制最坏场景不要全部同时取极端 |

所以对偶化解决了嵌套 max-min 的结构问题，但可能带来双线性或混合整数结构。

## 13. 这条链路的最终总结

从对偶到 CCG 的逻辑链是：

$$
\text{用原约束组合出目标上界}
$$

$$
\Downarrow
$$

$$
\text{找最紧上界，得到对偶问题}
$$

$$
\Downarrow
$$

$$
\text{对偶变量成为约束影子价格}
$$

$$
\Downarrow
$$

$$
\text{内层运行 LP 的最优值可以用对偶最优值替代}
$$

$$
\Downarrow
$$

$$
\max_{d\in\Xi}\min_y
\quad
\Longrightarrow
\quad
\max_{d,\pi}
$$

对 CCG 来说，最重要的一句话是：

$$
\boxed{
\text{对偶让 max-min oracle 里的内层运行优化问题显式化。}
}
$$
