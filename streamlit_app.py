import streamlit as st
import pandas as pd
import os

from allocator import (
    load_hugim,
    load_preferences,
    run_allocation,
    save_assignments,
    save_unassigned,
    save_stats,
    OUTPUT_ASSIGNMENTS_FILE,
    OUTPUT_STATS_FILE,
    OUTPUT_UNASSIGNED_FILE,
)

from data_helpers import (
    find_missing,
    show_uploaded,
    validate_csv_headers,
    to_csv_download
)

def main():
    st.title("Hugim Allocation Web App (New Version)")

    # 1. Instructions
    with st.expander("📄 Click here for instructions on preparing your CSV files"):
        st.markdown("""
    #### hugim.csv
    - **Columns required**: `HugName`, `Capacity`, `Aleph`, `Beth`, `Gimmel`
    - Each of Aleph/Beth/Gimmel should be 1 (activity offered at this time) or 0 (not offered at this time)
    - Example:
        | HugName   | Capacity | Aleph | Beth | Gimmel |
        |-----------|----------|-------|------|--------|
        | Sports    | 12       | 1     | 0    | 1      |
        | Art       | 10       | 1     | 1    | 1      |
        | Chess     | 8        | 0     | 1    | 0      |

    ---
    #### preferences.csv
    - One row per camper. Columns: `CamperID`, `Aleph_1`..`Aleph_5`, `Beth_1`..`Beth_5`, `Gimmel_1`..`Gimmel_5`
    - Example:
        | CamperID | Aleph_1 | Aleph_2 | Aleph_3 | Aleph_4 | Aleph_5 | Beth_1 | ... | Gimmel_5 |
        |----------|---------|---------|---------|---------|---------|--------|-----|----------|
        | 123      | Art     | Soccer  | Chess   | Drama   | Dance   | Chess  | ... | Art      |
    - For each time (Aleph, Beth, Gimmel), camper lists 5 ordered preferences.
    """)

    st.write("Upload your CSV files below (then you can preview and edit them before running allocation):")

    hugim_file = st.file_uploader("Upload hugim.csv (activities, times, capacities)", type=["csv"])
    prefs_file = st.file_uploader("Upload preferences.csv (5 choices per time, per camper)", type=["csv"])

    hugim_df = prefs_df = None
    missing_campers = []
    missing_hugim = []

    # Preview AND allow edit
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

    # Main logic -- use edited DataFrames regardless of input!
    ready = hugim_df is not None and prefs_df is not None

    if ready:
        ok, msg = validate_csv_headers(hugim_df, prefs_df)
        if not ok:
            st.error(msg)
            return

        # Now check for missing hugim in preferences
        missing_hugim = find_missing(prefs_df, None, hugim_df)  # campers_df=None
        if missing_hugim:
            st.warning(
                f"These HugNames are referenced in preferences.csv but missing from hugim.csv and will be skipped:\n`{', '.join(missing_hugim)}`"
            )

    # Allow Run Allocation with the edited data only
    if ready and st.button("Run Allocation"):
        # Write local CSVs to disk for the allocator module
        hugim_df.to_csv("hugim.csv", index=False)
        prefs_df.to_csv("preferences.csv", index=False)

        try:
            hug_data = load_hugim("hugim.csv")
            campers = load_preferences("preferences.csv")  # campers is a dict or list of campers w/ preferences

            st.info(f"Loaded {len(campers)} campers and {len(hug_data)} hugim.")

            run_allocation(campers, hug_data)
            save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
            save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
            save_stats(campers, hug_data, OUTPUT_STATS_FILE)

            # Show assignments output, if generated
            if os.path.exists(OUTPUT_ASSIGNMENTS_FILE) and os.path.getsize(OUTPUT_ASSIGNMENTS_FILE) > 0:
                df_assignments = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
                st.subheader("📋 Assignments Table")
                st.dataframe(df_assignments)
                st.download_button(
                    label="Download Assignments CSV",
                    data=df_assignments.to_csv(index=False),
                    file_name=OUTPUT_ASSIGNMENTS_FILE,
                    mime="text/csv"
                )
            else:
                st.error("Assignments output was not generated (allocation failed). See warnings above.")
                return

            # Show statistics output, if generated
            if os.path.exists(OUTPUT_STATS_FILE):
                df_stats = pd.read_csv(OUTPUT_STATS_FILE)
                st.subheader("📊 Statistics Table")
                st.dataframe(df_stats)
                st.download_button(
                    label="Download Stats CSV",
                    data=df_stats.to_csv(index=False),
                    file_name=OUTPUT_STATS_FILE,
                    mime="text/csv"
                )
            else:
                st.warning("No statistics generated.")

            # Show unassigned campers, if any
            if os.path.exists(OUTPUT_UNASSIGNED_FILE) and os.path.getsize(OUTPUT_UNASSIGNED_FILE) > 0:
                df_unassigned = pd.read_csv(OUTPUT_UNASSIGNED_FILE)
                st.subheader("❗ Unassigned Campers")
                st.dataframe(df_unassigned)
                st.download_button(
                    label="Download Unassigned Campers CSV",
                    data=df_unassigned.to_csv(index=False),
                    file_name=OUTPUT_UNASSIGNED_FILE,
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
