import streamlit as st
import pandas as pd
import random
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path to allow importing ui_utils
sys.path.append(str(Path(__file__).parent.parent))
import ui_utils

st.set_page_config(page_title="File Generator", page_icon="📝")

ui_utils.render_sidebar()

st.title("📝 Data File Generator")
st.write("Create the CSV files needed for the Camp Hugim Allocator.")

# Initialize session state for dataframes
if "gen_hugim_df" not in st.session_state:
    st.session_state["gen_hugim_df"] = pd.DataFrame(columns=["HugName", "Capacity", "Minimum", "Aleph", "Beth", "Gimmel"])
if "gen_prefs_df" not in st.session_state:
    st.session_state["gen_prefs_df"] = pd.DataFrame(columns=["CamperID"])

# --- Tab 1: Activities (Hugim) ---
tab1, tab2 = st.tabs(["1. Activities (Hugim)", "2. Campers & Preferences"])

with tab1:
    st.subheader("Manage Activities")
    st.write("Define the activities available, their limits, and when they are offered.")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Load Sample Activities"):
            sample_data = [
                ["Sports", 20, 8, 1, 1, 0],
                ["Art", 15, 5, 1, 0, 1],
                ["Drama", 15, 5, 1, 1, 0],
                ["Music", 10, 3, 0, 1, 1],
                ["Cooking", 12, 6, 1, 1, 1],
                ["Nature", 20, 5, 0, 1, 1],
                ["Swimming", 25, 10, 1, 0, 0]
            ]
            st.session_state["gen_hugim_df"] = pd.DataFrame(
                sample_data,
                columns=["HugName", "Capacity", "Minimum", "Aleph", "Beth", "Gimmel"]
            )
            st.success("Sample activities loaded!")

    st.session_state["gen_hugim_df"] = st.data_editor(
        st.session_state["gen_hugim_df"],
        num_rows="dynamic",
        column_config={
            "Aleph": st.column_config.CheckboxColumn(default=False),
            "Beth": st.column_config.CheckboxColumn(default=False),
            "Gimmel": st.column_config.CheckboxColumn(default=False),
            "Capacity": st.column_config.NumberColumn(min_value=1),
            "Minimum": st.column_config.NumberColumn(min_value=0)
        },
        key="editor_hugim"
    )

    st.download_button(
        label="⬇️ Download hugim.csv",
        data=st.session_state["gen_hugim_df"].to_csv(index=False),
        file_name="hugim.csv",
        mime="text/csv",
        disabled=st.session_state["gen_hugim_df"].empty
    )

# --- Tab 2: Campers & Preferences ---
with tab2:
    st.subheader("Manage Campers & Preferences")

    # Needs valid activities first
    activities_df = st.session_state["gen_hugim_df"]
    if activities_df.empty:
        st.warning("⚠️ Please define at least one activity in the previous tab first.")
    else:
        # Determine periods from activity columns (assuming Aleph, Beth, Gimmel structure for now)
        periods = [col for col in activities_df.columns if col in ["Aleph", "Beth", "Gimmel"]]
        if not periods:
            # Fallback if user renamed them, though app structure relies on specific headers or mapping
            # For generator, let's stick to Aleph/Beth/Gimmel or find columns that are not Name/Cap/Min
            periods = [c for c in activities_df.columns if c not in ["HugName", "Capacity", "Minimum"]]

        st.write(f"Detected Periods: {', '.join(periods)}")

        # Generator controls
        with st.expander("Generate Random Campers & Preferences"):
            num_campers = st.number_input("Number of campers to generate", min_value=1, value=50)

            if st.button("Generate Random Preferences"):
                campers = []
                # Simple name list or generator
                first_names = ["Noa", "David", "Sarah", "Daniel", "Maya", "Yoni", "Talia", "Adam", "Rachel", "Ben", "Leah", "Josh", "Shira", "Ari", "Eden", "Sam", "Dina", "Moshe"]
                last_names = ["Cohen", "Levy", "Mizrahi", "Peretz", "Goldstein", "Friedman", "Katz", "Rosen", "Schwartz", "Weiss", "Adler", "Berman", "Glick", "Kaplan"]

                new_rows = []
                for i in range(num_campers):
                    fname = random.choice(first_names)
                    lname = random.choice(last_names)
                    # unique ID
                    cid = f"{fname} {lname} {random.randint(100, 999)}"

                    row = {"CamperID": cid}

                    # Generate preferences for each period
                    for period in periods:
                        # Get activities offered in this period
                        # Assuming the period columns in hugim df act as booleans (1/0)
                        try:
                            # Filter where period column is truthy (1, True, "1")
                            offered = activities_df[
                                activities_df[period].astype(str).str.lower().isin(['1', 'true', 'yes', 'y']) |
                                (pd.to_numeric(activities_df[period], errors='coerce') > 0)
                            ]["HugName"].tolist()
                        except:
                            offered = activities_df["HugName"].tolist()

                        if not offered:
                            offered = ["None"] # Fallback

                        # Select 3-5 preferences
                        k = min(5, len(offered))
                        prefs = random.sample(offered, k)

                        # Fill columns Period_1, Period_2...
                        for rank, p_name in enumerate(prefs):
                            row[f"{period}_{rank+1}"] = p_name

                    new_rows.append(row)

                st.session_state["gen_prefs_df"] = pd.DataFrame(new_rows)
                st.success(f"Generated {num_campers} campers with random preferences!")

        # Display editor
        st.write("Edit Camper Preferences:")
        st.session_state["gen_prefs_df"] = st.data_editor(
            st.session_state["gen_prefs_df"],
            num_rows="dynamic",
            key="editor_prefs"
        )

        st.download_button(
            label="⬇️ Download preferences.csv",
            data=st.session_state["gen_prefs_df"].to_csv(index=False),
            file_name="preferences.csv",
            mime="text/csv",
            disabled=st.session_state["gen_prefs_df"].empty
        )
