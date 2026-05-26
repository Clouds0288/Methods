"""绘制 IEEE 33 网络概况图：拓扑、负荷、电压、电流放在同一张大图里。"""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))  # 允许直接运行脚本时导入项目包

from network.case33 import (  # noqa: E402
    ROOT_DIR, S_base, V_base_kv, buses, branch_df,
    p_load_mw, dg_buses,
)


OUT_DIR = ROOT_DIR / "results" / "network"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PLANNING_RESULT = ROOT_DIR / "results" / "planning" / "benders_standard_storage_ieee33_summary.xlsx"


def radial_layout():
    child_buses = {b: sorted(branch_df.loc[branch_df["from_bus"] == b, "to_bus"].tolist()) for b in buses}
    x_pos, y_pos = {}, {}
    leaf_index = 0

    def visit(bus, depth):
        nonlocal leaf_index
        x_pos[bus] = depth
        if len(child_buses[bus]) == 0:
            y_pos[bus] = leaf_index
            leaf_index += 1
        else:
            for child in child_buses[bus]:
                visit(child, depth + 1)
            y_pos[bus] = sum(y_pos[child] for child in child_buses[bus]) / len(child_buses[bus])

    visit(1, 0)
    return x_pos, y_pos


def plot_topology(ax, storage_buses):
    x_pos, y_pos = radial_layout()
    for _, f, t, *_ in branch_df.itertuples(index=False, name=None):
        ax.plot([x_pos[f], x_pos[t]], [y_pos[f], y_pos[t]], color="#7f7f7f", linewidth=1.4, zorder=1)  # 配电线路
    other_buses = [b for b in buses if b not in [1] + dg_buses + storage_buses]
    ax.scatter([x_pos[b] for b in other_buses], [y_pos[b] for b in other_buses], s=42, color="#b9c7d8", edgecolor="#455a64", linewidth=0.6, zorder=2)
    ax.scatter([x_pos[1]], [y_pos[1]], s=220, marker="*", color="#d73027", edgecolor="black", linewidth=0.8, zorder=5)  # 平衡节点
    ax.scatter([x_pos[1] + 0.22], [y_pos[1] + 0.35], s=120, marker="s", color="#1f1f1f", edgecolor="white", linewidth=0.8, zorder=6)  # 变压器位置
    ax.scatter([x_pos[b] for b in dg_buses], [y_pos[b] for b in dg_buses], s=110, marker="^", color="#2ca25f", edgecolor="black", linewidth=0.7, zorder=4)  # 光伏/DG 节点
    ax.scatter([x_pos[b] for b in storage_buses], [y_pos[b] for b in storage_buses], s=120, marker="D", color="#f28e2b", edgecolor="black", linewidth=0.7, zorder=4)  # 储能节点
    for b in buses:
        ax.text(x_pos[b], y_pos[b] + 0.18, str(b), ha="center", va="bottom", fontsize=8)
    handles = [
        Line2D([0], [0], marker="*", color="w", label="Slack bus", markerfacecolor="#d73027", markeredgecolor="black", markersize=14),
        Line2D([0], [0], marker="s", color="w", label="Transformer", markerfacecolor="#1f1f1f", markeredgecolor="black", markersize=9),
        Line2D([0], [0], marker="^", color="w", label="PV/DG", markerfacecolor="#2ca25f", markeredgecolor="black", markersize=10),
        Line2D([0], [0], marker="D", color="w", label="Storage", markerfacecolor="#f28e2b", markeredgecolor="black", markersize=10),
        Line2D([0], [0], color="#7f7f7f", label="Line", linewidth=1.8),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=9, frameon=True)
    ax.set_title("IEEE 33 topology and device locations")
    ax.set_xlabel("Feeder depth")
    ax.set_ylabel("Radial branch order")
    ax.grid(True, alpha=0.18)


def plot_bus_timeseries(ax, table, title, ylabel):
    norm = plt.Normalize(min(buses), max(buses))
    cmap = plt.get_cmap("viridis")
    for b in buses:
        linewidth = 1.8 if b in [1, 2, 3, 4, 18, 33] else 0.8
        alpha = 0.95 if b in [1, 2, 3, 4, 18, 33] else 0.45
        ax.plot(table.index, table[b], color=cmap(norm(b)), linewidth=linewidth, alpha=alpha)
    ax.set_title(title)
    ax.set_xlabel("Hour")
    ax.set_ylabel(ylabel)
    ax.set_xticks(list(range(0, 24, 2)))
    ax.grid(True, alpha=0.25)
    return plt.cm.ScalarMappable(norm=norm, cmap=cmap)


def plot_case33_overview():
    storage_plan = pd.read_excel(PLANNING_RESULT, sheet_name="storage_plan")
    node_balance = pd.read_excel(PLANNING_RESULT, sheet_name="node_balance")
    storage_buses = storage_plan.loc[storage_plan["build"] == 1, "bus"].astype(int).tolist()

    load = p_load_mw.reindex(columns=buses, fill_value=0.0)  # 平衡节点无负荷，显式补 0
    voltage = node_balance.pivot(index="hour", columns="bus", values="v_pu").reindex(columns=buses)
    current_source = node_balance.copy()
    current_source["current_ka"] = np.sqrt(current_source["ell_in_pu"]) * S_base / (np.sqrt(3) * V_base_kv)  # DistFlow 电流平方变量换算成三相线电流
    current = current_source.pivot(index="hour", columns="bus", values="current_ka").reindex(columns=buses)

    fig, axes = plt.subplots(2, 2, figsize=(20, 13), constrained_layout=True)
    fig.suptitle("IEEE 33 network overview: topology, load, voltage, current", fontsize=18)
    plot_topology(axes[0, 0], storage_buses)
    sm = plot_bus_timeseries(axes[0, 1], load, "All-bus active load profiles", "MW")
    plot_bus_timeseries(axes[1, 0], voltage, "All-bus voltage profiles", "p.u.")
    plot_bus_timeseries(axes[1, 1], current, "All-bus upstream current profiles", "kA")
    cbar = fig.colorbar(sm, ax=axes[:, 1], shrink=0.86, pad=0.01)
    cbar.set_label("Bus number")
    out_file = OUT_DIR / "ieee33_network_overview.png"
    fig.savefig(out_file, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(out_file)


if __name__ == "__main__":
    plot_case33_overview()
