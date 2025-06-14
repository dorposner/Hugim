"""Reusable UI components for the Hugim allocation system."""
import streamlit as st
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd

def show_data_overview() -> None:
    """Show the data overview section with metrics."""
    st.header("Data Overview")
    col1, col2 = st.columns(2)
    
    with col1:
        # Get all unique activity names across all periods
        unique_activities = set()
        for period_activities in st.session_state.hugim_data.values():
            if isinstance(period_activities, dict):
                unique_activities.update(period_activities.keys())
        st.metric("Activities Loaded", len(unique_activities))
    
    with col2:
        # Get unique camper IDs
        if isinstance(st.session_state.campers, list):
            camper_ids = {str(camper.get('CamperID', '')) 
                         for camper in st.session_state.campers 
                         if camper and camper.get('CamperID')}
            camper_count = len(camper_ids)
        else:
            camper_count = 0
        st.metric("Campers Loaded", camper_count)

def show_activities_table() -> None:
    """Show a sortable table of all activities."""
    if not st.session_state.hugim_data:
        st.info("No activities loaded. Please upload an activities file first.")
        return
    
    # Prepare data for display
    activities = []
    for period, period_activities in st.session_state.hugim_data.items():
        for activity, details in period_activities.items():
            enrolled = len(details['enrolled'])
            capacity = details['capacity']
            activities.append({
                'Activity': activity,
                'Period': period,
                'Capacity': capacity,
                'Minimum': details['min'],
                'Enrolled': enrolled,
                'Remaining': capacity - enrolled,
                'Utilization': (enrolled / capacity * 100) if capacity > 0 else 0
            })
    
    if not activities:
        st.info("No activities found in the loaded data.")
        return
    
    # Sort activities
    sort_by = st.selectbox(
        "Sort by",
        ["Activity (A-Z)", "Activity (Z-A)", "Period", "Enrolled (High-Low)", "Enrolled (Low-High)"],
        key="activity_sort"
    )
    
    if sort_by == "Activity (A-Z)":
        activities.sort(key=lambda x: x['Activity'].lower())
    elif sort_by == "Activity (Z-A)":
        activities.sort(key=lambda x: x['Activity'].lower(), reverse=True)
    elif sort_by == "Period":
        activities.sort(key=lambda x: (x['Period'], x['Activity']))
    elif sort_by == "Enrolled (High-Low)":
        activities.sort(key=lambda x: x['Enrolled'], reverse=True)
    elif sort_by == "Enrolled (Low-High)":
        activities.sort(key=lambda x: x['Enrolled'])
    
    # Format the utilization as percentage
    df = pd.DataFrame(activities)
    df['Utilization'] = df['Utilization'].apply(lambda x: f"{x:.1f}%")
    
    # Display as a table with better formatting
    st.dataframe(
        df[['Activity', 'Period', 'Capacity', 'Minimum', 'Enrolled', 'Remaining', 'Utilization']],
        use_container_width=True,
        column_config={
            'Activity': st.column_config.TextColumn("Activity Name", width="medium"),
            'Period': st.column_config.TextColumn("Period", width="small"),
            'Capacity': st.column_config.NumberColumn("Capacity", width="small"),
            'Minimum': st.column_config.NumberColumn("Minimum", width="small"),
            'Enrolled': st.column_config.NumberColumn("Enrolled", width="small"),
            'Remaining': st.column_config.NumberColumn("Remaining", width="small"),
            'Utilization': st.column_config.TextColumn("Utilization", width="small")
        },
        hide_index=True
    )

def show_camper_preferences() -> None:
    """Show a table of camper preferences."""
    if not st.session_state.campers:
        st.info("No camper preferences loaded yet.")
        return
    
    # Prepare data for display
    display_data = []
    for camper in st.session_state.campers[:100]:  # Limit to first 100 campers for performance
        camper_data = {'Camper ID': camper['CamperID']}
        
        # Add preferences for each period
        for period in st.session_state.mapping["Periods"]:
            prefs = camper['preferences'].get(period, [])
            # Show preferences as a comma-separated list with their ranks
            pref_str = ", ".join([f"{i+1}. {pref}" for i, pref in enumerate(prefs)])
            camper_data[f"{period} Preferences"] = pref_str
        
        display_data.append(camper_data)
    
    if not display_data:
        st.warning("No preference data to display.")
        return
    
    # Display as a table
    df = pd.DataFrame(display_data)
    
    # Reorder columns to have Camper ID first, then periods in order
    columns = ['Camper ID'] + [f"{period} Preferences" for period in st.session_state.mapping["Periods"]]
    df = df[columns]
    
    # Display the table with better formatting
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            'Camper ID': st.column_config.TextColumn("Camper ID", width="medium"),
            **{f"{period} Preferences": st.column_config.TextColumn(
                f"{period} Preferences", 
                width="large",
                help=f"{period} preferences in order of priority"
            ) for period in st.session_state.mapping["Periods"]}
        },
        hide_index=True
    )
    
    # Show total count
    st.caption(f"Showing {len(display_data)} campers. " + 
              ("(Limited to first 100 campers)" if len(st.session_state.campers) > 100 else ""))