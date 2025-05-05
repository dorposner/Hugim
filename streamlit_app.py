import streamlit as st
import pandas as pd
import os

from allocator import (
    load_hugim,
    load_campers,
    load_preferences,
    run_allocation,
    OUTPUT_ASSIGNMENTS_FILE,
    OUTPUT_STATS_FILE,
    OUTPUT_UNASSIGNED_FILE,
)

def show_uploaded_df(label, uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        st.write(f"**Preview of {label}:**")
        st.dataframe(df)
        return df
    except Exception as e:
        st.error(f"Could not read {label}: {e}")
        return None

def main():
    st.title("Hugim Allocation Web App")
    st.write("Upload your CSV files below (check the preview before running):")

    campers_file = st.file_uploader("Upload campers.csv", type=["csv"])
    hugim_file   = st.file_uploader("Upload hugim.csv", type=["csv"])
    pref_file    = st.file_uploader("Upload preferences.csv", type=["csv"])

    campers_df = hugim_df = prefs_df = None

    if campers_file:
        campers_df = show_uploaded_df("campers.csv", campers_file)
    if hugim_file:
        hugim_df = show_uploaded_df("hugim.csv", hugim_file)
    if pref_file:
        prefs_df = show_uploaded_df("preferences.csv", pref_file)

    ready = campers_file and hugim_file and pref_file and campers_df is not None and hugim_df is not None and prefs_df is not None

    if ready and st.button("Run Allocation"):
        # Save uploaded files to disk
        campers_file.seek(0)
        hugim_file.seek(0)
        pref_file.seek(0)
        with open("campers.csv", "wb") as f:
            f.write(campers_file.read())
        with open("hugim.csv", "wb") as f:
            f.write(hugim_file.read())
        with open("preferences.csv", "wb") as f:
            f.write(pref_file.read())

        # Now do everything in a try/except block and show more info!
        try:
            hug_data  = load_hugim("hugim.csv")
            camp_data = load_campers("campers.csv")
            load_preferences("preferences.csv", camp_data)
            st.info(f"Loaded {len(camp_data)} campers and {len(hug_data)} hugim.")

            run_allocation(camp_data, hug_data)

            # Show assignments output, if generated
            if os.path.exists(OUTPUT_ASSIGNMENTS_FILE) and os.path.getsize(OUTPUT_ASSIGNMENTS_FILE) > 0:
                df_assignments = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
                st.subheader("Assignments")
                st.dataframe(df_assignments)
                st.download_button(
                    label="Download Assignments CSV",
                    data=df_assignments.to_csv(index=False),
                    file_name=OUTPUT_ASSIGNMENTS_FILE,
                    mime="text/csv"
                )
            else:
                st.error("Assignments output was not generated. This usually means your input files have an error, typos in headers, or do not match. Please check the previews above and fix any typos. All IDs and names must match exactly. If you think there's a bug, contact the developer.")
                return

            # Show statistics output, if generated
            if os.path.exists(OUTPUT_STATS_FILE) and os.path.getsize(OUTPUT_STATS_FILE) > 0:
                df_stats = pd.read_csv(OUTPUT_STATS_FILE)
                st.subheader("Statistics")
                st.dataframe(df_stats)
                st.download_button(
                    label="Download Stats CSV",
                    data=df_stats.to_csv(index=False),
                    file_name=OUTPUT_STATS_FILE,
                    mime="text/csv"
                )
            else:
                st.warning("No statistics generated.")

            # Show unassigned output, if generated
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

        except Exception as e:
            st.error(f"An error occurred: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
