"""Statistics components for the Hugim allocation system."""
import streamlit as st
from typing import Dict, List, Any, Tuple
import pandas as pd
import plotly.express as px

def show_activity_statistics() -> None:
    """Show statistics about activities and their enrollment."""
    if not st.session_state.hugim_data:
        st.info("No activities loaded. Please upload an activities file first.")
        return
    
    st.header("Activity Statistics")
    
    # Prepare data for visualization
    activity_data = []
    for period, activities in st.session_state.hugim_data.items():
        for activity, details in activities.items():
            enrolled = len(details.get('enrolled', []))
            capacity = details.get('capacity', 0)
            utilization = (enrolled / capacity * 100) if capacity > 0 else 0
            
            activity_data.append({
                'Activity': activity,
                'Period': period,
                'Enrolled': enrolled,
                'Capacity': capacity,
                'Available': max(0, capacity - enrolled),
                'Utilization %': utilization,
                'Is Full': enrolled >= capacity
            })
    
    if not activity_data:
        st.info("No activity data available.")
        return
    
    df = pd.DataFrame(activity_data)
    
    # Overall statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Activities", len(df))
    with col2:
        st.metric("Total Capacity", df['Capacity'].sum())
    with col3:
        st.metric("Total Enrolled", df['Enrolled'].sum())
    
    # Activity utilization by period
    st.subheader("Activity Utilization by Period")
    if len(df) > 0:
        fig = px.bar(
            df, 
            x='Activity', 
            y='Utilization %',
            color='Period',
            barmode='group',
            title='Activity Utilization by Period',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Show detailed table
    st.subheader("Detailed Activity Data")
    st.dataframe(
        df,
        column_config={
            'Activity': st.column_config.TextColumn("Activity", width="medium"),
            'Period': st.column_config.TextColumn("Period", width="small"),
            'Enrolled': st.column_config.NumberColumn("Enrolled", width="small"),
            'Capacity': st.column_config.NumberColumn("Capacity", width="small"),
            'Available': st.column_config.NumberColumn("Available", width="small"),
            'Utilization %': st.column_config.ProgressColumn(
                "Utilization %",
                format="%.1f%%",
                min_value=0,
                max_value=100,
                width="medium"
            ),
            'Is Full': st.column_config.CheckboxColumn("Full?")
        },
        hide_index=True,
        use_container_width=True
    )

def show_camper_statistics() -> None:
    """Show statistics about campers and their preferences."""
    if not st.session_state.campers:
        st.info("No camper data available. Please upload a preferences file first.")
        return
    
    st.header("Camper Statistics")
    
    # Count preferences per camper
    preference_counts = []
    for camper in st.session_state.campers:
        prefs = camper.get('preferences', {})
        pref_count = sum(len(p) for p in prefs.values())
        preference_counts.append({
            'Camper ID': camper['CamperID'],
            'Preferences Count': pref_count
        })
    
    if not preference_counts:
        st.info("No preference data available.")
        return
    
    df = pd.DataFrame(preference_counts)
    
    # Overall statistics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Campers", len(df))
    with col2:
        avg_prefs = df['Preferences Count'].mean()
        st.metric("Avg. Preferences per Camper", f"{avg_prefs:.1f}")
    
    # Preferences distribution
    st.subheader("Preferences Distribution")
    if len(df) > 0:
        fig = px.histogram(
            df, 
            x='Preferences Count',
            title='Number of Preferences per Camper',
            labels={'Preferences Count': 'Number of Preferences'},
            nbins=10
        )
        st.plotly_chart(fig, use_container_width=True)

def show_statistics() -> None:
    """Main function to display all statistics."""
    tab1, tab2 = st.tabs(["Activity Statistics", "Camper Statistics"])
    
    with tab1:
        show_activity_statistics()
    
    with tab2:
        show_camper_statistics()
