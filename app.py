import os
import streamlit as st
from pathlib import Path
import sys
from pathlib import Path
import streamlit as st

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set page config - must be the first Streamlit command
st.set_page_config(
    page_title="Hugim Allocation System",
    page_icon="🎯",
    layout="wide"
)

def ensure_data_directories():
    """Ensure all required data directories exist"""
    data_dirs = [
        "data/uploads",
        "data/output",
        "data/state"
    ]
    
    for dir_path in data_dirs:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            st.error(f"Error creating directory {dir_path}: {e}")

def main():
    try:
        from src.utils.state import initialize_session_state
        
        # Initialize session state
        initialize_session_state()
        
        # Ensure all required data directories exist
        ensure_data_directories()
        
        # Simple routing
        st.sidebar.title("Navigation")
        page = st.sidebar.radio("Go to", ["Admin", "Camper"])
        
        if page == "Admin":
            from src.pages.admin.dashboard import main as admin_main
            admin_main()
        else:
            from src.pages.camper.registration import main as camper_main
            camper_main()
    except ImportError as e:
        st.error(f"Failed to initialize application: {e}")
        st.error("Please ensure all dependencies are installed and the project structure is correct.")
        st.stop()

if __name__ == "__main__":
    main()
