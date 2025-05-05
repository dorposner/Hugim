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
OUTPUT_UNASSIGNED_FILE
)

def main():
st.title("Hugim Allocation Web App")
st.write("Upload your CSV files below...")
# etc.
if name == "main":
main()

campers_file = st.file_uploader("Upload campers.csv", type=["csv"])
hugim_file   = st.file_uploader("Upload hugim.csv",   type=["csv"])
pref_file    = st.file_uploader("Upload preferences.csv", type=["csv"])

if campers_file and hugim_file and pref_file:
    if st.button("Run Allocation"):
        # Save uploaded files temporarily in the current directory
        with open("campers.csv", "wb") as f:
            f.write(campers_file.read())
        with open("hugim.csv", "wb") as f:
            f.write(hugim_file.read())
        with open("preferences.csv", "wb") as f:
            f.write(pref_file.read())

        # Run the core allocation logic
        hug_data  = load_hugim("hugim.csv")
        camp_data = load_campers("campers.csv")
        load_preferences("preferences.csv", camp_data)
        run_allocation(camp_data, hug_data)

        # Display results
        st.subheader("Assignments")
        df_assignments = pd.read_csv(OUTPUT_ASSIGNMENTS_FILE)
        st.dataframe(df_assignments)

        st.subheader("Statistics")
        df_stats = pd.read_csv(OUTPUT_STATS_FILE)
        st.dataframe(df_stats)

        if os.path.exists(OUTPUT_UNASSIGNED_FILE) and os.path.getsize(OUTPUT_UNASSIGNED_FILE) > 0:
            st.subheader("Unassigned Campers")
            df_unassigned = pd.read_csv(OUTPUT_UNASSIGNED_FILE)
            st.dataframe(df_unassigned)
        else:
            st.write("All campers got their required number of Hugim!")

        st.write("Download if desired:")
        st.download_button(
            label="Download Assignments CSV",
            data=df_assignments.to_csv(index=False),
            file_name=OUTPUT_ASSIGNMENTS_FILE,
            mime="text/csv"
        )
        st.download_button(
            label="Download Stats CSV",
            data=df_stats.to_csv(index=False),
            file_name=OUTPUT_STATS_FILE,
            mime="text/csv"
        )
        if os.path.exists(OUTPUT_UNASSIGNED_FILE) and os.path.getsize(OUTPUT_UNASSIGNED_FILE) > 0:
            with open(OUTPUT_UNASSIGNED_FILE, "r") as f:
                unassigned_csv = f.read()
            st.download_button(
                label="Download Unassigned Campers CSV",
                data=unassigned_csv,
                file_name=OUTPUT_UNASSIGNED_FILE,
                mime="text/csv"
            )
        if name == "main":
main()

  
