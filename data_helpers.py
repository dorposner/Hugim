import pandas as pd
import streamlit as st

def find_missing(pref_df, hugim_df):
    # Find hugim mentioned in any preference but missing from hugim list
    hugim_set = set(hugim_df['HugName'].astype(str).str.strip())
    pref_cols = [c for c in pref_df.columns if any(c.startswith(f"{period}_") for period in ["Aleph", "Beth", "Gimmel"])]
    hug_names_in_prefs = set()
    for c in pref_cols:
        hug_names_in_prefs.update(pref_df[c].dropna().astype(str).str.strip())
    missing_hugim = sorted(hug_names_in_prefs - hugim_set)
    return missing_hugim

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
    if not {'HugName', 'Capacity', 'Aleph', 'Beth', 'Gimmel'}.issubset(hugim_df.columns):
        return False, "hugim.csv must contain: HugName, Capacity, Aleph, Beth, Gimmel"
    if 'CamperID' not in prefs_df.columns:
        return False, "preferences.csv must contain a 'CamperID' column."
    expected_pref_cols = [f"{period}_{i}" for period in ["Aleph", "Beth", "Gimmel"] for i in range(1,6)]
    if not any(col in prefs_df.columns for col in expected_pref_cols):
        return False, "preferences.csv must contain preference columns like Aleph_1,...,Beth_5,Gimmel_5."
    return True, ""

def to_csv_download(df, filename, label):
    csv = df.to_csv(index=False)
    st.download_button(f"Download edited {label}", csv, file_name=filename, mime="text/csv")
