"""低压配网建筑分配的 Branch-and-Price 教学脚本。"""

from itertools import combinations, count
from pathlib import Path
import heapq
import sys

import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from network.case6 import ROOT_DIR  # noqa: E402


OUT_DIR = ROOT_DIR / "results" / "planning" / "branch_price"
OUTPUT_XLSX = OUT_DIR / "branch_price_summary.xlsx"
TOL = 1e-7

houses = list(range(1, 11))
transformers = ["A", "B", "C"]
load = {1: 6, 2: 5, 3: 7, 4: 8, 5: 6, 6: 7, 7: 5, 8: 6, 9: 5, 10: 4}
capacity = {t: 28 for t in transformers}

road_rows = [
    ("A", 1, 1.0, "main"),
    (1, 2, 1.0, "main"),
    (1, 3, 1.0, "main"),
    (3, 4, 1.0, "main"),
    (4, 5, 1.0, "main"),
    (5, 6, 1.0, "main"),
    (6, 7, 1.0, "main"),
    (7, "B", 1.0, "main"),
    (6, 8, 1.0, "main"),
    (8, 9, 1.0, "main"),
    (9, 10, 1.0, "main"),
    (10, "C", 1.0, "main"),
    (2, 4, 1.4, "shortcut"),
]

coord = {
    "A": (-1.0, 0.0),
    1: (0.0, 0.0),
    2: (0.0, 1.0),
    3: (1.0, 0.0),
    4: (2.0, 0.0),
    5: (3.0, 0.0),
    6: (4.0, 0.0),
    7: (5.0, 0.0),
    "B": (6.0, 0.0),
    8: (4.0, -1.0),
    9: (5.0, -1.0),
    10: (6.0, -1.0),
    "C": (7.0, -1.0),
}

fixed_column_cost = 5.0
length_cost = 0.2
distance_load_cost = 0.05
voltage_drop_alpha = 0.001
voltage_drop_max = 0.12

color = {"A": "#2766b0", "B": "#cf3e28", "C": "#4f9b58"}
initial_sets = {"A": (1, 2, 3, 4), "B": (5, 6, 7, 8), "C": (9, 10)}
branch_seed_sets = {
    "left_A_H2_eq_1": {"A": (1, 2, 3, 4), "B": (5, 6, 7, 8), "C": (9, 10)},
    "right_A_H2_eq_0": {"A": (1,), "B": (2, 3, 4, 5), "C": (6, 7, 8, 9, 10)},
}


def edge_key(u, v):
    return tuple(sorted((str(u), str(v))))


adj = {}
road_length = {}
road_kind = {}
for u, v, length, kind in road_rows:
    adj.setdefault(u, []).append((v, length))
    adj.setdefault(v, []).append((u, length))
    road_length[edge_key(u, v)] = length
    road_kind[edge_key(u, v)] = kind


def shortest_paths(root):
    order = count()
    dist = {root: 0.0}
    prev = {root: None}
    pq = [(0.0, next(order), root)]
    while pq:
        d, _, u = heapq.heappop(pq)
        if abs(d - dist[u]) > 1e-9:
            continue
        for v, length in adj[u]:
            nd = d + length
            if nd < dist.get(v, 1e100) - 1e-9:
                dist[v] = nd
                prev[v] = (u, length)
                heapq.heappush(pq, (nd, next(order), v))

    paths = {}
    for i in houses:
        path = []
        u = i
        while u != root:
            v, length = prev[u]
            path.append((v, u, length))
            u = v
        paths[i] = list(reversed(path))
    return paths


paths_by_transformer = {t: shortest_paths(t) for t in transformers}


def connected_houses(S):
    if not S:
        return True
    S = set(S)
    seen = {next(iter(S))}
    stack = list(seen)
    while stack:
        u = stack.pop()
        for v, _ in adj[u]:
            if v in S and v not in seen:
                seen.add(v)
                stack.append(v)
    return seen == S


def column_candidate(t, S):
    S = tuple(sorted(S))
    if not S:
        return {"ok": True, "reason": "ok", "column": {
            "transformer": t, "houses": S, "load": 0.0, "length": 0.0, "distance_load": 0.0,
            "max_drop": 0.0, "cost": 0.0, "feeder_edges": tuple(), "paths": {},
        }}

    total_load = sum(load[i] for i in S)
    if total_load > capacity[t]:
        return {"ok": False, "reason": "capacity", "column": None}
    if not connected_houses(S):
        return {"ok": False, "reason": "disconnected", "column": None}

    paths = {i: paths_by_transformer[t][i] for i in S}
    feeder = {}
    for path in paths.values():
        for u, v, length in path:
            feeder[edge_key(u, v)] = (u, v, length)

    downstream = {e: 0.0 for e in feeder}
    for i, path in paths.items():
        for u, v, _ in path:
            downstream[edge_key(u, v)] += load[i]

    house_drop = {
        i: voltage_drop_alpha * sum(length * downstream[edge_key(u, v)] for u, v, length in path)
        for i, path in paths.items()
    }
    max_drop = max(house_drop.values())
    if max_drop > voltage_drop_max:
        return {"ok": False, "reason": "voltage", "column": None}

    feeder_length = sum(length for _, _, length in feeder.values())
    distance_load = sum(load[i] * sum(length for _, _, length in paths[i]) for i in S)
    cost = fixed_column_cost + length_cost * feeder_length + distance_load_cost * distance_load
    return {"ok": True, "reason": "ok", "column": {
        "transformer": t, "houses": S, "load": total_load, "length": feeder_length,
        "distance_load": distance_load, "max_drop": max_drop, "cost": cost,
        "feeder_edges": tuple(sorted(feeder.keys())), "paths": paths,
    }}


def build_column_pool():
    columns = []
    rejected = []
    for t in transformers:
        empty = column_candidate(t, ())["column"]
        columns.append(empty)
        for r in range(1, len(houses) + 1):
            for S in combinations(houses, r):
                result = column_candidate(t, S)
                if result["ok"]:
                    columns.append(result["column"])
                else:
                    rejected.append((t, S, result["reason"]))

    for k, col in enumerate(columns):
        col["id"] = f"C{k:03d}"
        col["houses_text"] = "empty" if not col["houses"] else ",".join(f"H{i}" for i in col["houses"])
        col["feeder_text"] = "none" if not col["feeder_edges"] else "; ".join(f"{u}-{v}" for u, v in col["feeder_edges"])
    id_map = {(col["transformer"], col["houses"]): k for k, col in enumerate(columns)}
    return columns, id_map, rejected


columns, id_map, rejected_columns = build_column_pool()


def allowed_by_branch(k, branch):
    col = columns[k]
    for (t, i), val in branch.items():
        if col["transformer"] == t:
            if val == 1 and i not in col["houses"]:
                return False
            if val == 0 and i in col["houses"]:
                return False
        elif val == 1 and i in col["houses"]:
            return False
    return True


def set_gurobi_params(m):
    m.Params.LogToConsole = 0
    m.Params.Threads = 1
    m.Params.Method = 0
    m.Params.Presolve = 0


def solve_master(active, branch=None, binary=False, name="rmp"):
    branch = branch or {}
    use = sorted(k for k in active if allowed_by_branch(k, branch))
    m = gp.Model(name)
    set_gurobi_params(m)
    x = m.addVars(use, lb=0, ub=1, vtype=GRB.BINARY if binary else GRB.CONTINUOUS, name="x")
    cover = {
        i: m.addConstr(gp.quicksum(x[k] for k in use if i in columns[k]["houses"]) == 1, name=f"cover[H{i}]")
        for i in houses
    }
    choose = {
        t: m.addConstr(gp.quicksum(x[k] for k in use if columns[k]["transformer"] == t) == 1, name=f"choose[{t}]")
        for t in transformers
    }
    m.setObjective(gp.quicksum(columns[k]["cost"] * x[k] for k in use), GRB.MINIMIZE)
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"{name} status {m.Status}")
    return m, x, cover, choose, use


def solution_entries(x, use):
    return [(k, x[k].X, columns[k]) for k in use if x[k].X > 1e-8]


def solution_text(entries):
    parts = []
    for _, val, col in entries:
        parts.append(f"{val:.3f} {col['transformer']} -> {col['houses_text']} (c={col['cost']:.2f})")
    return "; ".join(parts)


def assignment_fraction(entries):
    rows = []
    for i in houses:
        row = {"house": f"H{i}"}
        for t in transformers:
            row[t] = sum(val for _, val, col in entries if col["transformer"] == t and i in col["houses"])
        rows.append(row)
    return pd.DataFrame(rows)


def min_pricing_columns(pi, sigma, active, branch):
    rows = []
    add = []
    for t in transformers:
        candidates = []
        for k, col in enumerate(columns):
            if col["transformer"] != t or k in active or not allowed_by_branch(k, branch):
                continue
            cover_dual = sum(pi[i] for i in col["houses"])
            rc = col["cost"] - cover_dual - sigma[t]
            candidates.append((rc, k, cover_dual))
        if candidates:
            rc, k, cover_dual = min(candidates, key=lambda item: item[0])
            col = columns[k]
            rows.append({
                "transformer": t, "column_id": col["id"], "houses": col["houses_text"],
                "cost": col["cost"], "cover_dual_sum": cover_dual, "sigma": sigma[t],
                "reduced_cost": rc, "added": rc < -TOL,
            })
            if rc < -TOL:
                add.append(k)
    return rows, add


def run_column_generation(node, branch, active_start):
    active = set(k for k in active_start if allowed_by_branch(k, branch))
    iter_rows, dual_rows, pricing_rows, snapshots = [], [], [], []

    for it in range(40):
        m, x, cover, choose, use = solve_master(active, branch, binary=False, name=f"{node}_rmp_{it}")
        entries = solution_entries(x, use)
        pi = {i: cover[i].Pi for i in houses}
        sigma = {t: choose[t].Pi for t in transformers}
        price_rows, add = min_pricing_columns(pi, sigma, active, branch)

        iter_rows.append({
            "node": node, "iteration": it, "objective": m.ObjVal, "active_columns": len(active),
            "new_columns": ",".join(columns[k]["id"] for k in add), "solution": solution_text(entries),
            "integer_solution": all(abs(val - round(val)) <= 1e-7 for _, val, _ in entries),
        })
        for i in houses:
            dual_rows.append({"node": node, "iteration": it, "kind": "cover", "item": f"H{i}", "dual": pi[i]})
        for t in transformers:
            dual_rows.append({"node": node, "iteration": it, "kind": "choose", "item": t, "dual": sigma[t]})
        for row in price_rows:
            row = row.copy()
            row["node"] = node
            row["iteration"] = it
            pricing_rows.append(row)
        snapshots.append({
            "iteration": it, "objective": m.ObjVal, "entries": entries, "pi": pi,
            "sigma": sigma, "pricing": price_rows, "added": list(add),
        })

        if not add:
            return {
                "node": node, "branch": branch, "active": active, "model": m, "x": x, "use": use,
                "entries": entries, "iterations": iter_rows, "duals": dual_rows,
                "pricing": pricing_rows, "snapshots": snapshots, "lower_bound": m.ObjVal,
                "integer": all(abs(val - round(val)) <= 1e-7 for _, val, _ in entries),
            }
        active.update(add)

    raise RuntimeError(f"{node} column generation did not converge")


def solve_full_validation(binary=True):
    active = set(range(len(columns)))
    m, x, _, _, use = solve_master(active, {}, binary=binary, name="full_column_validation")
    return m, x, use, solution_entries(x, use)


def seed_active(seed_sets):
    return {id_map[(t, seed_sets[t])] for t in transformers}


def md_table(rows, headers):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def fmt(x, nd=4):
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return x


def draw_base(ax):
    for u, v, length, kind in road_rows:
        x1, y1 = coord[u]
        x2, y2 = coord[v]
        ls = "--" if kind == "shortcut" else "-"
        ax.plot([x1, x2], [y1, y2], color="#b8b8b8", lw=2.0, ls=ls, zorder=1)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.08, f"{length:g}", fontsize=8, color="#777777", ha="center")

    for i in houses:
        x, y = coord[i]
        ax.scatter(x, y, s=240, facecolor="white", edgecolor="#333333", lw=1.4, zorder=5)
        ax.text(x, y + 0.02, f"H{i}", ha="center", va="center", fontsize=9, zorder=6)
        ax.text(x, y - 0.28, f"d={load[i]}", ha="center", va="center", fontsize=8, color="#555555", zorder=6)

    for t in transformers:
        x, y = coord[t]
        ax.scatter(x, y, s=280, marker="s", facecolor=color[t], edgecolor="#222222", lw=1.0, zorder=6)
        ax.text(x, y + 0.35, f"T{t}", ha="center", va="center", fontsize=10, weight="bold", color=color[t])

    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_xlim(-1.6, 7.5)
    ax.set_ylim(-1.7, 1.6)


def draw_pie(ax, x, y, shares):
    start = 90.0
    radius = 0.18
    for t in transformers:
        frac = shares.get(t, 0.0)
        if frac <= 1e-8:
            continue
        wedge = Wedge((x, y), radius, start, start + 360 * frac, facecolor=color[t], edgecolor="white", lw=0.5, zorder=7)
        ax.add_patch(wedge)
        start += 360 * frac
    ax.add_patch(plt.Circle((x, y), radius, fill=False, color="#222222", lw=0.6, zorder=8))


def plot_solution(filename, title, entries, highlight=None):
    highlight = highlight or []
    fig, ax = plt.subplots(figsize=(10, 4.8))
    draw_base(ax)

    for _, val, col in entries:
        if not col["houses"]:
            continue
        for key in col["feeder_edges"]:
            u, v = next((u, v) for u, v, _, _ in road_rows if edge_key(u, v) == key)
            x1, y1 = coord[u]
            x2, y2 = coord[v]
            ax.plot([x1, x2], [y1, y2], color=color[col["transformer"]], lw=1.5 + 4.0 * val, alpha=0.55, zorder=2)

    for k in highlight:
        col = columns[k]
        for key in col["feeder_edges"]:
            u, v = next((u, v) for u, v, _, _ in road_rows if edge_key(u, v) == key)
            x1, y1 = coord[u]
            x2, y2 = coord[v]
            ax.plot([x1, x2], [y1, y2], color=color[col["transformer"]], lw=2.5, ls=":", alpha=0.95, zorder=3)

    shares = {i: {t: 0.0 for t in transformers} for i in houses}
    for _, val, col in entries:
        for i in col["houses"]:
            shares[i][col["transformer"]] += val
    for i in houses:
        draw_pie(ax, coord[i][0], coord[i][1], shares[i])

    ax.set_title(title)
    handles = [plt.Line2D([0], [0], color=color[t], lw=4, label=f"T{t}") for t in transformers]
    if highlight:
        handles.append(plt.Line2D([0], [0], color="#333333", lw=2.5, ls=":", label="new column"))
    ax.legend(handles=handles, loc="lower left", frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_network_case():
    fig, ax = plt.subplots(figsize=(10, 4.8))
    draw_base(ax)
    ax.set_title("10-house road network for branch-and-price")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "00_network_case.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_dual(filename, snapshot):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].bar([f"H{i}" for i in houses], [snapshot["pi"][i] for i in houses], color="#2766b0")
    axes[0].axhline(0, color="#444444", lw=0.8)
    axes[0].set_title("Cover dual price pi")
    axes[0].set_ylabel("dual value")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].grid(axis="y", alpha=0.25)

    price = snapshot["pricing"]
    axes[1].bar([row["transformer"] for row in price], [row["reduced_cost"] for row in price], color="#cf3e28")
    axes[1].axhline(0, color="#444444", lw=0.8)
    axes[1].set_title("Best pricing reduced cost")
    axes[1].set_ylabel("reduced cost")
    axes[1].grid(axis="y", alpha=0.25)
    for p, row in enumerate(price):
        axes[1].text(p, row["reduced_cost"], row["houses"], ha="center", va="top" if row["reduced_cost"] < 0 else "bottom", fontsize=8)

    fig.suptitle(f"Iteration {snapshot['iteration']} dual and pricing")
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def column_df():
    return pd.DataFrame([
        {
            "column_id": col["id"], "transformer": col["transformer"], "houses": col["houses_text"],
            "load": col["load"], "feeder_length": col["length"], "distance_load": col["distance_load"],
            "max_drop": col["max_drop"], "cost": col["cost"], "feeder_edges": col["feeder_text"],
        }
        for col in columns
    ])


def write_case_data_md():
    rows = [{"house": f"H{i}", "load": load[i], "x": coord[i][0], "y": coord[i][1]} for i in houses]
    road_md = [
        {"from": u, "to": v, "length": length, "kind": kind}
        for u, v, length, kind in road_rows
    ]
    text = f"""# 00 Case data

这个算例把低压配网 planning 简化成“房子通过道路分配给变压器供电”。道路网络有 10 栋房子、3 台变压器，`H2-H4` 是一条捷径边，用来制造一个有教学价值的 LP 分数解。

![network](00_network_case.png)

## Houses

{md_table(rows, ["house", "load", "x", "y"])}

## Roads

{md_table(road_md, ["from", "to", "length", "kind"])}

## Column 的数学含义

一个 column 是某台变压器 $t$ 的一个供电区域 $S$。它不是单个建筑分配变量，而是一整个可行供电方案。

$$
x_{{tp}}=1
$$

表示变压器 $t$ 选择 column $p$，也就是服务该 column 中的房子集合 $S_p$。

可行性条件为：

$$
\\sum_{{i\\in S_p}} d_i \\le C_t
$$

$$
S_p \\text{{ 在道路诱导子图中连通}}
$$

$$
\\max_{{i\\in S_p}} \\Delta V_i(S_p,t) \\le {voltage_drop_max}
$$

这里的电压降是教学用代理量，不是完整潮流：

$$
\\Delta V_i(S,t)=\\alpha\\sum_{{e\\in path(t,i)}} l_e D_e(S)
$$

其中 $D_e(S)$ 是经过道路边 $e$ 的下游负荷，$\\alpha={voltage_drop_alpha}$。

column 成本为：

$$
c_t(S)=5+0.2L_t(S)+0.05\\sum_{{i\\in S}}d_i\\operatorname{{dist}}_{{ti}}
$$

空 column 允许存在，表示该变压器本轮不服务任何房子，成本为 0。
"""
    (OUT_DIR / "00_case_data.md").write_text(text, encoding="utf-8")


def write_column_pool_md(rejected):
    reason_df = pd.DataFrame(rejected, columns=["transformer", "houses", "reason"])
    reason_rows = reason_df.groupby("reason").size().reset_index(name="count").to_dict("records")
    sample = column_df().sort_values(["transformer", "cost"]).groupby("transformer").head(8)
    sample_rows = [
        {
            "column": row.column_id, "t": row.transformer, "houses": row.houses,
            "load": fmt(row.load, 2), "length": fmt(row.feeder_length, 2),
            "drop": fmt(row.max_drop, 4), "cost": fmt(row.cost, 2),
        }
        for row in sample.itertuples(index=False)
    ]
    text = f"""# 01 Column pool

全候选 column 数量为 **{len(columns)}**。真实大规模问题里不可能枚举所有 column；这里枚举只是为了教学、pricing 和最终校验。

## 如何构造一个 column

对每台变压器 $t$，枚举房子集合 $S\\subseteq I$。每个集合依次检查：

1. 容量是否满足 $\\sum_i d_i \\le C_t$。
2. 房子集合是否在道路网络中连通。
3. 从变压器到房子的最短路并集是否满足电压降代理上限。
4. 通过成本公式得到 $c_t(S)$。

pricing problem 也是在这个可行 column 池中寻找 reduced cost 最小的 column：

$$
\\min_{{p\\in P_t}}\\left(c_{{tp}}-\\sum_i\\pi_i a_{{ip}}-\\sigma_t\\right)
$$

## 不可行原因统计

{md_table(reason_rows, ["reason", "count"])}

## 示例 columns

{md_table(sample_rows, ["column", "t", "houses", "load", "length", "drop", "cost"])}
"""
    (OUT_DIR / "01_column_pool.md").write_text(text, encoding="utf-8")


def write_root_md(root):
    iter_rows = [
        {
            "iter": row["iteration"], "obj": fmt(row["objective"], 4), "active": row["active_columns"],
            "new": row["new_columns"] or "none", "integer": row["integer_solution"],
        }
        for row in root["iterations"]
    ]
    pricing_rows = [
        {
            "iter": row["iteration"], "t": row["transformer"], "column": row["column_id"],
            "houses": row["houses"], "cost": fmt(row["cost"], 2),
            "dual_sum": fmt(row["cover_dual_sum"], 3), "sigma": fmt(row["sigma"], 3),
            "rc": fmt(row["reduced_cost"], 4), "add": row["added"],
        }
        for row in root["pricing"]
    ]
    final_snapshot = root["snapshots"][-1]
    dual_rows = [{"item": f"H{i}", "pi": fmt(final_snapshot["pi"][i], 4)} for i in houses]
    dual_rows += [{"item": t, "pi": f"sigma={final_snapshot['sigma'][t]:.4f}"} for t in transformers]
    text = f"""# 02 Root column generation

root 节点先解 LP 松弛。主问题只包含当前 active columns：

$$
\\min \\sum_{{t,p\\in P_t^k}} c_{{tp}}x_{{tp}}
$$

$$
\\sum_{{t,p\\in P_t^k}} a_{{ip}}x_{{tp}}=1,\\quad \\forall i
$$

$$
\\sum_{{p\\in P_t^k}}x_{{tp}}=1,\\quad \\forall t
$$

$$
x_{{tp}}\\ge 0
$$

对偶问题是：

$$
\\max \\sum_i\\pi_i+\\sum_t\\sigma_t
$$

$$
\\sum_i a_{{ip}}\\pi_i+\\sigma_t\\le c_{{tp}},\\quad \\forall t,p\\in P_t^k
$$

$\\pi_i$ 是“覆盖房子 $i$”这条等式约束的对偶价格，$\\sigma_t$ 是“变压器 $t$ 选一个 column”这条等式约束的对偶价格。它们不是实际电价，而是当前 RMP 下的边际价值信号。一个没加入的 column 如果满足：

$$
\\bar c_{{tp}}=c_{{tp}}-\\sum_i\\pi_i a_{{ip}}-\\sigma_t<0
$$

就违反了当前对偶约束，说明它能改进当前 LP，所以要加入 RMP。

## Iterations

{md_table(iter_rows, ["iter", "obj", "active", "new", "integer"])}

## Pricing 记录

{md_table(pricing_rows, ["iter", "t", "column", "houses", "cost", "dual_sum", "sigma", "rc", "add"])}

## 终止轮对偶

{md_table(dual_rows, ["item", "pi"])}

root LP 收敛目标值为 **{root['lower_bound']:.4f}**。由于解中存在分数 column，接下来进入 branch。
"""
    (OUT_DIR / "02_root_column_generation.md").write_text(text, encoding="utf-8")


def write_branching_md(root, left, right, incumbent):
    root_assign = assignment_fraction(root["entries"])
    root_rows = [
        {"house": row.house, "A": fmt(row.A, 3), "B": fmt(row.B, 3), "C": fmt(row.C, 3)}
        for row in root_assign.itertuples(index=False)
    ]
    branch_rows = [
        {
            "node": "left A-H2=1", "LP_bound": fmt(left["lower_bound"], 4),
            "integer": left["integer"], "status": "incumbent" if left["integer"] else "open",
        },
        {
            "node": "right A-H2=0", "LP_bound": fmt(right["lower_bound"], 4),
            "integer": right["integer"], "status": "pruned by bound" if right["lower_bound"] >= incumbent - TOL else "open",
        },
    ]
    text = f"""# 03 Branching

root LP 的目标值是 **{root['lower_bound']:.4f}**，但是它是分数解。下面的表是由 column 解还原出来的建筑分配比例 $z_{{ti}}=\\sum_{{p:i\\in p}}x_{{tp}}$。

{md_table(root_rows, ["house", "A", "B", "C"])}

我们对 `H2 是否由 A 供电` 分支：

左支：

$$
z_{{A,H2}}=1
$$

右支：

$$
z_{{A,H2}}=0
$$

注意分支条件必须同步传给 pricing problem。左支中，pricing 给 A 生成 column 时必须包含 H2，给 B/C 生成 column 时不能包含 H2；右支中，pricing 给 A 生成 column 时不能包含 H2。

每个分支节点还需要一组满足该分支条件的初始可行 columns。这里左支沿用初始分区，右支用 `A -> H1`、`B -> H2,H3,H4,H5`、`C -> H6,H7,H8,H9,H10` 启动。

## Branch nodes

{md_table(branch_rows, ["node", "LP_bound", "integer", "status"])}

左支直接得到整数解，成为 incumbent，目标值 **{incumbent:.4f}**。右支的 LP 下界已经大于 incumbent，因此不需要继续向下 branch。
"""
    (OUT_DIR / "03_branching.md").write_text(text, encoding="utf-8")


def write_final_md(final_entries, validation_obj, root):
    rows = [
        {
            "t": col["transformer"], "column": col["id"], "houses": col["houses_text"],
            "load": fmt(col["load"], 2), "length": fmt(col["length"], 2),
            "drop": fmt(col["max_drop"], 4), "cost": fmt(col["cost"], 2),
        }
        for _, _, col in final_entries
    ]
    total = sum(col["cost"] for _, _, col in final_entries)
    text = f"""# 04 Final solution

最终整数规划方案如下。

{md_table(rows, ["t", "column", "houses", "load", "length", "drop", "cost"])}

总成本：

$$
{total:.4f}
$$

全列 MIP 校验目标值：

$$
{validation_obj:.4f}
$$

两者一致，说明 branch-and-price 得到的整数解与枚举全部 columns 后直接求 MIP 的结果一致。本算例存在多个并列最优解；这里报告与初始分区一致、也更容易从图上阅读的一组 incumbent。

## 学习要点

1. column 是一整个变压器供电区域，不是单个 $y_{{it}}$。
2. RMP 的对偶变量 $\\pi_i$ 告诉 pricing：当前哪些房子“值得覆盖”。
3. reduced cost 小于 0 表示新 column 能改善当前 LP。
4. root LP 目标值 **{root['lower_bound']:.4f}** 是整数问题的下界，但分数解不能直接作为规划方案。
5. branch 条件要能被 pricing 理解，否则子节点无法正确生成 columns。

![final](07_final_assignment.png)
"""
    (OUT_DIR / "04_final_solution.md").write_text(text, encoding="utf-8")


def write_excel(root, left, right, final_entries):
    house_df = pd.DataFrame([{"house": f"H{i}", "load": load[i], "x": coord[i][0], "y": coord[i][1]} for i in houses])
    road_df = pd.DataFrame(road_rows, columns=["from", "to", "length", "kind"])
    all_iter = pd.DataFrame(root["iterations"] + left["iterations"] + right["iterations"])
    all_duals = pd.DataFrame(root["duals"] + left["duals"] + right["duals"])
    all_pricing = pd.DataFrame(root["pricing"] + left["pricing"] + right["pricing"])
    branch_df = pd.DataFrame([
        ("root", "none", root["lower_bound"], pd.NA, root["integer"], len(root["active"])),
        ("left", "A-H2=1", left["lower_bound"], left["lower_bound"], left["integer"], len(left["active"])),
        ("right", "A-H2=0", right["lower_bound"], pd.NA, right["integer"], len(right["active"])),
    ], columns=["node", "branch_rule", "lower_bound", "upper_bound", "integer", "active_columns"])
    final_df = pd.DataFrame([
        {
            "transformer": col["transformer"], "column_id": col["id"], "houses": col["houses_text"],
            "load": col["load"], "feeder_length": col["length"], "max_drop": col["max_drop"], "cost": col["cost"],
        }
        for _, _, col in final_entries
    ])
    with pd.ExcelWriter(OUTPUT_XLSX) as writer:
        house_df.to_excel(writer, sheet_name="houses", index=False)
        road_df.to_excel(writer, sheet_name="roads", index=False)
        column_df().to_excel(writer, sheet_name="all_columns", index=False)
        all_iter.to_excel(writer, sheet_name="cg_iterations", index=False)
        all_duals.to_excel(writer, sheet_name="duals", index=False)
        all_pricing.to_excel(writer, sheet_name="pricing", index=False)
        branch_df.to_excel(writer, sheet_name="branch_nodes", index=False)
        final_df.to_excel(writer, sheet_name="final_solution", index=False)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    active0 = {id_map[(t, initial_sets[t])] for t in transformers}
    root = run_column_generation("root", {}, active0)
    if any(row["reduced_cost"] < -TOL for row in root["snapshots"][-1]["pricing"]):
        raise RuntimeError("root pricing stopped with a negative reduced cost column")
    root["model"].write(str(OUT_DIR / "root_final_rmp.lp"))

    left_active0 = root["active"] | seed_active(branch_seed_sets["left_A_H2_eq_1"])
    left = run_column_generation("left_A_H2_eq_1", {("A", 2): 1}, left_active0)
    incumbent = left["lower_bound"]
    right_active0 = root["active"] | seed_active(branch_seed_sets["right_A_H2_eq_0"])
    right = run_column_generation("right_A_H2_eq_0", {("A", 2): 0}, right_active0)

    full_mip, _, _, full_entries = solve_full_validation(binary=True)
    full_mip.write(str(OUT_DIR / "full_column_validation.lp"))
    if abs(full_mip.ObjVal - incumbent) > 1e-6:
        raise RuntimeError("branch-and-price incumbent does not match full-column MIP")

    final_entries = [(id_map[(t, initial_sets[t])], 1.0, columns[id_map[(t, initial_sets[t])]]) for t in transformers]
    if abs(sum(col["cost"] for _, _, col in final_entries) - incumbent) > 1e-6:
        raise RuntimeError("canonical final solution is not an incumbent")

    plot_network_case()
    plot_solution("01_initial_partition.png", "Initial feasible columns", [(k, 1.0, columns[k]) for k in active0])
    for snap in root["snapshots"]:
        plot_solution(f"02_root_iter_{snap['iteration']:02d}.png", f"Root iteration {snap['iteration']} solution and new columns", snap["entries"], snap["added"])
        plot_dual(f"03_dual_iter_{snap['iteration']:02d}.png", snap)
    plot_solution("04_root_fractional_solution.png", "Root final fractional LP solution", root["entries"])
    plot_solution("05_branch_left.png", "Branch left: A must serve H2", left["entries"])
    plot_solution("06_branch_right.png", "Branch right: A cannot serve H2", right["entries"])
    plot_solution("07_final_assignment.png", "Final integer assignment", final_entries)

    write_case_data_md()
    write_column_pool_md(rejected_columns)
    write_root_md(root)
    write_branching_md(root, left, right, incumbent)
    write_final_md(final_entries, full_mip.ObjVal, root)
    write_excel(root, left, right, final_entries)

    print("Branch-and-price teaching example")
    print(f"Columns: {len(columns)}")
    print(f"Root LP bound: {root['lower_bound']:.4f}")
    print(f"Left incumbent: {incumbent:.4f}")
    print(f"Right LP bound: {right['lower_bound']:.4f}")
    print(f"Full-column MIP: {full_mip.ObjVal:.4f}")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
