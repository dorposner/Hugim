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
    to_csv_download
)

# ---- Output paths for this app session ----
OUTPUT_ASSIGNMENTS_FILE = Path("assignments_output.csv")
OUTPUT_STATS_FILE = Path("stats_output.csv")
OUTPUT_UNASSIGNED_FILE = Path("unassigned_campers_output.csv")

def main():
    # ---- BUTTON SAFETY STATE INIT ----
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

    # Preview/edit both files
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

    # --- TRACK "last upload" to know if things changed ---
    upload_key = str(hugim_file) + "_" + str(prefs_file)
    if st.session_state["last_upload_key"] != upload_key:
        st.session_state["allocation_run"] = False
        st.session_state["last_upload_key"] = upload_key

    ready = hugim_df is not None and prefs_df is not None

    # ---- FLEXIBLE MAPPINGS UI ----
    hugim_mapping, prefs_mapping = {}, {}
    if ready:
        st.markdown("## 1. Match your columns")
        hugim_cols = list(hugim_df.columns)
        hugname_col = st.selectbox("Column for Hug Name (activity name):", hugim_cols, key="hugname")
        cap_col = st.selectbox("Column for Capacity:", hugim_cols, key="capacity")
        min_col = st.selectbox("Column for Minimum Campers (must join):", hugim_cols, key="min_campers")
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

        # Preferences mapping
        pref_cols = list(prefs_df.columns)
        camperid_col = st.selectbox("Column for Camper ID:", pref_cols, key="camperid")
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

    # ---------- Missing Hugim Check ---------
    if ready:
        pref_period_cols = []
        for period, prefix in prefs_mapping.get("PeriodPrefixes", {}).items():
            prefix_str = str(prefix)
            pref_period_cols.extend([col for col in prefs_df.columns if col.startswith(prefix_str + "_")])
        missing_hugim = find_missing(prefs_df[pref_period_cols], hugim_df[[hugim_mapping["HugName"]]])
        if missing_hugim:
            st.warning(
                f"These HugNames are referenced in preferences.csv but missing from hugim.csv and will be skipped:\n`{', '.join(missing_hugim)}`"
            )

    # ------- Allocation Button & Handling -------
    if ready:
        if st.session_state["allocation_run"]:
            st.warning("Allocation already run for current files. Upload or edit data to enable again.")
            st.button("Run Allocation", disabled=True)
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
                    calculate_and_store_weekly_scores(campers)
                    save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
                    save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
                    save_stats(campers, hug_data, OUTPUT_STATS_FILE)

                    # -- OUTPUTS WITH PATH OBJECTS (no more os.path.* for these) --
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

                    if OUTPUT_UNASSIGNED_FILE.exists() and OUTPUT_UNASSIGNED_FILE.stat().st_size > 0:
                        df_unassigned = pd.read_csv(OUTPUT_UNASSIGNED_FILE)
                        st.subheader("❗ Unassigned Campers")
                        df_unassigned.index = df_unassigned.index + 1
                        st.dataframe(df_unassigned)
                        st.download_button(
                            label="Download Unassigned Campers CSV",
                            data=OUTPUT_UNASSIGNED_FILE.read_text(),
                            file_name=OUTPUT_UNASSIGNED_FILE.name,
                            mime="text/csv"
                        )
                    else:
                        st.success("All campers got a Hug assignment for each period! No one unassigned.")

                    if missing_hugim:
                        st.warning(f"Ignored preferences for these HugNames (not in hugim.csv): {', '.join(missing_hugim)}")
                except Exception as e:
                    st.error(f"Error during allocation: {e}")

if __name__ == "__main__":
    main()
