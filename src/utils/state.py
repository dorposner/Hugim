"""State management utilities for the Hugim allocation system."""
import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import streamlit as st

# State persistence paths
STATE_DIR = Path("data/state")
STATE_FILE = STATE_DIR / "app_state.pkl"

# Ensure state directory exists
STATE_DIR.mkdir(parents=True, exist_ok=True)

def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        return ""

def save_state() -> None:
    """Save the current application state to disk."""
    try:
        # Always save the current state
        state = {
            'hugim_data': st.session_state.get('hugim_data', {}),
            'campers': st.session_state.get('campers', []),
            'mapping': st.session_state.get('mapping', {
                "HugName": "HugName",
                "Capacity": "Capacity",
                "Minimum": "Minimum",
                "Periods": ["Aleph", "Beth", "Gimmel"],
                "NumPreferences": 5
            }),
            'file_hashes': {
                'hugim': compute_file_hash(Path("data/uploads/hugim.csv")),
                'preferences': compute_file_hash(Path("data/uploads/preferences.csv")),
            },
        }
        
        # Ensure the directory exists
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the state
        with open(STATE_FILE, 'wb') as f:
            pickle.dump(state, f)
    except Exception as e:
        st.warning(f"Could not save application state: {e}")

def load_state() -> bool:
    """Load application state from disk if available."""
    if not STATE_FILE.exists():
        st.sidebar.warning("No saved state file found")
        return False
        
    try:
        with open(STATE_FILE, 'rb') as f:
            state = pickle.load(f)
        
        # Always load the state, but mark that we need to reload from CSV
        st.session_state.hugim_data = state.get('hugim_data', {})
        st.session_state.campers = state.get('campers', [])
        st.session_state.mapping = state.get('mapping', {
            "HugName": "HugName",
            "Capacity": "Capacity",
            "Minimum": "Minimum",
            "Periods": ["Aleph", "Beth", "Gimmel"],
            "NumPreferences": 5
        })
        
        st.sidebar.success("Loaded previous state from disk")
        return True
            
    except Exception as e:
        st.sidebar.warning(f"Could not load application state: {e}")
        return False

def initialize_session_state() -> None:
    """Initialize all session state variables with default values."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'hugim_data' not in st.session_state:
        st.session_state.hugim_data = {}
    if 'campers' not in st.session_state:
        st.session_state.campers = []
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
    if 'state_loaded' not in st.session_state:
        st.session_state.state_loaded = False