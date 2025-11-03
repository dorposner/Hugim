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
# 2. MAIN LOGIC
# ============================
if hugim_file and prefs_file:
    try:
        # Load data
        df_hugim = pd.read_csv(hugim_file)
        df_prefs = pd.read_csv(prefs_file)
        
        
        # Display info
    except Exception as e:
        st.error(f"שגיאת עיבוד קבצים: {str(e)}")
        import traceback
        st.write(traceback.format_exc())
