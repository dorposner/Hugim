import sys
import pickle
from pathlib import Path

import streamlit as st

# Add the project root to Python path to allow absolute imports
PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

# Import local modules
try:
    # Import from src package
    from src.utils.state import (
        initialize_session_state,
        load_state,
        save_state,
        compute_file_hash,
        STATE_DIR,
        STATE_FILE
    )
    from src.utils.loaders import (
        save_uploaded_file, load_hugim, load_preferences,
        HUGIM_CSV, PREFERENCES_CSV, UPLOAD_DIR
    )
    from src.utils.editors import show_activity_editor, show_camper_editor
    from src.utils.ui.components import (
        show_data_overview, show_activities_table, show_camper_preferences
    )
    from src.utils.ui.statistics import show_statistics
    
    # Import from root directory
    try:
        from allocator import run_allocation
        from data_helpers import enforce_minimums_cancel_and_reallocate
    except ImportError:
        # Try relative import if running from a different context
        import sys
        sys.path.append(str(Path(__file__).parents[3]))
        from allocator import run_allocation
        from data_helpers import enforce_minimums_cancel_and_reallocate
    
    # Import models
    from src.models.camper import Camper
    from src.models.period import Period
    from src.models.activity import Activity
except ImportError as e:
    st.error(f"Failed to import required modules: {e}")
    st.stop()

def load_activities(file_path: Path) -> None:
    """Load activities from a CSV file and update session state"""
    if not file_path.exists():
        st.warning(f"Activities file not found: {file_path}")
        return
    
    # Ensure mapping exists
    if 'mapping' not in st.session_state:
        st.session_state.mapping = {
            "HugName": "HugName",
            "Capacity": "Capacity",
            "Minimum": "Minimum",
            "Periods": ["Aleph", "Beth", "Gimmel"],
            "PeriodPrefixes": {
                "Aleph": "Aleph",
                "Beth": "Beth",
                "Gimmel": "Gimmel"
            },
            "NumPreferences": 5
        }
    
    # Load and update the data
    try:
        st.session_state.hugim_data = load_hugim(file_path, st.session_state.mapping)
        save_state()
        st.toast(f"Loaded {sum(len(acts) for acts in st.session_state.hugim_data.values())} activities")
    except Exception as e:
        st.error(f"Error loading activities: {e}")

def load_camper_preferences(file_path: Path) -> None:
    """Load camper preferences from a CSV file and update session state"""
    if not file_path.exists():
        st.warning(f"Preferences file not found: {file_path}")
        return
    
    # Ensure mapping is properly initialized
    if 'mapping' not in st.session_state:
        st.session_state.mapping = {
            "HugName": "HugName",
            "Capacity": "Capacity",
            "Minimum": "Minimum",
            "Periods": ["Aleph", "Beth", "Gimmel"],
            "PeriodPrefixes": {
                "Aleph": "Aleph",
                "Beth": "Beth",
                "Gimmel": "Gimmel"
            },
            "NumPreferences": 5
        }
    
    # Load and update the data
    try:
        st.session_state.campers = load_preferences(file_path, st.session_state.mapping)
        save_state()
        st.toast(f"Loaded preferences for {len(st.session_state.campers)} campers")
    except Exception as e:
        st.error(f"Error loading preferences: {e}")

# Initialize session state with defaults
initialize_session_state()

# Load data from CSV files on startup

# Clear any existing data
st.session_state.hugim_data = {}
st.session_state.campers = []

# Load activities
if HUGIM_CSV.exists():
    with st.spinner("Loading activities..."):
        load_activities(HUGIM_CSV)
else:
    st.sidebar.warning(f"Activities file not found at {HUGIM_CSV}")

# Load preferences
if PREFERENCES_CSV.exists():
    with st.spinner("Loading camper preferences..."):
        load_camper_preferences(PREFERENCES_CSV)
else:
    st.sidebar.warning(f"Preferences file not found at {PREFERENCES_CSV}")

# Mark state as loaded
st.session_state.state_loaded = True

# Save the state after loading
save_state()

def show_dashboard():
    st.title("Hugim Allocation Admin")
    

    # Show data overview
    show_data_overview()
    
    # File uploaders
    st.header("Upload Data")
    
    # Activities upload
    st.subheader("1. Upload Activities (CSV)")
    activities_file = st.file_uploader(
        "Upload Activities CSV", 
        type=["csv"], 
        key="activities_uploader"
    )
    
    if activities_file is not None:
        # Save the uploaded file
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_uploaded_file(activities_file, HUGIM_CSV)
        
        # Load the activities
        with st.spinner("Loading activities..."):
            load_activities(HUGIM_CSV)
    
    # Show loaded activities info
    if 'hugim_data' in st.session_state and st.session_state.hugim_data:
        total_activities = sum(len(acts) for acts in st.session_state.hugim_data.values())
        st.success(f"✅ Loaded {total_activities} activities across {len(st.session_state.hugim_data)} periods")
    
    # Preferences upload
    st.subheader("2. Upload Camper Preferences (CSV)")
    preferences_file = st.file_uploader(
        "Upload Preferences CSV", 
        type=["csv"], 
        key="preferences_uploader"
    )
    
    if preferences_file is not None:
        # Save the uploaded file
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_uploaded_file(preferences_file, PREFERENCES_CSV)
        
        # Load the preferences
        with st.spinner("Loading camper preferences..."):
            load_camper_preferences(PREFERENCES_CSV)
    
    # Show loaded campers info
    if 'campers' in st.session_state and st.session_state.campers:
        st.success(f"✅ Loaded preferences for {len(st.session_state.campers)} campers")
    
    # Run allocation button
    if st.button("Run Allocation"):
        if not st.session_state.hugim_data or not st.session_state.campers:
            st.error("Please load both activities and camper preferences first.")
        else:
            with st.spinner("Running allocation..."):
                try:
                    # Convert data to format expected by the allocator
                    periods = []
                    for period_name, activities in st.session_state.hugim_data.items():
                        period = Period(period_name)
                        for activity_name, details in activities.items():
                            activity = Activity(activity_name, details['capacity'], details['min'], periods=[period_name])
                            period.add_activity(activity)
                        periods.append(period)
                    
                    # Create campers with preferences
                    campers = []
                    for camper_data in st.session_state.campers:
                        camper = Camper(camper_data['CamperID'])
                        for period_name, prefs in camper_data['preferences'].items():
                            camper.set_preferences(period_name, prefs)
                        campers.append(camper)
                    
                    # Run allocation
                    results = run_allocation(campers, periods)
                    
                    # Update session state with assignments
                    for camper_data, camper in zip(st.session_state.campers, campers):
                        for period in st.session_state.mapping["Periods"]:
                            assignment = camper.get_assignment(period)
                            if assignment:
                                camper_data['assignments'][period] = {
                                    'hug': assignment.activity.name,
                                    'how': assignment.method
                                }
                    
                    save_state()  # Save state after allocation
                    st.toast("Allocation completed successfully!", icon="✅")
                except Exception as e:
                    st.error(f"Error during allocation: {e}")
    
    # Tabs for viewing and editing data
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard",
        "Activities View", 
        "Edit Activities", 
        "Camper Preferences", 
        "Edit Campers"
    ])
    
    with tab1:
        show_statistics()
    
    with tab2:
        show_activities_table()
    
    with tab3:
        show_activity_editor()
    
    with tab4:
        show_camper_preferences()
        
    with tab5:
        show_camper_editor()

def main():
    """Main entry point for the admin dashboard"""
    initialize_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        st.title("Login")
        password = st.text_input("Enter password", type="password")
        if st.button("Login"):
            if password == "admin123":  # In a real app, use proper authentication
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        return
    
    # Add a logout button in the sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.state_loaded = False
            st.rerun()
    
    show_dashboard()

if __name__ == "__main__":
    main()
