"""Data loading and saving utilities for the Hugim allocation system."""
import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import csv

# File paths
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

HUGIM_CSV = UPLOAD_DIR / "hugim.csv"
PREFERENCES_CSV = UPLOAD_DIR / "preferences.csv"

def save_uploaded_file(uploaded_file, save_path: Path) -> None:
    """Save an uploaded file to the specified path."""
    try:
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    except Exception as e:
        st.error(f"Error saving file: {e}")
        raise

def load_hugim(file_path: Path, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Load activities data from a CSV file."""
    try:
        st.write(f"Loading activities from: {file_path}")
        st.write(f"Using mapping: {mapping}")
        
        # Read CSV with error handling
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            st.error(f"Error reading CSV file: {e}")
            return {period: {} for period in mapping.get("Periods", ["Aleph", "Beth", "Gimmel"])}
            
        st.write(f"Loaded CSV with columns: {df.columns.tolist()}")
        
        # Convert column names to strings in case they're not
        df.columns = df.columns.astype(str)
        
        # Get required columns
        name_col = str(mapping.get("HugName", "")).strip()
        capacity_col = str(mapping.get("Capacity", "")).strip()
        min_col = str(mapping.get("Minimum", "")).strip()
        
        # Check if required columns exist
        missing_cols = []
        if not name_col or name_col not in df.columns:
            missing_cols.append(f"Name column ('{name_col}')")
        if not capacity_col or capacity_col not in df.columns:
            missing_cols.append(f"Capacity column ('{capacity_col}')")
        if not min_col or min_col not in df.columns:
            missing_cols.append(f"Minimum column ('{min_col}')")
            
        if missing_cols:
            st.error(f"Missing required columns in CSV: {', '.join(missing_cols)}")
            return {}
        
        periods = mapping.get("Periods", ["Aleph", "Beth", "Gimmel"])
        hugim = {period: {} for period in periods}
        
        # Debug: Show first few rows
        st.write("First few rows of the CSV:")
        st.write(df.head())
        
        for _, row in df.iterrows():
            try:
                name = str(row[name_col]).strip()
                if not name or pd.isna(name):
                    st.warning(f"Skipping row with empty name: {row}")
                    continue
                    
                capacity = int(float(row[capacity_col]))
                minimum = int(float(row[min_col]))
                
                # Find which periods this activity is available in
                for period in periods:
                    # Try different column naming patterns
                    period_patterns = [
                        period,  # Exact period name
                        f"{period} Available",
                        f"Available {period}",
                        f"{period}_Available",
                        f"Available_{period}",
                        f"{period}Active",
                        f"Active{period}",
                        f"{period}_Active",
                        f"Active_{period}",
                    ]
                    
                    # Check if any of the patterns match a column
                    period_col = next((col for col in df.columns if col in period_patterns), None)
                    
                    if period_col and pd.notna(row.get(period_col)):
                        # Check if the value indicates availability
                        val = str(row[period_col]).strip().lower()
                        if val in ['1', 'true', 'yes', 'y', 'available', 'active']:
                            hugim[period][name] = {
                                'capacity': capacity,
                                'min': minimum,
                                'enrolled': set()
                            }
            except Exception as e:
                st.warning(f"Error processing row {_}: {e}")
                continue
        
        # Debug: Show loaded data
        st.write("Successfully loaded activities:")
        for period, activities in hugim.items():
            st.write(f"{period}: {len(activities)} activities")
            
        return hugim
        
    except Exception as e:
        st.error(f"Error loading activities: {e}")
        st.exception(e)
        return {period: {} for period in mapping.get("Periods", ["Aleph", "Beth", "Gimmel"])}

def load_preferences(file_path: Path, mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load camper preferences from a CSV file."""
    try:
        st.write(f"Loading preferences from: {file_path}")
        
        # Read CSV with error handling
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            st.error(f"Error reading preferences CSV: {e}")
            return []
            
        st.write(f"Loaded preferences CSV with columns: {df.columns.tolist()}")
        
        # Convert column names to strings in case they're not
        df.columns = df.columns.astype(str)
        
        # Debug: Show first few rows
        st.write("First few rows of preferences:")
        st.write(df.head())
        
        campers = []
        num_prefs = mapping.get("NumPreferences", 5)
        periods = mapping.get("Periods", ["Aleph", "Beth", "Gimmel"])
        
        # Find the CamperID column (try multiple possible names)
        camper_id_cols = [
            'CamperID', 'Camper ID', 'ID', 'camper_id', 'Camper',
            'Participant', 'ParticipantID', 'Participant ID', 'participant_id'
        ]
        
        # Find the first matching column (case insensitive)
        camper_id_col = None
        for col in camper_id_cols:
            if col in df.columns:
                camper_id_col = col
                break
        
        if not camper_id_col:
            st.error("Could not find a valid Camper ID column in the CSV")
            st.write("Tried column names:", camper_id_cols)
            return []
            
        st.write(f"Using '{camper_id_col}' as the Camper ID column")
        
        for _, row in df.iterrows():
            try:
                camper_id = str(row[camper_id_col]).strip()
                if not camper_id or pd.isna(camper_id):
                    st.warning(f"Skipping row with empty CamperID: {row}")
                    continue
                    
                preferences = {}
                for period in periods:
                    # Get period prefix from mapping or use period name
                    period_prefix = mapping.get("PeriodPrefixes", {}).get(period, period)
                    
                    # Look for preference columns with various naming patterns
                    found_prefs = []
                    
                    # Try different patterns for preference columns
                    for i in range(1, num_prefs + 1):
                        # Try different column name patterns
                        possible_cols = [
                            # Standard patterns
                            f"{period}_Pref_{i}",
                            f"{period}Pref{i}",
                            f"{period} Pref {i}",
                            f"{period_prefix}_Pref_{i}",
                            f"{period_prefix}Pref{i}",
                            f"{period_prefix} Pref {i}",
                            
                            # More flexible patterns
                            f"{period}_{i}",
                            f"{period} {i}",
                            f"{period_prefix}_{i}",
                            f"{period_prefix} {i}",
                            
                            # With different capitalization
                            f"{period.upper()}_PREF_{i}",
                            f"{period.upper()}_CHOICE_{i}",
                            f"{period.title()} Preference {i}",
                            f"{period.title()} Choice {i}"
                        ]
                        
                        # Find the first matching column with a non-empty value
                        for col in possible_cols:
                            if col in row and pd.notna(row[col]) and str(row[col]).strip():
                                pref_value = str(row[col]).strip()
                                if pref_value:  # Only add non-empty preferences
                                    found_prefs.append(pref_value)
                                break  # Move to next preference number
                    
                    # Only add period if we found preferences
                    if found_prefs:
                        preferences[period] = found_prefs
                
                # Only add camper if they have at least one preference
                if preferences:
                    campers.append({
                        'CamperID': camper_id,
                        'preferences': preferences,
                        'assignments': {}
                    })
                else:
                    st.warning(f"Camper {camper_id} has no valid preferences and was skipped")
                    
            except Exception as e:
                st.warning(f"Error processing camper row {_}: {e}")
                continue
        
        if not campers:
            st.error("No valid campers found in the preferences file")
        else:
            st.success(f"Successfully loaded {len(campers)} campers with preferences")
        
        return campers
        
    except Exception as e:
        st.error(f"Error loading preferences: {e}")
        st.exception(e)
        return []

def save_activities_to_csv(hugim_data: Dict[str, Any], output_path: Path) -> None:
    """Save activities data to a CSV file."""
    try:
        # Convert the nested dict to a list of rows
        rows = []
        for period, activities in hugim_data.items():
            for name, details in activities.items():
                rows.append({
                    'HugName': name,
                    'Capacity': details['capacity'],
                    'Minimum': details['min'],
                    period: 'Yes'
                })
        
        # Convert to DataFrame and save
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False)
            
    except Exception as e:
        st.error(f"Error saving activities: {e}")
        raise