import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Camp Hugim Allocator",
    page_icon="🏕️",
    initial_sidebar_state="collapsed"
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
    enforce_minimums_cancel_and_reallocate
)

# ---- Output paths for this app session ----
OUTPUT_ASSIGNMENTS_FILE = Path("assignments_output.csv")
OUTPUT_STATS_FILE = Path("stats_output.csv")
OUTPUT_UNASSIGNED_FILE = Path("unassigned_campers_output.csv")


def find_best_column_match(columns, target_names):
    """
    Find the best matching column from a list of target names.
    Returns the index of the best match, or 0 if no match found.
    """
    for target in target_names:
        for i, col in enumerate(columns):
            if target.lower() in col.lower():
                return i
    return 0


# =====================
# PAGE LAYOUT & STYLING
# =====================
st.markdown(
    """
    <style>
    .big-font {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .info-box {
        background: rgba(31, 119, 180, 0.1);
        padding: 1rem;
        border-left: 4px solid #1f77b4;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<p class="big-font">🏕️ Camp Hugim Allocator 🏕️</p>', unsafe_allow_html=True)
st.markdown("---")

# ============================
# 1. FILE UPLOAD SIDEBAR
# ============================
with st.sidebar:
    st.subheader("📁 Upload Files")
    hugim_file = st.file_uploader(
        "Upload hugim.csv (Camp schedule)",
        type="csv",
        key="hugim_uploader"
    )
    prefs_file = st.file_uploader(
        "Upload preferences.csv (Camper preferences)",
        type="csv",
        key="prefs_uploader"
    )

# ============================
# 2. MAIN LOGIC
# ============================
if hugim_file and prefs_file:
    try:
        # Load data
        df_hugim = pd.read_csv(hugim_file)
        df_prefs = pd.read_csv(prefs_file)

        # Display info
        with st.expander("📊 Uploaded Files Preview", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**hugim.csv**")
                st.dataframe(df_hugim.head())
            with col2:
                st.write("**preferences.csv**")
                st.dataframe(df_prefs.head())

        # Simple display and allocation example
        st.success("✅ Files loaded successfully!")

        if st.button("🎲 Run Allocation"):
            st.info("Allocation logic would go here...")

    except Exception as e:
        st.error(f"Error processing files: {e}")
        with st.expander("Show details"):
            import traceback
            st.code(traceback.format_exc())
else:
    st.info("👈 Please upload both files to get started.")

st.markdown("---")
st.markdown("Built By Dor Posner with ❤️ for Camp Administrators | [Support](mailto:dorposner@gmail.com)")
