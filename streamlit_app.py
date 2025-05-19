import streamlit as st
import pandas as pd
import os

from allocator import (
    load_hugim,
    load_campers,
    load_preferences,
    run_allocation,
    save_assignments,
    save_unassigned,
    save_stats,
    OUTPUT_ASSIGNMENTS_FILE,
    OUTPUT_STATS_FILE,
    OUTPUT_UNASSIGNED_FILE,
)

from data_helpers import find_missing, show_uploaded, validate_csv_headers, validate_age_groups, to_csv_download

def main():
    st.title("Hugim Allocation Web App")

    # 1. Instructions
with st.expander("📄 Click here for instructions on preparing your CSV files"):
    st.markdown("""
    #### campers.csv
    - **Columns required**: `CamperID`, `Got1stChoiceLastWeek`, `AgeGroup`
    - `AgeGroup` must be either `"Younger"` or `"Older"`
    - Example:
        | CamperID | Got1stChoiceLastWeek | AgeGroup |
        |----------|---------------------|----------|
        | 123      | Yes                 | Younger  |
        | 456      | No                  | Older    |

    ---
    #### hugim.csv
    - **Columns required**: `HugName`, `Capacity`, `AgeGroup`
    - `AgeGroup` must be `"Younger"`, `"Older"`, or `"All"` (if open to both)
    - Example:
        | HugName   | Capacity | AgeGroup |
        |-----------|----------|----------|
        | Sports    | 10       | All      |
        | Art       | 15       | Younger  |
        | Coding    | 12       | Older    |

    ---
    #### preferences.csv
    - Must contain columns: `CamperID`, `Pref1`, ... (up to `Pref5`)
    - Example:
        | CamperID | Pref1   | Pref2 | Pref3 | Pref4 | Pref5 |
        |----------|---------|-------|-------|-------|-------|
        | 123      | Drama   | Art   | Music |       |       |
        | 456      | Sports  | Drama |       |       |       |
    """)

    st.write("Upload your CSV files below (then you can preview and edit them before running allocation):")

    campers_file = st.file_uploader("Upload campers.csv", type=["csv"])
    hugim_file = st.file_uploader("Upload hugim.csv", type=["csv"])
    prefs_file = st.file_uploader("Upload preferences.csv", type=["csv"])

    campers_df = hugim_df = prefs_df = None
    missing_campers = missing_hugim = []

    # Preview AND allow edit
    if campers_file:
        campers_df = show_uploaded(st, "campers.csv", campers_file)
        st.subheader("✏️ Edit campers.csv")
        campers_df = st.data_editor(campers_df, num_rows="dynamic", key="edit_campers")
        to_csv_download(campers_df, "campers_edited.csv", "campers.csv")
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
    ready = campers_df is not None and hugim_df is not None and prefs_df is not None

if ready:
    # 1. Check required columns
    ok, msg = validate_csv_headers(campers_df, hugim_df, prefs_df)
    if not ok:
        st.error(msg)
        return

    # 2. Check AgeGroup values
    is_valid, msg = validate_age_groups(campers_df, hugim_df)
    if not is_valid:
        st.error(msg)
        return

        # Now check for missing campers/hugim in preferences
        missing_campers, missing_hugim = find_missing(prefs_df, campers_df, hugim_df)
        if missing_campers:
            st.warning(
                f"These CamperIDs are referenced in preferences.csv but missing from campers.csv and will be skipped:\n`{', '.join(missing_campers)}`"
            )
        if missing_hugim:
            st.warning(
                f"These HugNames are referenced in preferences.csv but missing from hugim.csv and will be skipped:\n`{', '.join(missing_hugim)}`"
            )

    # Allow Run Allocation with the edited data only
    if ready and st.button("Run Allocation"):
        # Exclude rows with missing campers from prefs
        valid_prefs_df = prefs_df[~prefs_df['CamperID'].astype(str).str.strip().isin(missing_campers)]
        campers_df.to_csv("campers.csv", index=False)
        hugim_df.to_csv("hugim.csv", index=False)
        valid_prefs_df.to_csv("preferences.csv", index=False)

        try:
            hug_data = load_hugim("hugim.csv")
            camp_data = load_campers("campers.csv")
            load_preferences("preferences.csv", camp_data)
            st.info(f"Loaded {len(camp_data)} campers and {len(hug_data)} hugim.")

            run_allocation(camp_data, hug_data)
            save_assignments(camp_data, OUTPUT_ASSIGNMENTS_FILE)
            save_unassigned(camp_data, OUTPUT_UNASSIGNED_FILE)
            save_stats(camp_data, hug_data, OUTPUT_STATS_FILE)

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
            if os.path.exists(OUTPUT_STATS_FILE) and os.path.getsize(OUTPUT_STATS_FILE) > 0:
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
                st.success("All campers got their required number of Hugim! No one unassigned.")

            # Summary of what was skipped
            if missing_campers:
                st.warning(f"Skipped `preferences.csv` rows for missing CamperIDs: {', '.join(missing_campers)}")
            if missing_hugim:
                st.warning(f"Ignored preferences for these HugNames (not in hugim.csv): {', '.join(missing_hugim)}")

        except Exception as e:
            st.error(f"Error during allocation: {e}")

if __name__ == "__main__":
    main()
