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

from data_helpers import find_missing, show_uploaded, validate_csv_headers

def main():
    st.title("Hugim Allocation Web App")
    st.write("Upload your CSV files below (check the preview before running):")

    campers_file = st.file_uploader("Upload campers.csv", type=["csv"])
    hugim_file = st.file_uploader("Upload hugim.csv", type=["csv"])
    prefs_file = st.file_uploader("Upload preferences.csv", type=["csv"])

    campers_df = hugim_df = prefs_df = None
    missing_campers = missing_hugim = []

    if campers_file:
        campers_df = show_uploaded(st, "campers.csv", campers_file)
    if hugim_file:
        hugim_df = show_uploaded(st, "hugim.csv", hugim_file)
    if prefs_file:
        prefs_df = show_uploaded(st, "preferences.csv", prefs_file)

    ready = (
        campers_file and hugim_file and prefs_file and
        campers_df is not None and hugim_df is not None and prefs_df is not None
    )

    if ready:
        ok, msg = validate_csv_headers(campers_df, hugim_df, prefs_df)
        if not ok:
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

    if ready and st.button("Run Allocation"):
        # Exclude rows with missing campers from prefs
        valid_prefs_df = prefs_df[~prefs_df['CamperID'].astype(str).str.strip().isin(missing_campers)]
        # Overwrite the file Streamlit gave us with a "cleaned" version
        valid_prefs_df.to_csv("preferences.csv", index=False)
        campers_file.seek(0)
        hugim_file.seek(0)
        # Write the originals as received so they're consistent when loaded
        with open("campers.csv", "wb") as f:
            f.write(campers_file.read())
        with open("hugim.csv", "wb") as f:
            f.write(hugim_file.read())

        try:
            hug_data = load_hugim("hugim.csv")
            camp_data = load_campers("campers.csv")
            load_preferences("preferences.csv", camp_data)
            st.info(f"Loaded {len(camp_data)} campers and {len(hug_data)} hugim.")

            run_allocation(camp_data, hug_data)

            # NEW: Save output files so the web app finds them
            save_assignments(camp_data, OUTPUT_ASSIGNMENTS_FILE)
            save_unassigned(camp_data, OUTPUT_UNASSIGNED_FILE)
            save_stats(camp_data, hug_data, OUTPUT_STATS_FILE)

            # Show assignments output, if generated
            if os.path.exists(OUTPUT_ASSIGNMENTS_FILE) and os.path.getsize(OUTPUT_ASSIGNMENTS_FILE) > 0:
                df_assignments = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
                st.subheader("Assignments Table")
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
                st.subheader("Statistics Table")
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
                st.subheader("Unassigned Campers")
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
