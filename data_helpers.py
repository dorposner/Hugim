import pandas as pd

def find_missing(pref_df, campers_df, hugim_df):
    campers_set = set(campers_df['CamperID'].astype(str).str.strip())
    prefs_set = set(pref_df['CamperID'].astype(str).str.strip())
    missing_campers = sorted(prefs_set - campers_set)

    hugim_set = set(hugim_df['HugName'].astype(str).str.strip())
    pref_cols = [c for c in pref_df.columns if c.startswith("Pref")]
    hug_names_in_prefs = set()
    for c in pref_cols:
        hug_names_in_prefs.update(pref_df[c].dropna().astype(str).str.strip())
    missing_hugim = sorted(hug_names_in_prefs - hugim_set)

    return missing_campers, missing_hugim

def show_uploaded(st, label, uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        st.write(f"**Preview of {label}:**")
        st.dataframe(df)
        return df
    except Exception as e:
        st.error(f"Could not read {label}: {e}")
        return None

def validate_csv_headers(campers_df, hugim_df, prefs_df):
    """
    Checks that all input DataFrames have required columns.
    Returns (ok:bool, error_message:str)
    """
    campers_headers = set(campers_df.columns)
    hugim_headers = set(hugim_df.columns)
    
    if not {'CamperID', 'Got1stChoiceLastWeek'}.issubset(campers_headers):
        return False, "campers.csv must contain: CamperID, Got1stChoiceLastWeek"
    if not {'HugName', 'Capacity'}.issubset(hugim_headers):
        return False, "hugim.csv must contain: HugName, Capacity"
    if 'CamperID' not in prefs_df.columns:
        return False, "preferences.csv must contain a 'CamperID' column."
    return True, ""
