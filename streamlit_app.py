import streamlit as st
import pandas as pd
from pathlib import Path

from allocator import (
    load_hugim,
    load_preferences,
    run_allocation,
    save_assignments,
    save_unassigned,
    save_stats,
    calculate_and_store_weekly_scores,
    OUTPUT_ASSIGNMENTS_FILE as ALLOCATOR_OUTPUT_ASSIGNMENTS_FILE,
    OUTPUT_STATS_FILE as ALLOCATOR_OUTPUT_STATS_FILE,
    OUTPUT_UNASSIGNED_FILE as ALLOCATOR_OUTPUT_UNASSIGNED_FILE,
)

from data_helpers import (
    find_missing,
    show_uploaded,
    to_csv_download,
    enforce_minimums_cancel_and_reallocate
)

st.set_page_config(
    page_title="CYJ Hugim Allocator",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("---")
st.markdown("Built with ❤️ for Camp Administrators | [Support](mailto:dorposner@gmail.com)")

# ---- Output paths for this app session ----
OUTPUT_ASSIGNMENTS_FILE = Path("assignments_output.csv")
OUTPUT_STATS_FILE = Path("stats_output.csv")
OUTPUT_UNASSIGNED_FILE = Path("unassigned_campers_output.csv")

def find_best_column_match(columns, target_names):
    """
    Find the best matching column from a list of target names.
    Returns the index of the best match, or 0 if no match found.
    """
    columns_lower = [col.lower().strip() for col in columns]
    
    for target in target_names:
        target_lower = target.lower().strip()
        # Exact match
        if target_lower in columns_lower:
            return columns_lower.index(target_lower)
        # Partial match (target contained in column name)
        for i, col in enumerate(columns_lower):
            if target_lower in col:
                return i
    
    return 0  # Default to first column if no match

def main():
    if "allocation_run" not in st.session_state:
        st.session_state["allocation_run"] = False
    if "last_upload_key" not in st.session_state:
        st.session_state["last_upload_key"] = ""

    st.title("CYJ Hugim Allocation Web App")
    with st.expander("📄 Click here for instructions (ignore column names if using your own):"):
        st.markdown("""
        For `hugim.csv`, you must have:
        - Activity column (name of hug)
        - Capacity column (how many can join)
        - Minimum column (how few must join) 
        - Columns indicating in which periods (Aleph, Beth, Gimmel...) each hug is offered (should be 1/0 or TRUE/FALSE)

        For `preferences.csv`, you must have:
        - Unique camper ID column
        - Preference columns for each period (such as Aleph_1, Aleph_2, ..., Gimmel_5)
        """)

    st.write("Upload your CSV files below. You can preview and edit before running allocation:")

    hugim_file = st.file_uploader("Upload hugim.csv", type=["csv"])
    prefs_file = st.file_uploader("Upload preferences.csv", type=["csv"])

    hugim_df = prefs_df = None

    if hugim_file:
        hugim_df = show_uploaded(st, "hugim.csv", hugim_file)
        st.subheader("✏️ Edit hugim.csv")
        hugim_df = st.data_editor(hugim_df, num_rows="dynamic", key="edit_hugim")
        to_csv_download(hugim_df, "hugim_edited.csv", "hugim.csv")
    if prefs_file:
        prefs_df = show_uploaded(st, "preferences.csv", prefs_file)
        st.subheader("✏️ Edit preferences.csv")
        prefs_df = st.data_editor(prefs_df, num_rows="dynamic", key="edit_prefs")
        to_csv_download(prefs_df, "preferences_edited.csv", "preferences.csv")

    upload_key = str(hugim_file) + "_" + str(prefs_file)
    if st.session_state["last_upload_key"] != upload_key:
        st.session_state["allocation_run"] = False
        st.session_state["last_upload_key"] = upload_key

    ready = hugim_df is not None and prefs_df is not None

    hugim_mapping, prefs_mapping = {}, {}
    if ready:
        st.markdown("## 1. Match your columns")
        hugim_cols = list(hugim_df.columns)
        # Auto-detect column indices
        hugname_idx = find_best_column_match(hugim_cols, ["hugname", "hug_name", "activity", "activityname", "name"])
        capacity_idx = find_best_column_match(hugim_cols, ["capacity", "cap", "max", "maximum"])
        minimum_idx = find_best_column_match(hugim_cols, ["minimum", "min", "min_campers"])

        hugname_col = st.selectbox("Column for Hug Name (activity name):", hugim_cols, index=hugname_idx, key="hugname")
        cap_col = st.selectbox("Column for Capacity:", hugim_cols, index=capacity_idx, key="capacity")
        min_col = st.selectbox("Column for Minimum Campers (must join):", hugim_cols, index=minimum_idx, key="min_campers")
        period_cols = st.multiselect(
            "Columns for periods (choose 3, e.g. Aleph, Beth, Gimmel):",
            hugim_cols,
            default=[col for col in hugim_cols if col.lower() in ["aleph", "beth", "gimmel"]]
        )
        hugim_mapping = {
            "HugName": hugname_col,
            "Capacity": cap_col,
            "Minimum": min_col,
            "Periods": period_cols
        }

        pref_cols = list(prefs_df.columns)
        camperid_idx = find_best_column_match(pref_cols, ["camperid", "camper_id", "student_id", "studentid", "full_name", "fullname", "name", "Full Name", "id"])
        camperid_col = st.selectbox("Column for Camper ID:", pref_cols, index=camperid_idx, key="camperid")
        period_prefixes = set(c.split("_")[0] for c in pref_cols if "_" in c)
        st.write("Match your periods:")
        period_map = {}
        for period in period_cols:
            auto = [p for p in period_prefixes if p.lower() == period.lower()]
            value = st.selectbox(
                f"Prefix in preferences.csv for period '{period}':",
                sorted(period_prefixes),
                index=sorted(period_prefixes).index(auto[0]) if auto else 0,
                key=f"pref_prefix_{period}"
            )
            period_map[period] = value
        prefs_mapping = {
            "CamperID": camperid_col,
            "PeriodPrefixes": period_map
        }
        st.info(f"Hugim mapping: {hugim_mapping}")
        st.info(f"Preferences mapping: {prefs_mapping}")

    if ready:
        pref_period_cols = []
        for period, prefix in prefs_mapping.get("PeriodPrefixes", {}).items():
            prefix_str = str(prefix)
            pref_period_cols.extend([col for col in prefs_df.columns if col.startswith(prefix_str + "_")])
        missing_hugim = find_missing(
            prefs_df[pref_period_cols],
            hugim_df,
            hug_col=hugim_mapping["HugName"]
        )
        if missing_hugim:
            st.warning(
                f"These HugNames are referenced in preferences.csv but missing from hugim.csv and will be skipped:\n`{', '.join(missing_hugim)}`"
            )

    if ready:
        if st.session_state["allocation_run"]:
            st.warning("Allocation already run for current files.")
            col1, col2 = st.columns(2)
            with col1:
                st.button("Run Allocation", disabled=True)
            with col2:
                if st.button("Allow Rerun"):
                    st.session_state["allocation_run"] = False
        else:
            if st.button("Run Allocation"):
                st.session_state["allocation_run"] = True
                mapped_hugim = hugim_df[
                    [hugim_mapping["HugName"], hugim_mapping["Capacity"], hugim_mapping["Minimum"]] + list(hugim_mapping["Periods"])
                ]
                mapped_hugim.to_csv("hugim.csv", index=False)
                mapped_prefs = prefs_df.copy()
                mapped_prefs.to_csv("preferences.csv", index=False)

                try:
                    hug_data = load_hugim("hugim.csv", mapping=hugim_mapping)
                    campers = load_preferences("preferences.csv", mapping=prefs_mapping)
                    st.info(f"Loaded {len(campers)} campers and {sum(len(hs) for hs in hug_data.values())} hugim-periods.")

                    run_allocation(campers, hug_data)
                    enforce_minimums_cancel_and_reallocate(campers, hug_data)
                    calculate_and_store_weekly_scores(campers)
                    save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
                    save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
                    save_stats(campers, hug_data, OUTPUT_STATS_FILE)

                    # ----- OUTPUTS -----
                    # =========================
                    # 1. Assignments Table
                    # =========================
                    if OUTPUT_ASSIGNMENTS_FILE.exists() and OUTPUT_ASSIGNMENTS_FILE.stat().st_size > 0:
                        df_assignments = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
                        st.subheader("📋 Assignments Table")
                        df_assignments.index = df_assignments.index + 1
                        st.dataframe(df_assignments)
                        st.download_button(
                            label="Download Assignments CSV",
                            data=OUTPUT_ASSIGNMENTS_FILE.read_text(),
                            file_name=OUTPUT_ASSIGNMENTS_FILE.name,
                            mime="text/csv"
                        )
                    else:
                        st.error("Assignments output was not generated (allocation failed). See warnings above.")
                        return

                    # =========================
                    # 2. Preference Satisfaction Summary
                    # =========================
                    st.subheader("🌟 Preference Satisfaction Summary")
                    how_cols = [col for col in df_assignments.columns if col.endswith('_How')]
                    pref_counts = {}
                    for how_col in how_cols:
                        vals = df_assignments[how_col].value_counts()
                        for idx, count in vals.items():
                            pref_counts[idx] = pref_counts.get(idx, 0) + count

                    total_assignments = sum(pref_counts.values())
                    summary_rows = []
                    order = ['Pref_1','Pref_2','Pref_3','Pref_4','Pref_5','Random','Forced_minimum', '']
                    order_labels = ['1st Choice', '2nd Choice', '3rd Choice', '4th Choice', '5th Choice', 'Random', 'Forced Minimum', 'Unassigned']
                    for pref, label in zip(order, order_labels):
                        cnt = pref_counts.get(pref, 0)
                        pct = 100 * cnt / total_assignments if total_assignments else 0
                        summary_rows.append({"Assignment Type": label, "Count": cnt, "Percent": f"{pct:.1f}%"})
                    summary_df = pd.DataFrame(summary_rows)
                    st.dataframe(summary_df)

                    # =========================
                    # 3. Bar Chart Visualization
                    # =========================
                    try:
                        import plotly.express as px
                        chart_df = summary_df[summary_df['Assignment Type'] != 'Unassigned']
                        fig = px.bar(
                            chart_df, x='Assignment Type', y='Count', text='Percent',
                            title="Assignments by Preference Rank", color='Assignment Type'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except ImportError:
                        st.bar_chart(summary_df[summary_df['Assignment Type'] != 'Unassigned'].set_index('Assignment Type')["Count"])

                    # =========================
                    # 4. Statistics Table
                    # =========================
                    if OUTPUT_STATS_FILE.exists():
                        df_stats = pd.read_csv(OUTPUT_STATS_FILE)
                        st.subheader("📊 Statistics Table")
                        df_stats.index = df_stats.index + 1
                        st.dataframe(df_stats)
                        st.download_button(
                            label="Download Stats CSV",
                            data=OUTPUT_STATS_FILE.read_text(),
                            file_name=OUTPUT_STATS_FILE.name,
                            mime="text/csv"
                        )
                    else:
                        st.warning("No statistics generated.")

                    # =========================
                    # 5. Unassigned Campers (with reason breakdown)
                    # =========================

                    if OUTPUT_UNASSIGNED_FILE.exists() and OUTPUT_UNASSIGNED_FILE.stat().st_size > 0:
                        df_unassigned = pd.read_csv(OUTPUT_UNASSIGNED_FILE)
                        st.subheader("🚫 Unassigned Campers")
                        df_unassigned.index = df_unassigned.index + 1
                        st.dataframe(df_unassigned)
                        st.download_button(
                            label="Download Unassigned Campers CSV",
                            data=OUTPUT_UNASSIGNED_FILE.read_text(),
                            file_name=OUTPUT_UNASSIGNED_FILE.name,
                            mime="text/csv"
                        )

                        # Reason Breakdown
                        st.write("### Unassignment Reasons Breakdown")
                        reason_counts = df_unassigned['Reason'].value_counts()
                        st.write(reason_counts)
                    else:
                        st.success("All campers got a Hug assignment for each period! No one unassigned.")

                    # =========================
                    # 6. Cancelled Hugim - Who wanted them?
                    # =========================
                    if ready and 'missing_hugim' in locals() and missing_hugim:
                        st.subheader("❌ Cancelled or Unavailable Hugim Analysis")

                        for hug in missing_hugim:
                            campers_wanted = []
                            for period, prefix in prefs_mapping.get("PeriodPrefixes", {}).items():
                                period_pref_cols = [col for col in prefs_df.columns if col.startswith(f"{prefix}_")]
                                matches = prefs_df[period_pref_cols].apply(lambda row: hug in row.values, axis=1)
                                wanted_these = prefs_df.loc[matches, prefs_mapping["CamperID"]].tolist()
                                campers_wanted.extend([
                                    f"{str(camper)} (Period: {period})"
                                    for camper in wanted_these
                                ])
                            n_wanted = len(campers_wanted)
                            st.info(f"Hug '{hug}': {n_wanted} camper(s) listed this as a preference.")
                            if campers_wanted:
                                with st.expander(f"See list of campers who wanted '{hug}'"):
                                    st.write(', '.join(campers_wanted))

                    st.success("Allocation and report sections complete. Please review the summaries, download files as needed, or allow a rerun above if you wish to re-allocate.")

                    # Optionally, summarize at a glance:
                    st.markdown(f"""
                        #### 📊 Quick Summary
                        - **Total campers assigned**: {len(df_assignments)}
                        - **Total assignments (all periods):** {total_assignments}
                        - **Unassigned slots:** {summary_df[summary_df['Assignment Type'] == 'Unassigned']['Count'].values[0]}
                        - **% Got Top-3 choice:** {sum(summary_df.loc[:2, 'Count'])/total_assignments*100:.1f}% 
                    """)

                    if missing_hugim:
                        st.warning(f"Ignored preferences for these HugNames (not in hugim.csv): {', '.join(missing_hugim)}")
                except Exception as e:
                    import traceback
                    st.error(f"Error during allocation: {e}")
                    with st.expander("Show traceback"):
                        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
