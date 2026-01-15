import streamlit as st
import pandas as pd
from pathlib import Path
import googlesheets  # NEW: Import the Google Sheets module
import importlib
importlib.reload(googlesheets) # Force reload to ensure latest logic is used

st.set_page_config(
    page_title="Camp Hugim Allocator",
    page_icon="🏕️",
    initial_sidebar_state="expanded"
)

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
    enforce_minimums_cancel_and_reallocate,
    fill_minimums
)

def init_session():
    """Initialize session_state keys so Streamlit won't lose data after refresh."""
    keys = [
        "campers",
        "hug_data",
        "assignments_df",
        "stats_df",
        "unassigned_df",
        "pending_config", # NEW: For config loading
        "current_camp_name", # NEW: Track camp name
        "hugim_df",
        "prefs_df"
    ]
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

    if "uploader_id" not in st.session_state:
        st.session_state["uploader_id"] = 0

init_session()

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

    # ---------------------------------------------------------
    # SIDEBAR FOR CAMP CONFIGURATION
    # ---------------------------------------------------------
    st.sidebar.title("Camp Configuration")
    camp_name = st.sidebar.text_input("Camp Name / ID", value=st.session_state.get("current_camp_name") or "")

    # Load Logic
    if camp_name and camp_name != st.session_state.get("current_camp_name"):
        st.session_state["current_camp_name"] = camp_name
        # Reset uploaders when switching camp
        st.session_state["uploader_id"] += 1
        st.session_state["hugim_df"] = None
        st.session_state["prefs_df"] = None

        with st.spinner(f"Loading configuration for '{camp_name}'..."):
            config = googlesheets.read_config(camp_name)
            if config:
                st.session_state["pending_config"] = config
                # Load data if available
                if 'hugim_df' in config and not config['hugim_df'].empty:
                    st.session_state["hugim_df"] = config['hugim_df']
                if 'prefs_df' in config and not config['prefs_df'].empty:
                    st.session_state["prefs_df"] = config['prefs_df']
                st.sidebar.success(f"Configuration loaded!")
            else:
                st.sidebar.info("No existing configuration found. A new one will be created upon save.")

    # Save Logic
    if st.sidebar.button("Save Camp Configuration"):
        if not camp_name:
            st.sidebar.error("Please enter a Camp Name.")
        elif "hugname" not in st.session_state:
            st.sidebar.error("Please configure the columns and periods before saving.")
        else:
             # Gather data from session state
             try:
                 # Get selected periods
                 periods = st.session_state.get("periods_selected", [])

                 # Capture any prefixes for periods that might have been added manually
                 prefixes = {}
                 all_period_keys = [k for k in st.session_state.keys() if k.startswith("pref_prefix_")]
                 for key in all_period_keys:
                     p_name = key.replace("pref_prefix_", "")
                     prefixes[p_name] = st.session_state[key]
                     if p_name not in periods:
                         periods.append(p_name)

                 config_data = {
                     'config': {
                         'col_hug_name': st.session_state.get("hugname"),
                         'col_capacity': st.session_state.get("capacity"),
                         'col_minimum': st.session_state.get("min_campers"),
                         'col_camper_id': st.session_state.get("camperid"),
                         'max_preferences_per_period': st.session_state.get("detected_max_prefs", 5)
                     },
                     'periods': periods,
                     'preference_prefixes': prefixes
                 }

                 # Get current dataframes
                 hugim_df_save = st.session_state.get("hugim_df")
                 prefs_df_save = st.session_state.get("prefs_df")

                 with st.sidebar.status("Saving to Master Spreadsheet..."):
                     success = googlesheets.save_config(camp_name, config_data, hugim_df_save, prefs_df_save)
                     if success:
                         st.sidebar.success("Configuration and data saved successfully!")
                     else:
                         st.sidebar.error("Failed to save configuration.")
             except Exception as e:
                 st.sidebar.error(f"Error gathering configuration: {e}")

    # Reset Logic
    if st.sidebar.button("Reset Configuration"):
        st.session_state["pending_config"] = None
        st.session_state["current_camp_name"] = None
        keys_to_clear = ["hugname", "capacity", "min_campers", "camperid", "periods_selected"]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        # Also clear prefix keys
        for k in list(st.session_state.keys()):
            if k.startswith("pref_prefix_"):
                del st.session_state[k]
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Maintenance")
    if st.sidebar.button("Empty Service Account Trash"):
        with st.sidebar.status("Emptying trash..."):
            if googlesheets.force_empty_trash():
                st.sidebar.success("Trash emptied successfully.")
            else:
                st.sidebar.error("Failed to empty trash.")

    # ---------------------------------------------------------
    # MAIN APP
    # ---------------------------------------------------------

    st.title("Camp Hugim Allocation Web App")

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

    st.info("💡 Need sample data? Use the **[File Generator](/generate_files)** page to create random test files.")

    st.write("Upload your CSV files below. You can preview and edit before running allocation:")

    # Check if data is already loaded
    if st.session_state.get("hugim_df") is not None:
        st.success("✅ hugim.csv loaded from cloud.")
    if st.session_state.get("prefs_df") is not None:
        st.success("✅ preferences.csv loaded from cloud.")

    uploader_key = st.session_state["uploader_id"]
    hugim_file = st.file_uploader("Upload hugim.csv", type=["csv"], key=f"hugim_up_{uploader_key}")
    prefs_file = st.file_uploader("Upload preferences.csv", type=["csv"], key=f"prefs_up_{uploader_key}")

    # Use session state as primary source
    hugim_df = st.session_state.get("hugim_df")
    prefs_df = st.session_state.get("prefs_df")

    if hugim_file:
        hugim_df = show_uploaded(st, "hugim.csv", hugim_file)
        st.session_state["hugim_df"] = hugim_df

    if prefs_file:
        prefs_df = show_uploaded(st, "preferences.csv", prefs_file)
        st.session_state["prefs_df"] = prefs_df

    if hugim_df is not None:
        st.subheader("✏️ Edit hugim.csv")
        hugim_df = st.data_editor(hugim_df, num_rows="dynamic", key="edit_hugim")
        st.session_state["hugim_df"] = hugim_df
        to_csv_download(hugim_df, "hugim_edited.csv", "hugim.csv")

    if prefs_df is not None:
        st.subheader("✏️ Edit preferences.csv")
        prefs_df = st.data_editor(prefs_df, num_rows="dynamic", key="edit_prefs")
        st.session_state["prefs_df"] = prefs_df
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
        pref_cols = list(prefs_df.columns)

        # ---------------------------------------------------------
        # APPLY LOADED CONFIG (if available and not yet applied)
        # ---------------------------------------------------------
        if st.session_state.get("pending_config"):
            config = st.session_state["pending_config"]
            cfg_dict = config.get('config', {})

            # Helper to check validity
            def set_if_valid(key, val, options):
                if val in options:
                    st.session_state[key] = val

            set_if_valid("hugname", cfg_dict.get('col_hug_name'), hugim_cols)
            set_if_valid("capacity", cfg_dict.get('col_capacity'), hugim_cols)
            set_if_valid("min_campers", cfg_dict.get('col_minimum'), hugim_cols)
            set_if_valid("camperid", cfg_dict.get('col_camper_id'), pref_cols)

            # Periods
            saved_periods = config.get('periods', [])
            valid_periods = [p for p in saved_periods if p in hugim_cols]
            if valid_periods:
                st.session_state["periods_selected"] = valid_periods

            # Prefixes
            saved_prefixes = config.get('preference_prefixes', {})
            # We can set these even if widget not created yet, Streamlit will pick them up
            for p, prefix in saved_prefixes.items():
                # We should verify if prefix is roughly valid?
                # Ideally we check against sorted(period_prefixes) derived below,
                # but we can just set it and let the user correct if needed.
                st.session_state[f"pref_prefix_{p}"] = prefix

            del st.session_state["pending_config"]
            st.rerun()

        # ---------------------------------------------------------

        # Auto-detect column indices (defaults)
        hugname_idx = find_best_column_match(hugim_cols, ["hugname", "hug_name", "activity", "activityname", "name"])
        capacity_idx = find_best_column_match(hugim_cols, ["capacity", "cap", "max", "maximum"])
        minimum_idx = find_best_column_match(hugim_cols, ["minimum", "min", "min_campers"])

        hugname_col = st.selectbox("Column for Hug Name (activity name):", hugim_cols, index=hugname_idx, key="hugname")
        cap_col = st.selectbox("Column for Capacity:", hugim_cols, index=capacity_idx, key="capacity")
        min_col = st.selectbox("Column for Minimum Campers (must join):", hugim_cols, index=minimum_idx, key="min_campers")

        period_cols = st.multiselect(
            "Columns for periods (e.g. Morning, Afternoon):",
            hugim_cols,
            default=[col for col in hugim_cols if col.lower() in ["aleph", "beth", "gimmel", "morning", "afternoon", "block a", "block b"]] if "aleph" in [c.lower() for c in hugim_cols] else [],
            key="periods_selected"
        )

        # NEW: Show detected periods and allow adding a new period (UI-only)
        st.write("🎪 Detected periods from hugim.csv:")
        if period_cols:
            st.info(", ".join(period_cols))
        else:
            st.warning("No period columns selected. Please choose the period columns above.")

        # Note: 'new_period' is not persisted in config unless it becomes a column or is added to multiselect
        new_period = st.text_input("Add a new period name (optional):", value="", placeholder="e.g., Dalet")
        if new_period and new_period.strip():
            new_period_clean = new_period.strip()
            if new_period_clean not in period_cols:
                # We can't easily append to the multiselect output variable to influence the options,
                # but we can append to the list used for mapping.
                period_cols.append(new_period_clean)
                st.success(f"New period '{new_period_clean}' has been added to the list (UI only).")
            else:
                st.info(f"Period '{new_period_clean}' already exists in the list.")

        hugim_mapping = {
            "HugName": hugname_col,
            "Capacity": cap_col,
            "Minimum": min_col,
            "Periods": period_cols
        }

        camperid_idx = find_best_column_match(pref_cols, ["camperid", "camper_id", "student_id", "studentid", "full_name", "fullname", "name", "Full Name", "id"])
        camperid_col = st.selectbox("Column for Camper ID:", pref_cols, index=camperid_idx, key="camperid")

        period_prefixes = set(c.split("_")[0] for c in pref_cols if "_" in c)
        # Informational: Max preferences
        max_pref_count = 0
        for prefix in period_prefixes:
            count = len([c for c in pref_cols if c.startswith(prefix + "_")])
            if count > max_pref_count:
                max_pref_count = count
        if max_pref_count > 0:
            st.info(f"ℹ️ Detected up to {max_pref_count} preferences per period.")

        st.session_state["detected_max_prefs"] = max_pref_count

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
            # Add UI selection for Minimums Strategy
            strategy = st.radio(
                "Under-enrolled Strategy:",
                ("Cancel & Reallocate (Default)", "Force Fill"),
                help="Cancel: Removes activities below minimum and moves campers. Force Fill: Adds random campers to meet minimums."
            )

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
                    # UPDATED: Receive max_prefs
                    campers, max_prefs = load_preferences("preferences.csv", mapping=prefs_mapping)
                    st.info(f"Loaded {len(campers)} campers and {sum(len(hs) for hs in hug_data.values())} hugim-periods.")

                    # UPDATED: Pass periods and max_prefs
                    run_allocation(campers, hug_data, list(period_map.keys()), max_prefs)

                    if strategy.startswith("Cancel"):
                        enforce_minimums_cancel_and_reallocate(campers, hug_data)
                    else:
                        fill_minimums(campers, hug_data)

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

                    # 🔹 Save all results into session_state (after files are saved)
                    if OUTPUT_ASSIGNMENTS_FILE.exists():
                        st.session_state["assignments_df"] = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
                    else:
                        st.session_state["assignments_df"] = None
                    
                    if OUTPUT_STATS_FILE.exists():
                        st.session_state["stats_df"] = pd.read_csv(OUTPUT_STATS_FILE)
                    else:
                        st.session_state["stats_df"] = None
                    
                    if OUTPUT_UNASSIGNED_FILE.exists():
                        st.session_state["unassigned_df"] = pd.read_csv(OUTPUT_UNASSIGNED_FILE)
                    else:
                        st.session_state["unassigned_df"] = None
                    
                    st.session_state["campers"] = campers
                    st.session_state["hug_data"] = hug_data
                    
                    st.success("✅ Allocation completed! You can now view or download results below.")

                    if st.session_state["assignments_df"] is not None:
                        st.subheader("📋 Assignments Results")
                        st.dataframe(st.session_state["assignments_df"])
                        st.download_button(
                            "⬇️ Download Assignments CSV",
                            data=st.session_state["assignments_df"].to_csv(index=False),
                            file_name="assignments_output.csv",
                            mime="text/csv"
                        )

                    if st.session_state["unassigned_df"] is not None:
                        st.subheader("🚫 Unassigned Campers")
                        st.dataframe(st.session_state["unassigned_df"])
                        st.download_button(
                            "⬇️ Download Unassigned CSV",
                            data=st.session_state["unassigned_df"].to_csv(index=False),
                            file_name="unassigned_campers_output.csv",
                            mime="text/csv"
                        )



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

    st.markdown("---")
    st.markdown("Built By Dor Posner with ❤️ for Camp Administrators | [Support](mailto:dorposner@gmail.com)")

if __name__ == "__main__":
    main()
