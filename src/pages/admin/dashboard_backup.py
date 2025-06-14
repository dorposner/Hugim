import sys
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

# Function definitions

def load_activities(file_path: Path) -> None:
    """Load activities from a CSV file and update session state"""
    try:
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
                "NumPreferences": 5
            }
            
        st.session_state.hugim_data = load_hugim(file_path, st.session_state.mapping)
        save_state()  # Save state after loading activities
        st.toast(f"Successfully loaded {sum(len(acts) for acts in st.session_state.hugim_data.values())} activities")
    except Exception as e:
        st.error(f"Error loading activities: {e}")

def load_camper_preferences(file_path: Path) -> None:
    """Load camper preferences from a CSV file and update session state"""
    try:
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
                "NumPreferences": 5
            }
            
        campers = load_preferences(file_path, st.session_state.mapping)
        if campers:
            st.session_state.campers = campers
            save_state()  # Save state after loading campers
            st.toast(f"Successfully loaded preferences for {len(campers)} campers")
    except Exception as e:
        st.error(f"Error loading preferences: {e}")

# Initialize session state
initialize_session_state()

# Debug info
st.sidebar.subheader("Debug Info")
st.sidebar.write(f"Current working directory: {Path.cwd()}")
st.sidebar.write(f"HUGIM_CSV exists: {HUGIM_CSV.exists()} at {HUGIM_CSV}")
st.sidebar.write(f"PREFERENCES_CSV exists: {PREFERENCES_CSV.exists()} at {PREFERENCES_CSV}")

# Try to load saved state if not already loaded
if not st.session_state.get('state_loaded'):
    st.sidebar.write("Attempting to load saved state...")
    state_loaded = load_state()
    st.sidebar.write(f"State loaded: {state_loaded}")
    
    if state_loaded:
        st.session_state.state_loaded = True
        st.toast("Loaded previous application state", icon="✅")
        
        # Try to reload the last used files
        try:
            if HUGIM_CSV.exists():
                st.sidebar.write("Loading activities from:", HUGIM_CSV)
                with st.spinner("Reloading activities..."):
                    load_activities(HUGIM_CSV)
            else:
                st.sidebar.warning("Activities file not found")
                
            if PREFERENCES_CSV.exists():
                st.sidebar.write("Loading preferences from:", PREFERENCES_CSV)
                with st.spinner("Reloading camper preferences..."):
                    load_camper_preferences(PREFERENCES_CSV)
            else:
                st.sidebar.warning("Preferences file not found")
                
        except Exception as e:
            st.error(f"Error reloading data: {e}")
            st.exception(e)
    else:
        st.sidebar.warning("No saved state found or error loading state")

# State loading and saving are handled by the imported functions

def load_state() -> bool:
    """Load application state from disk if available."""
    state_path = STATE_FILE.absolute()
    st.sidebar.write(f"Looking for state file at: {state_path}")
    
    if not state_path.exists():
        st.sidebar.warning(f"State file not found at {state_path}")
        return False
        
    try:
        st.sidebar.write("Loading state from:", state_path)
        with open(state_path, 'rb') as f:
            state = pickle.load(f)
            
        # Debug: Show what's in the state
        st.sidebar.write("State keys:", list(state.keys()))
        
        # Verify file hashes if files exist
        if 'file_hashes' in state:
            st.sidebar.write("Found file hashes in state")
            
            # Check if we have file paths in the state
            if 'file_paths' in state:
                hugim_path = Path(state['file_paths']['hugim'])
                prefs_path = Path(state['file_paths']['preferences'])
            else:
                # Fallback to default paths
                hugim_path = Path("data/uploads/hugim.csv")
                prefs_path = Path("data/uploads/preferences.csv")
            
            st.sidebar.write(f"Looking for hugim at: {hugim_path}")
            st.sidebar.write(f"Looking for prefs at: {prefs_path}")
            
            if hugim_path.exists() and prefs_path.exists():
                hugim_hash = compute_file_hash(hugim_path)
                prefs_hash = compute_file_hash(prefs_path)
                
                if (hugim_hash and hugim_hash != state['file_hashes'].get('hugim', '')) or \
                   (prefs_hash and prefs_hash != state['file_hashes'].get('preferences', '')):
                    st.warning("Data files have changed since last save. Loading saved state but you may want to re-upload files.")
        
        # Restore session state
        for key, value in state.items():
            if key not in ['file_hashes', 'file_paths']:  # Don't restore internal state
                st.session_state[key] = value
                
        st.sidebar.success("State loaded successfully")
        return True
        
    except Exception as e:
        st.sidebar.error(f"Error loading saved state: {e}", exc_info=True)
        return False

def save_state() -> None:
    """Save the current application state to disk."""
    if 'hugim_data' not in st.session_state or 'campers' not in st.session_state:
        st.sidebar.warning("Cannot save state: missing required data")
        return False
        
    try:
        # Ensure state directory exists
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Get absolute paths
        hugim_path = Path("data/uploads/hugim.csv").absolute()
        prefs_path = Path("data/uploads/preferences.csv").absolute()
        
        state = {
            'hugim_data': st.session_state.hugim_data,
            'campers': st.session_state.campers,
            'mapping': st.session_state.mapping,
            'file_hashes': {
                'hugim': compute_file_hash(hugim_path) if hugim_path.exists() else "",
                'preferences': compute_file_hash(prefs_path) if prefs_path.exists() else "",
            },
            'file_paths': {
                'hugim': str(hugim_path),
                'preferences': str(prefs_path)
            }
        }
        
        # Save state
        with open(STATE_FILE, 'wb') as f:
            pickle.dump(state, f)
            
        st.sidebar.success(f"State saved to {STATE_FILE.absolute()}")
        return True
        
    except Exception as e:
        st.sidebar.error(f"Error saving state: {e}")
        return False

def load_activities(file_path: Path) -> None:
    """Load activities from a CSV file and update session state"""
    try:
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
                "NumPreferences": 5
            }
            
        st.session_state.hugim_data = load_hugim(file_path, st.session_state.mapping)
        save_state()  # Save state after loading activities
        st.toast(f"Successfully loaded {sum(len(acts) for acts in st.session_state.hugim_data.values())} activities")
    except Exception as e:
        st.error(f"Error loading activities: {e}")

def load_camper_preferences(file_path: Path) -> None:
    """Load camper preferences from a CSV file and update session state"""
    try:
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
                "NumPreferences": 5
            }
            
        campers = load_preferences(file_path, st.session_state.mapping)
        if campers:
            st.session_state.campers = campers
            save_state()  # Save state after loading campers
            st.toast(f"Successfully loaded preferences for {len(campers)} campers")
    except Exception as e:
        st.error(f"Error loading preferences: {e}")

def show_dashboard():
    st.title("Hugim Allocation Admin")
    
    # Debug info
    st.sidebar.subheader("Session State")
    st.sidebar.json({
        'has_hugim_data': 'hugim_data' in st.session_state,
        'hugim_data_keys': list(st.session_state.get('hugim_data', {}).keys()) if 'hugim_data' in st.session_state else None,
        'has_campers': 'campers' in st.session_state,
        'num_campers': len(st.session_state.get('campers', [])),
        'has_mapping': 'mapping' in st.session_state,
        'mapping': st.session_state.get('mapping', {})
    })
    
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
                            activity = Activity(activity_name, details['capacity'], details['min'])
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "Activities View", 
        "Edit Activities", 
        "Camper Preferences", 
        "Edit Campers"
    ])
    
    with tab1:
        show_activities_table()
    
    with tab2:
        show_activity_editor()
    
    with tab3:
        show_camper_preferences()
        
    with tab4:
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
