import streamlit as st
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
