import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from network.case6 import OUT_DIR, OUTPUT_XLSX, V_min, hours, buses, bus_df, branch_df, p_load_mw, q_load_mvar, total_load


grid_price = dict(zip(hours, [45] * 7 + [70] * 5 + [90] * 5 + [120] * 4 + [75] * 3))
dg_cost = 85.0


def write_sheets(sheets):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mode = "a" if OUTPUT_XLSX.exists() else "w"
    kwargs = {"engine": "openpyxl", "mode": mode}
    if mode == "a":
        kwargs["if_sheet_exists"] = "replace"
    with pd.ExcelWriter(OUTPUT_XLSX, **kwargs) as writer:
        for sheet, df, index in sheets:
            df.to_excel(writer, sheet_name=sheet, index=index)


def move_sheet_to_front(sheet_name):
    from openpyxl import load_workbook

    wb = load_workbook(OUTPUT_XLSX)
    ws = wb[sheet_name]
    wb.move_sheet(ws, offset=-wb.index(ws))  # 把模型对比表移动到第一个 sheet
    wb.save(OUTPUT_XLSX)


def comparison_tables():
    dc = pd.read_excel(OUTPUT_XLSX, sheet_name="dc_dispatch", index_col="hour")
    sdp = pd.read_excel(OUTPUT_XLSX, sheet_name="sdp_dispatch", index_col="hour")
    lin = pd.read_excel(OUTPUT_XLSX, sheet_name="lin_dispatch", index_col="hour")
    dist = pd.read_excel(OUTPUT_XLSX, sheet_name="dist_dispatch", index_col="hour")
    ac = pd.read_excel(OUTPUT_XLSX, sheet_name="ac_dispatch", index_col="hour")
    dc_branch = pd.read_excel(OUTPUT_XLSX, sheet_name="dc_branch_flow")
    sdp_branch = pd.read_excel(OUTPUT_XLSX, sheet_name="sdp_branch_flow")
    sdp_rank = pd.read_excel(OUTPUT_XLSX, sheet_name="sdp_rank")
    lin_branch = pd.read_excel(OUTPUT_XLSX, sheet_name="lin_branch_flow")
    dist_branch = pd.read_excel(OUTPUT_XLSX, sheet_name="dist_branch_flow")
    ac_branch = pd.read_excel(OUTPUT_XLSX, sheet_name="ac_branch_flow")

    price = pd.Series(grid_price, name="grid_price")
    dc_obj = (price * dc["p_grid_mw"] + dg_cost * dc["p_dg_mw"]).sum()
    sdp_obj = (price * sdp["p_grid_mw"] + dg_cost * sdp["p_dg_mw"]).sum()
    lin_obj = (price * lin["p_grid_mw"] + dg_cost * lin["p_dg_mw"]).sum()
    dist_obj = (price * dist["p_grid_mw"] + dg_cost * dist["p_dg_mw"]).sum()
    ac_obj = (price * ac["p_grid_mw"] + dg_cost * ac["p_dg_mw"]).sum()

    summary = pd.DataFrame(
        [   ("objective", ac_obj, dc_obj, sdp_obj, dist_obj, lin_obj),
            ("total_grid_mwh", ac["p_grid_mw"].sum(), dc["p_grid_mw"].sum(), sdp["p_grid_mw"].sum(), dist["p_grid_mw"].sum(), lin["p_grid_mw"].sum()),
            ("total_dg_mwh", ac["p_dg_mw"].sum(), dc["p_dg_mw"].sum(), sdp["p_dg_mw"].sum(), dist["p_dg_mw"].sum(), lin["p_dg_mw"].sum()),
            ("total_q_grid_mvarh", ac["q_grid_mvar"].sum(), np.nan, sdp["q_grid_mvar"].sum(), dist["q_grid_mvar"].sum(), lin["q_grid_mvar"].sum()),
            ("min_voltage_pu", ac["v_min_pu"].min(), dc["v_min_pu"].min(), sdp["v_min_pu"].min(), dist["v_min_pu"].min(), lin["v_min_pu"].min()),
            ("max_branch_loading_pct", ac_branch["loading_pct"].max(), dc_branch["loading_pct"].max(), sdp_branch["loading_pct"].max(), dist_branch["loading_pct"].max(), lin_branch["loading_pct"].max()),
            ("total_active_loss_mwh", ac_branch["p_loss_mw"].sum(), 0.0, sdp_branch["p_loss_mw"].sum(), dist_branch["p_loss_mw"].sum(), 0.0),
            ("total_reactive_loss_mvarh", ac_branch["q_loss_mvar"].sum(), np.nan, sdp_branch["q_loss_mvar"].sum(), dist_branch["q_loss_mvar"].sum(), 0.0),
            ("max_sdp_lambda2_over_lambda1", 0.0, np.nan, sdp_rank["lambda2_over_lambda1"].max(), np.nan, np.nan),
            ("max_distflow_soc_gap", 0.0, np.nan, np.nan, dist_branch["soc_gap"].abs().max(), np.nan),],
        columns=["metric", "ac_opf", "dcflow", "sdp_relaxation", "distflow_socp", "lindistflow"],)
    summary["dc_minus_ac"] = summary["dcflow"] - summary["ac_opf"]
    summary["sdp_minus_ac"] = summary["sdp_relaxation"] - summary["ac_opf"]
    summary["dist_minus_ac"] = summary["distflow_socp"] - summary["ac_opf"]
    summary["lin_minus_ac"] = summary["lindistflow"] - summary["ac_opf"]

    hourly = pd.DataFrame(
        {
            "load_mw": total_load["p_mw"],
            "load_mvar": total_load["q_mvar"],
            "p_grid_ac_mw": ac["p_grid_mw"],
            "p_grid_dc_mw": dc["p_grid_mw"],
            "p_grid_sdp_mw": sdp["p_grid_mw"],
            "p_grid_dist_mw": dist["p_grid_mw"],
            "p_grid_lin_mw": lin["p_grid_mw"],
            "p_grid_dc_minus_ac_mw": dc["p_grid_mw"] - ac["p_grid_mw"],
            "p_grid_sdp_minus_ac_mw": sdp["p_grid_mw"] - ac["p_grid_mw"],
            "p_grid_dist_minus_ac_mw": dist["p_grid_mw"] - ac["p_grid_mw"],
            "p_grid_lin_minus_ac_mw": lin["p_grid_mw"] - ac["p_grid_mw"],
            "q_grid_ac_mvar": ac["q_grid_mvar"],
            "q_grid_sdp_mvar": sdp["q_grid_mvar"],
            "q_grid_dist_mvar": dist["q_grid_mvar"],
            "q_grid_lin_mvar": lin["q_grid_mvar"],
            "q_grid_sdp_minus_ac_mvar": sdp["q_grid_mvar"] - ac["q_grid_mvar"],
            "q_grid_dist_minus_ac_mvar": dist["q_grid_mvar"] - ac["q_grid_mvar"],
            "q_grid_lin_minus_ac_mvar": lin["q_grid_mvar"] - ac["q_grid_mvar"],
            "p_dg_ac_mw": ac["p_dg_mw"],
            "p_dg_dc_mw": dc["p_dg_mw"],
            "p_dg_sdp_mw": sdp["p_dg_mw"],
            "p_dg_dist_mw": dist["p_dg_mw"],
            "p_dg_lin_mw": lin["p_dg_mw"],
            "v_min_ac_pu": ac["v_min_pu"],
            "v_min_dc_pu": dc["v_min_pu"],
            "v_min_sdp_pu": sdp["v_min_pu"],
            "v_min_dist_pu": dist["v_min_pu"],
            "v_min_lin_pu": lin["v_min_pu"],
            "v_min_dc_minus_ac_pu": dc["v_min_pu"] - ac["v_min_pu"],
            "v_min_sdp_minus_ac_pu": sdp["v_min_pu"] - ac["v_min_pu"],
            "v_min_dist_minus_ac_pu": dist["v_min_pu"] - ac["v_min_pu"],
            "v_min_lin_minus_ac_pu": lin["v_min_pu"] - ac["v_min_pu"],
        }
    )
    hourly.index.name = "hour"
    return summary, hourly


def plot_results():
    dc = pd.read_excel(OUTPUT_XLSX, sheet_name="dc_dispatch", index_col="hour")
    sdp = pd.read_excel(OUTPUT_XLSX, sheet_name="sdp_dispatch", index_col="hour")
    lin = pd.read_excel(OUTPUT_XLSX, sheet_name="lin_dispatch", index_col="hour")
    dist = pd.read_excel(OUTPUT_XLSX, sheet_name="dist_dispatch", index_col="hour")
    ac = pd.read_excel(OUTPUT_XLSX, sheet_name="ac_dispatch", index_col="hour")
    lin_v = pd.read_excel(OUTPUT_XLSX, sheet_name="lin_voltage", index_col="hour")
    dist_v = pd.read_excel(OUTPUT_XLSX, sheet_name="dist_voltage", index_col="hour")
    ac_v = pd.read_excel(OUTPUT_XLSX, sheet_name="ac_voltage", index_col="hour")
    lin_v.columns = [int(c) for c in lin_v.columns]
    dist_v.columns = [int(c) for c in dist_v.columns]
    ac_v.columns = [int(c) for c in ac_v.columns]

    pos = {i: (i, 0) for i in buses}
    fig, ax = plt.subplots(figsize=(8, 2.5), dpi=120)
    for br, f, t, *_ in branch_df.itertuples(index=False, name=None):
        ax.plot([pos[f][0], pos[t][0]], [0, 0], color="black", lw=2)
        ax.text((f + t) / 2, 0.08, br, ha="center", fontsize=9)
    for b, kind in bus_df.itertuples(index=False, name=None):
        ax.scatter(*pos[b], s=600, color="#87ceeb" if kind == "slack" else "#ffd166", edgecolor="black", zorder=3)
        ax.text(*pos[b], str(b), ha="center", va="center", weight="bold")
    ax.set_title("6-bus radial feeder")
    ax.set_xlim(0.5, 6.5)
    ax.set_ylim(-0.4, 0.3)
    ax.axis("off")
    fig.savefig(OUT_DIR / "network.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), dpi=120, sharex=True)
    p_load_mw.plot(ax=axes[0], marker="o", ms=3, lw=1.4)
    q_load_mvar.plot(ax=axes[1], marker="o", ms=3, lw=1.4)
    total_load["p_mw"].plot(ax=axes[0], color="black", lw=2.4, label="Total")
    total_load["q_mvar"].plot(ax=axes[1], color="black", lw=2.4, label="Total")
    axes[0].set_title("Active load")
    axes[1].set_title("Reactive load")
    axes[0].set_ylabel("MW")
    axes[1].set_ylabel("MVAr")
    axes[1].set_xlabel("Hour")
    axes[1].set_xticks(list(hours))
    for ax in axes:
        ax.grid(ls="--", alpha=0.35)
        ax.legend(title="Bus", ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "load_profiles.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), dpi=120, sharex=True)
    axes[0].plot(hours, total_load["p_mw"], color="black", lw=2.4, label="Load")
    axes[0].plot(hours, ac["p_grid_mw"], marker="^", ms=3, label="Grid AC OPF")
    axes[0].plot(hours, dc["p_grid_mw"], marker="x", ms=3, label="Grid DC")
    axes[0].plot(hours, sdp["p_grid_mw"], marker="d", ms=3, label="Grid SDP")
    axes[0].plot(hours, dist["p_grid_mw"], marker="s", ms=3, label="Grid DistFlow")
    axes[0].plot(hours, lin["p_grid_mw"], marker="o", ms=3, label="Grid LinDistFlow")
    axes[0].plot(hours, ac["p_dg_mw"], ls="-.", label="DG AC OPF")
    axes[0].plot(hours, dc["p_dg_mw"], ls="-", lw=1, label="DG DC")
    axes[0].plot(hours, sdp["p_dg_mw"], ls=(0, (3, 1, 1, 1)), label="DG SDP")
    axes[0].plot(hours, dist["p_dg_mw"], ls=":", label="DG DistFlow")
    axes[0].plot(hours, lin["p_dg_mw"], ls="--", label="DG LinDistFlow")
    axes[0].set_ylabel("MW")
    axes[0].legend(frameon=False, ncol=3)
    axes[1].plot(hours, ac["q_grid_mvar"], marker="^", ms=3, label="Grid Q AC OPF")
    axes[1].plot(hours, sdp["q_grid_mvar"], marker="d", ms=3, label="Grid Q SDP")
    axes[1].plot(hours, dist["q_grid_mvar"], marker="s", ms=3, label="Grid Q DistFlow")
    axes[1].plot(hours, lin["q_grid_mvar"], marker="o", ms=3, label="Grid Q LinDistFlow")
    axes[1].set_ylabel("MVAr")
    axes[1].legend(frameon=False, ncol=3)
    axes[2].plot(hours, ac["v_min_pu"], marker="^", ms=3, label="Min V AC OPF")
    axes[2].plot(hours, dc["v_min_pu"], marker="x", ms=3, label="V DC flat assumption")
    axes[2].plot(hours, sdp["v_min_pu"], marker="d", ms=3, label="Min V SDP")
    axes[2].plot(hours, dist["v_min_pu"], marker="s", ms=3, label="Min V DistFlow")
    axes[2].plot(hours, lin["v_min_pu"], marker="o", ms=3, label="Min V LinDistFlow")
    axes[2].axhline(V_min, color="red", ls="--", lw=1)
    axes[2].set_ylabel("Voltage / pu")
    axes[2].set_xlabel("Hour")
    axes[2].set_xticks(list(hours))
    axes[2].legend(frameon=False, ncol=3)
    for ax in axes:
        ax.grid(ls="--", alpha=0.35)
    fig.suptitle("AC OPF vs DC vs SDP vs DistFlow SOCP vs LinDistFlow", y=0.99)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "opf_comparison.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    summary, hourly = comparison_tables()
    write_sheets([("summary", summary, False), ("hourly_comparison", hourly, True)])
    move_sheet_to_front("summary")
    plot_results()

    print("Model comparison")
    print(summary.round(6).to_string(index=False))
    print()
    print("Largest hourly active-grid differences vs AC OPF")
    err = hourly[["p_grid_dc_minus_ac_mw", "p_grid_sdp_minus_ac_mw", "p_grid_dist_minus_ac_mw", "p_grid_lin_minus_ac_mw"]].abs().max(axis=1)
    print(hourly.reindex(err.sort_values(ascending=False).index).head(8).round(6).to_string())
