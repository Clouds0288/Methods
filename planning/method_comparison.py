"""汇总比较 MISOCP、Benders、有限场景 CCG 和 dual CCG 的规划结果。"""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from network.case33 import ROOT_DIR  # noqa: E402


PLANNING_DIR = ROOT_DIR / "results" / "planning"
OUT_DIR = PLANNING_DIR / "comparison"
OUTPUT_XLSX = OUT_DIR / "method_comparison.xlsx"

BENDERS_XLSX = PLANNING_DIR / "benders" / "benders_standard_storage_ieee33_summary.xlsx"
CCG_XLSX = PLANNING_DIR / "ccg" / "ccg_storage_ieee33_summary.xlsx"
CCG_DUAL_XLSX = PLANNING_DIR / "ccg_dual" / "ccg_dual_storage_ieee33_summary.xlsx"
SMALL_MISOCP_XLSX = PLANNING_DIR / "misocp" / "planning_comparison.xlsx"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_summary(path, sheet_name, key_col, value_col):
    df = pd.read_excel(path, sheet_name=sheet_name)
    df = df[[key_col, value_col]].dropna(subset=[key_col])
    return dict(zip(df[key_col], df[value_col]))


def read_embedded_history(path):
    raw = pd.read_excel(path, sheet_name="summary_progress")
    header_row = raw.index[raw.iloc[:, 0] == "iteration"][0]
    history = raw.iloc[header_row + 1:].dropna(how="all").copy()
    history.columns = raw.iloc[header_row]
    return history.dropna(subset=["iteration"]).reset_index(drop=True)


def read_storage_plan(path, sheet_name, method):
    plan = pd.read_excel(path, sheet_name=sheet_name)
    plan.insert(0, "method", method)
    return plan


def method_rows():
    benders = read_summary(BENDERS_XLSX, "summary_progress", "item", "value")
    ccg = read_summary(CCG_XLSX, "summary", "item", "value")
    dual = read_summary(CCG_DUAL_XLSX, "summary", "item", "value")
    small = read_summary(SMALL_MISOCP_XLSX, "summary", "metric", "storage_misocp")
    return pd.DataFrame([
        ("MISOCP", "IEEE33", "DistFlow-SOCP", "deterministic", benders["monolithic_objective"], benders["investment_cost"], benders["operation_cost"], benders["cycle_cost"], 1, 0.0, benders["built_buses"], None, None, "monolithic solve embedded in benders script"),
        ("Benders", "IEEE33", "DistFlow-SOCP", "deterministic", benders["objective"], benders["investment_cost"], benders["operation_cost"], benders["cycle_cost"], benders["iterations"], benders["benders_minus_monolithic"], benders["built_buses"], None, None, "same model as MISOCP, decomposed by capacity cuts"),
        ("CCG", "IEEE33", "DistFlow-SOCP", "finite scenarios", ccg["objective"], ccg["investment_cost"], ccg["worst_energy_operation_cost"], ccg["worst_cycle_cost"], ccg["iterations"], 0.0, ccg["built_buses"], ccg["worst_scenario"], None, "robust over explicit scenario pool"),
        ("CCG-dual", "IEEE33", "aggregate active-power LP", "budgeted binary uncertainty", dual["objective"], dual["investment_cost"], dual["worst_energy_operation_cost"], dual["worst_cycle_cost"], dual["iterations"], dual["final_gap"], dual["built_buses"], None, f"load {dual['final_load_hours']}; dg {dual['final_dg_hours']}", "teaching dual oracle, not network-equivalent to DistFlow-SOCP"),
        ("MISOCP-6bus", "case6", "DistFlow-SOCP", "deterministic", small["objective"], small["investment_cost"], small["operation_cost"], small["cycle_cost"], 1, 0.0, 3, None, None, "small standalone script; kept out of IEEE33 direct charts"),
    ], columns=["method", "case", "recourse_model", "uncertainty", "objective", "investment_cost", "energy_operation_cost", "cycle_cost", "iterations", "final_gap", "built_buses", "worst_scenario", "worst_budget_hours", "note"])


def convergence_table():
    b = read_embedded_history(BENDERS_XLSX)
    b = b[["iteration", "LB", "UB", "gap"]].assign(method="Benders")
    c = pd.read_excel(CCG_XLSX, sheet_name="ccg_progress")
    c = c[["iteration", "LB", "UB", "gap"]].assign(method="CCG")
    d = pd.read_excel(CCG_DUAL_XLSX, sheet_name="ccg_dual_progress")
    d = d[["iteration", "LB", "UB", "gap"]].assign(method="CCG-dual")
    return pd.concat([b, c, d], ignore_index=True)


def apple_to_apple_table(methods):
    ieee = methods.loc[methods["case"] == "IEEE33"].copy()
    misocp_obj = ieee.loc[ieee["method"] == "MISOCP", "objective"].iloc[0]
    ieee["objective_minus_misocp"] = ieee["objective"] - misocp_obj
    ieee["relative_minus_misocp"] = ieee["objective_minus_misocp"] / misocp_obj
    return ieee


def plot_objective(methods):
    data = methods.loc[methods["case"] == "IEEE33"].copy()
    data["run_cost"] = data["energy_operation_cost"] + data["cycle_cost"]
    x = range(len(data))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, data["investment_cost"], color="#2766b0", label="Investment")
    ax.bar(x, data["run_cost"], bottom=data["investment_cost"], color="#ef9b20", label="Operation + cycle")
    ax.set_xticks(list(x))
    ax.set_xticklabels(data["method"])
    ax.set_ylabel("Objective components")
    ax.set_title("Planning Method Objective Breakdown")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "method_01_objective_breakdown.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_convergence(convergence):
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = {"Benders": "#2766b0", "CCG": "#cf3e28", "CCG-dual": "#4f9b58"}
    for method, part in convergence.groupby("method"):
        part = part.sort_values("iteration")
        ax.plot(part["iteration"], part["LB"], marker="o", color=colors[method], label=f"{method} LB")
        ax.plot(part["iteration"], part["UB"], marker="s", ls="--", color=colors[method], label=f"{method} UB")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Objective bound")
    ax.set_title("Decomposition Convergence")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "method_02_convergence.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_capacity(storage_plans):
    built = storage_plans.loc[(storage_plans["build"] == 1) & (storage_plans["method"] != "MISOCP-6bus")].copy()
    labels = [f"{m}\nBus {int(b)}" for m, b in zip(built["method"], built["bus"])]
    x = range(len(built))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - 0.18 for i in x], built["p_cap_mw"], width=0.36, color="#2766b0", label="Power capacity")
    ax.bar([i + 0.18 for i in x], built["e_cap_mwh"], width=0.36, color="#ef9b20", label="Energy capacity")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("MW / MWh")
    ax.set_title("Built Storage Capacity by Method")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "method_03_storage_capacity.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


methods = method_rows()
convergence = convergence_table()
apple_to_apple = apple_to_apple_table(methods)
storage_plans = pd.concat([
    read_storage_plan(BENDERS_XLSX, "storage_plan", "MISOCP/Benders"),
    read_storage_plan(CCG_XLSX, "storage_plan", "CCG"),
    read_storage_plan(CCG_DUAL_XLSX, "storage_plan", "CCG-dual"),
    read_storage_plan(SMALL_MISOCP_XLSX, "storage_plan", "MISOCP-6bus"),
], ignore_index=True)

with pd.ExcelWriter(OUTPUT_XLSX) as writer:
    methods.to_excel(writer, sheet_name="method_summary", index=False)
    apple_to_apple.to_excel(writer, sheet_name="ieee33_comparison", index=False)
    convergence.to_excel(writer, sheet_name="convergence", index=False)
    storage_plans.to_excel(writer, sheet_name="storage_plan", index=False)

plot_objective(methods)
plot_convergence(convergence)
plot_capacity(storage_plans)

print("Planning method comparison")
print(methods.to_string(index=False))
print()
print("IEEE33 objective differences vs monolithic MISOCP")
print(apple_to_apple[["method", "objective", "objective_minus_misocp", "relative_minus_misocp", "note"]].to_string(index=False))
print()
print(f"Excel: {OUTPUT_XLSX}")
print(f"01 Objective plot: {OUT_DIR / 'method_01_objective_breakdown.png'}")
print(f"02 Convergence plot: {OUT_DIR / 'method_02_convergence.png'}")
print(f"03 Capacity plot: {OUT_DIR / 'method_03_storage_capacity.png'}")
