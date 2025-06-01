import pandas as pd
import streamlit as st

PERIODS = ["Aleph", "Beth", "Gimmel"]
PREFERENCES_PER_PERIOD = 5

def find_missing(pref_df, hugim_df):
    # Check hug names referenced in any preferences columns for all periods
    hugim_set = set(hugim_df['HugName'].astype(str).str.strip())
    hug_names_in_prefs = set()
    for period in PERIODS:
        for i in range(1, PREFERENCES_PER_PERIOD + 1):
            col = f"{period}_{i}"
            if col in pref_df.columns:
                hug_names_in_prefs.update(pref_df[col].dropna().astype(str).str.strip())
    missing_hugim = sorted(hug_names_in_prefs - hugim_set)
    return missing_hugim   # campers are never missing in new approach

def show_uploaded(st, label, uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        st.write(f"**Preview of {label}:**")
        st.dataframe(df)
        return df
    except Exception as e:
        st.error(f"Could not read {label}: {e}")
        return None

def validate_csv_headers(hugim_df, prefs_df):
    hugim_headers = set(hugim_df.columns)
    # Must have HugName, Capacity, Aleph, Beth, Gimmel
    if not {'HugName', 'Capacity', 'Aleph', 'Beth', 'Gimmel'}.issubset(hugim_headers):
        return False, "hugim.csv must contain: HugName, Capacity, Aleph, Beth, Gimmel"
    # preferences.csv: must have CamperID and at least Aleph_1, Beth_1, Gimmel_1
    if 'CamperID' not in prefs_df.columns:
        return False, "preferences.csv must contain a 'CamperID' column."
    for period in PERIODS:
        if f"{period}_1" not in prefs_df.columns:
            return False, f"preferences.csv must have '{period}_1' column."
    return True, ""

def to_csv_download(df, filename, label):
    csv = df.to_csv(index=False)
    st.download_button(f"Download edited {label}", csv, file_name=filename, mime="text/csv")
