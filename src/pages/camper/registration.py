import streamlit as st
from pathlib import Path
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

# Page configuration is handled in app.py
def load_activities() -> Dict[str, Dict]:
    """Load activities from the latest allocation output"""
    output_dir = Path("data/output")
    activities_file = output_dir / "activities.json"
    
    if activities_file.exists():
        with open(activities_file, 'r') as f:
            return json.load(f)
    return {}

def save_preferences(camper_id: str, preferences: Dict[str, List[str]]):
    """Save camper preferences to a file"""
    output_dir = Path("data/camper_preferences")
    output_dir.mkdir(exist_ok=True)
    
    pref_data = {
        "camper_id": camper_id,
        "timestamp": datetime.now().isoformat(),
        "preferences": preferences
    }
    
    with open(output_dir / f"{camper_id}.json", 'w') as f:
        json.dump(pref_data, f)

def registration_form():
    """Display the camper registration form"""
    st.title("Camper Registration")
    
    # Load activities
    activities = load_activities()
    if not activities:
        st.warning("No activities available yet. Please check back later.")
        return
    
    # Camper information
    st.header("Your Information")
    camper_id = st.text_input("Camper ID")
    name = st.text_input("Full Name")
    
    if not camper_id or not name:
        st.warning("Please enter your camper ID and name to continue.")
        return
    
    # Preferences section
    st.header("Activity Preferences")
    st.info("Please select your top 3 preferences for each period.")
    
    preferences = {}
    periods = ["Aleph", "Beth", "Gimmel"]
    
    for period in periods:
        st.subheader(f"{period} Period")
        period_activities = [
            name for name, details in activities.get(period, {}).items() 
            if details.get("is_active", True)
        ]
        
        if not period_activities:
            st.warning(f"No activities available for {period} period.")
            continue
            
        # Allow selecting up to 3 preferences per period
        selected = st.multiselect(
            f"Select your top 3 preferences for {period}",
            period_activities,
            max_selections=3,
            key=f"prefs_{period}"
        )
        preferences[period] = selected
    
    # Submit button
    if st.button("Submit Preferences"):
        if any(len(prefs) > 0 for prefs in preferences.values()):
            save_preferences(camper_id, preferences)
            st.success("Your preferences have been saved!")
            
            # Show confirmation
            st.subheader("Your Selections")
            for period, prefs in preferences.items():
                if prefs:
                    st.write(f"**{period}:** {', '.join(prefs)}")
        else:
            st.error("Please select at least one preference.")

def main():
    # Initialize session state with default values if they don't exist
    if 'camper_authenticated' not in st.session_state:
        st.session_state.camper_authenticated = False
    if 'camper_id' not in st.session_state:
        st.session_state.camper_id = None
    
    # Simple authentication check (can be enhanced)
    if not st.session_state.get('camper_authenticated', False):
        st.title("Camper Login")
        camper_id = st.text_input("Enter Your Camper ID")
        if st.button("Continue"):
            if camper_id:
                st.session_state.camper_authenticated = True
                st.session_state.camper_id = camper_id
                st.rerun()
            else:
                st.warning("Please enter a valid Camper ID")
        return
    
    # Show registration form
    registration_form()
    
    # Logout button
    if st.button("Logout"):
        st.session_state.camper_authenticated = False
        st.session_state.camper_id = None
        st.rerun()

if __name__ == "__main__":
    main()
