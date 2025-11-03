import streamlit as st
import pandas as pd
# ============================
# 1. FILE UPLOAD MAIN AREA
# ============================
st.title("🏕️ Camp Hugim Allocator")
st.markdown("Upload your files to get started:")
col1, col2 = st.columns(2)
with col1:
    hugim_file = st.file_uploader(
        "Upload hugim.csv (Camp schedule)",
        type="csv",
        key="hugim_uploader"
    )
with col2:
    prefs_file = st.file_uploader(
        "Upload preferences.csv (Camper preferences)",
        type="csv",
        key="prefs_uploader"
    )

# ============================
# 2. DISPLAY PREVIEW IMMEDIATELY AFTER UPLOAD
# ============================
if hugim_file:
    st.info("📋 Camp Schedule Preview:")
    try:
        df_hugim = pd.read_csv(hugim_file)
        st.dataframe(df_hugim.head())
    except Exception as e:
        st.error(f"Error loading hugim.csv: {e}")

if prefs_file:
    st.info("👥 Camper Preferences Preview:")
    try:
        df_prefs = pd.read_csv(prefs_file)
        st.dataframe(df_prefs.head())
    except Exception as e:
        st.error(f"Error loading preferences.csv: {e}")

# ============================
# 3. MAIN LOGIC - RUN ALLOCATION
# ============================
if hugim_file and prefs_file:
    # Show the Run Allocation button
    if st.button("▶️ Run Allocation", key="run_button"):
        try:
            # Load data
            df_hugim = pd.read_csv(hugim_file)
            df_prefs = pd.read_csv(prefs_file)
            
            # Display info
            st.success("Files loaded successfully!")
            st.markdown("### 🎯 Allocation Results:")
            st.dataframe(df_hugim)
            st.dataframe(df_prefs)
            
        except Exception as e:
            st.error(f"Error during allocation: {e}")
