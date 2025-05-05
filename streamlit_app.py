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

def main():
    st.title("Hugim Allocation Web App")
    st.write("Upload your CSV files below...")

    campers_file = st.file_uploader("Upload campers.csv", type=["csv"])
    hugim_file   = st.file_uploader("Upload hugim.csv", type=["csv"])
    pref_file    = st.file_uploader("Upload preferences.csv", type=["csv"])

    if campers_file and hugim_file and pref_file:
        if st.button("Run Allocation"):
            # Save uploaded files temporarily to the current dir
            with open("campers.csv", "wb") as f:
                f.write(campers_file.read())
            with open("hugim.csv", "wb") as f:
                f.write(hugim_file.read())
            with open("preferences.csv", "wb") as f:
                f.write(pref_file.read())

            # RUN allocation
            try:
                hug_data  = load_hugim("hugim.csv")
                camp_data = load_campers("campers.csv")
                load_preferences("preferences.csv", camp_data)
                run_allocation(camp_data, hug_data)
            except Exception as e:
                st.error(f"Error during allocation: {e}")
                return

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
                st.error("Assignments output was not generated. Please check your input files and try again.")
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

if __name__ == "__main__":
    main()
