"""Data editing utilities for the Hugim allocation system."""
import streamlit as st
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import pandas as pd

from .loaders import save_activities_to_csv, HUGIM_CSV

def edit_activity(period: str, activity_name: str, activity_data: Dict[str, Any]) -> None:
    """Edit an existing activity."""
    with st.expander(f"Edit {activity_name}"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input("Activity Name", value=activity_name, key=f"name_{period}_{activity_name}")
            capacity = st.number_input(
                "Capacity", 
                min_value=1, 
                value=activity_data['capacity'],
                key=f"capacity_{period}_{activity_name}"
            )
            minimum = st.number_input(
                "Minimum", 
                min_value=0, 
                value=activity_data['min'],
                key=f"min_{period}_{activity_name}"
            )
        
        if st.button("Save Changes", key=f"save_{period}_{activity_name}"):
            if new_name != activity_name and new_name in st.session_state.hugim_data[period]:
                st.error(f"An activity named '{new_name}' already exists in {period}")
            else:
                # Update the activity
                if new_name != activity_name:
                    del st.session_state.hugim_data[period][activity_name]
                
                st.session_state.hugim_data[period][new_name] = {
                    'capacity': capacity,
                    'min': minimum,
                    'enrolled': activity_data['enrolled']
                }
                
                # Save to CSV
                save_activities_to_csv(st.session_state.hugim_data, HUGIM_CSV)
                st.success("Activity updated successfully!")
                st.rerun()
                
        # Add delete button with confirmation
        if st.button("Delete Activity", key=f"delete_{period}_{activity_name}", type="primary"):
            if st.session_state.get(f'confirm_delete_{period}_{activity_name}', False):
                # Remove the activity from all campers' preferences
                for camper in st.session_state.get('campers', []):
                    for p, prefs in camper.get('preferences', {}).items():
                        if activity_name in prefs:
                            prefs.remove(activity_name)
                    # Remove the period if no preferences left
                    if period in camper['preferences'] and not camper['preferences'][period]:
                        del camper['preferences'][period]
                
                # Remove the activity
                del st.session_state.hugim_data[period][activity_name]
                save_activities_to_csv(st.session_state.hugim_data, HUGIM_CSV)
                st.success(f"Activity '{activity_name}' deleted successfully!")
                st.session_state[f'confirm_delete_{period}_{activity_name}'] = False
                st.rerun()
            else:
                st.session_state[f'confirm_delete_{period}_{activity_name}'] = True
                st.warning("Click again to confirm deletion. This cannot be undone.")

def add_new_activity(period: str) -> None:
    """Add a new activity for a period."""
    with st.expander("Add New Activity", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Activity Name", key=f"new_activity_name_{period}")
            capacity = st.number_input(
                "Capacity", 
                min_value=1, 
                value=10, 
                key=f"new_capacity_{period}"
            )
            minimum = st.number_input(
                "Minimum", 
                min_value=0, 
                value=4, 
                key=f"new_min_{period}"
            )
        
        if st.button("Add Activity", key=f"add_{period}"):
            if not name:
                st.error("Please enter an activity name")
            elif name in st.session_state.hugim_data[period]:
                st.error(f"An activity named '{name}' already exists in {period}")
            else:
                st.session_state.hugim_data[period][name] = {
                    'capacity': capacity,
                    'min': minimum,
                    'enrolled': set()
                }
                
                # Save to CSV
                save_activities_to_csv(st.session_state.hugim_data, HUGIM_CSV)
                st.success(f"Added {name} to {period}")
                st.rerun()

def show_activity_editor() -> None:
    """Show the activity editor interface."""
    if not st.session_state.hugim_data:
        st.info("No activities loaded. Please upload an activities file first.")
        return
    
    st.header("Edit Activities")
    
    # Show activities by period
    for period, activities in st.session_state.hugim_data.items():
        st.subheader(f"{period} Activities")
        
        # Show existing activities
        if activities:
            for activity_name, activity_data in activities.items():
                edit_activity(period, activity_name, activity_data)
        else:
            st.info(f"No activities defined for {period}")
        
        # Add new activity
        add_new_activity(period)

def edit_camper_preferences(camper: Dict[str, Any]) -> None:
    """Edit a camper's preferences."""
    with st.expander(f"Edit {camper['CamperID']}"):
        new_prefs = {}
        
        # Ensure mapping exists and has required keys
        if 'mapping' not in st.session_state or 'Periods' not in st.session_state.mapping:
            st.warning("Please load the preferences file first to initialize the mapping.")
            return
            
        # Ensure NumPreferences is set, default to 5 if not
        num_prefs = st.session_state.mapping.get("NumPreferences", 5)
        
        # Display current preferences first
        st.subheader("Current Preferences")
        if 'preferences' in camper and camper['preferences']:
            for period, prefs in camper.get('preferences', {}).items():
                if prefs:  # Only show if there are preferences for this period
                    st.write(f"**{period}:** {', '.join(prefs) if prefs else 'No preferences set'}")
        else:
            st.info("No preferences set for this camper.")
        
        st.divider()
        st.subheader("Edit Preferences")
        
        for period in st.session_state.mapping["Periods"]:
            current_prefs = camper.get('preferences', {}).get(period, [])
            if not isinstance(current_prefs, list):
                current_prefs = []
                
            prefs = []
            
            st.write(f"**{period} Preferences**")
            
            # Get available activities for this period
            available_activities = sorted(st.session_state.get('hugim_data', {}).get(period, {}).keys())
            
            if not available_activities:
                st.warning(f"No activities available for {period}. Please add activities first.")
                continue
                
            for i in range(num_prefs):
                # Find the index of the current preference in available_activities
                current_pref = current_prefs[i] if i < len(current_prefs) else ""
                pref_index = 0
                if current_pref in available_activities:
                    pref_index = available_activities.index(current_pref) + 1  # +1 because of the empty first option
                    
                pref = st.selectbox(
                    f"Preference {i+1}",
                    options=[""] + available_activities,
                    index=pref_index,
                    key=f"{camper['CamperID']}_{period}_{i}",
                    disabled=not available_activities
                )
                if pref:  # Only add non-empty preferences
                    prefs.append(pref)
            
            if prefs:
                new_prefs[period] = prefs
        
        if st.button("Save Changes", key=f"save_{camper['CamperID']}"):
            camper['preferences'] = new_prefs
            st.success("Preferences updated!")
            st.rerun()
            
        # Add delete button with confirmation
        if st.button("Delete Camper", key=f"delete_{camper['CamperID']}", type="primary"):
            if st.session_state.get(f'confirm_delete_{camper["CamperID"]}', False):
                # Remove camper from activities' enrolled lists
                for period, activities in st.session_state.get('hugim_data', {}).items():
                    for activity_name, activity_data in activities.items():
                        if 'enrolled' in activity_data and camper['CamperID'] in activity_data['enrolled']:
                            activity_data['enrolled'].remove(camper['CamperID'])
                
                # Remove the camper
                st.session_state.campers = [c for c in st.session_state.campers if c['CamperID'] != camper['CamperID']]
                save_activities_to_csv(st.session_state.hugim_data, HUGIM_CSV)
                st.success(f"Camper '{camper['CamperID']}' deleted successfully!")
                st.session_state[f'confirm_delete_{camper["CamperID"]}'] = False
                st.rerun()
            else:
                st.session_state[f'confirm_delete_{camper["CamperID"]}'] = True
                st.warning("Click again to confirm deletion. This cannot be undone.")

def show_camper_editor() -> None:
    """Show the camper editor interface with search functionality."""
    # Check if we have the necessary data
    if 'hugim_data' not in st.session_state or not st.session_state.hugim_data:
        st.warning("Please load the activities file first.")
        return
        
    if 'campers' not in st.session_state or not st.session_state.campers:
        st.info("No campers loaded. Please upload a preferences file first.")
        return
        
    # Initialize mapping with defaults if not present
    if 'mapping' not in st.session_state:
        st.session_state.mapping = {
            "HugName": "HugName",
            "Capacity": "Capacity",
            "Minimum": "Minimum",
            "Periods": list(st.session_state.hugim_data.keys()),
            "NumPreferences": 5
        }
    
    st.header("Edit Camper Preferences")
    
    # Search box with clear button
    col1, col2 = st.columns([4, 1])
    with col1:
        search_term = st.text_input(
            "Search by Camper ID", 
            value="", 
            key="camper_search",
            placeholder="Enter camper ID..."
        )
    
    with col2:
        st.write("")
        clear_search = st.button("Clear")
        if clear_search:
            search_term = ""
            st.experimental_rerun()
    
    # Show search instructions
    st.caption("Start typing a camper ID to search. Leave empty to see all campers.")
    
    # Filter campers by search term (case-insensitive partial match)
    filtered_campers = [
        camper for camper in st.session_state.campers
        if not search_term or search_term.lower() in camper['CamperID'].lower()
    ]
    
    # Show number of matching campers
    if search_term and filtered_campers:
        st.success(f"Found {len(filtered_campers)} camper(s) matching '{search_term}'")
    
    # Show campers or no results message
    if not filtered_campers:
        if search_term:
            st.warning(f"No campers found matching '{search_term}'. Try a different search term.")
        else:
            st.info("No campers found. Please check your data.")
        return
    
    # Show campers in a clean section
    st.subheader(f"Matching Campers ({len(filtered_campers)})")
    for camper in filtered_campers:
        edit_camper_preferences(camper)