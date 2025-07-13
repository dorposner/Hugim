import pandas as pd
import streamlit as st
from collections import defaultdict
import random

def find_missing(pref_df, hugim_df, hug_col="HugName"):
    # Find hugim mentioned in any preference but missing from hugim list
    hugim_set = set(hugim_df[hug_col].astype(str).str.strip())
    hug_names_in_prefs = set()
    for c in pref_df.columns:
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

def enforce_minimums_cancel_and_reallocate(campers, hugim):
    import streamlit as st
    canceled_hugs_by_period = {period: set() for period in hugim}
    changes = True
    while changes:
        changes = False
        # 1. Check each period for canceled Hugim
        for period in list(hugim.keys()):
            under_minimum = []
            for hug_name in list(hugim[period].keys()):
                info = hugim[period][hug_name]
                if len(info['enrolled']) < info['min']:
                    under_minimum.append(hug_name)
            # Cancel undersubscribed Hugim
            for hug_name in under_minimum:
                # Remove campers from these hugs (set assignments to None)
                for camper in campers:
                    assn = camper['assignments'][period]
                    if assn['hug'] == hug_name:
                        assn['hug'] = None
                        assn['how'] = None
                # Remove the hug from the structure
                del hugim[period][hug_name]
                canceled_hugs_by_period[period].add(hug_name)
                changes = True  # We made a change, may need another reallocation round
        # 2. Redistribute unassigned campers (who lost their hug, or started unassigned)
        for p_idx, period in enumerate(hugim):
            for camper in campers:
                if camper['assignments'][period]['hug'] is None:
                    # Try to allocate using next available preference
                    for pref_index, pref in enumerate(camper['preferences'][period]):
                        # Skip any canceled hugs in this period
                        if pref in canceled_hugs_by_period[period]:
                            continue
                        if (pref in hugim[period] and
                            len(hugim[period][pref]['enrolled']) < hugim[period][pref]['capacity'] and
                            # Check for uniqueness constraint, i.e., not already assigned in other period:
                            all(assn['hug'] != pref for p2, assn in camper['assignments'].items() if p2 != period)
                        ):
                            camper['assignments'][period]['hug'] = pref
                            # Set the preference rank instead of "Reallocated"
                            camper['assignments'][period]['how'] = f'Pref_{pref_index + 1}'
                            hugim[period][pref]['enrolled'].add(camper['CamperID'])
                            break  # assigned

    # --- Final reporting, show which hugs were canceled
    for period, canceled in canceled_hugs_by_period.items():
        for hug in canceled:
            try:
                st.warning(f"Hug '{hug}' in period '{period}' was canceled (did not meet minimum). Campers were re-allocated.")
            except Exception:
                print(f"Warning: Hug '{hug}' in period '{period}' was canceled (did not meet minimum).")

def fill_minimums(campers, hugim):
    # aggregate Hug assignments over all periods
    # Step 1: Calculate total assigned per Hug, and store (hug: set of assigned camperIDs)
    hug_to_campers = defaultdict(set)
    camper_lookup = {camper['CamperID']: camper for camper in campers}
    for period in hugim:
        for hug in hugim[period]:
            hug_to_campers[hug].update(hugim[period][hug]['enrolled'])
    # Step 2: Figure out each Hug's minimum
    # For consistency, just get minimum from first period we find it in (should be same for all its instances)
    hug_minimums = {}
    for period in hugim:
        for hug in hugim[period]:
            hug_minimums[hug] = hugim[period][hug]['min']
    # Step 3: For all hugs, ensure enough campers
    for hug, required_min in hug_minimums.items():
        have_now = len(hug_to_campers[hug])
        if have_now >= required_min:
            continue
        missing = required_min - have_now
        # Find unassigned campers (in any period), or campers with lowest satisfaction for this hug
        available_campers = []
        # 1st: campers totally unassigned to this hug in any period
        for camper in campers:
            if camper['CamperID'] not in hug_to_campers[hug]:
                available_campers.append(camper)
        random.shuffle(available_campers)
        # 2nd: now for each available camper, try to add them to the hug in any period where space allows 
        for camper in available_campers:
            periods_with_room = [period for period in hugim if hug in hugim[period] and
                                 len(hugim[period][hug]['enrolled']) < hugim[period][hug]['capacity']]
            for period in periods_with_room:
                assn = camper['assignments'][period]['hug']
                if assn is None:
                    # Easy: assign to this hug
                    camper['assignments'][period]['hug'] = hug
                    camper['assignments'][period]['how'] = 'Forced_minimum'
                    hugim[period][hug]['enrolled'].add(camper['CamperID'])
                    hug_to_campers[hug].add(camper['CamperID'])
                    missing -= 1
                    break
            if missing <= 0:
                break
        # If still missing, consider swapping out lowest-preference assignments
        # This code can be extended for more advanced heuristics (swap lowest-satisfaction assignees etc).
        if missing > 0:
            warning_msg = f"Unable to meet minimum for hug '{hug}'; need {missing} more."
            print("Warning:", warning_msg)
        try:
            st.warning(warning_msg)
        except Exception:
            # If not running in Streamlit, just ignore
            pass
            
def get_unassignment_reason(campers, camper_idx, period, hugim_for_period):
    """Returns a reason for why the camper cannot be assigned in this period."""
    camper = campers[camper_idx]
    # 1. Are there any Hugim offered this period?
    if not hugim_for_period:
        return "No activities offered in this period."

    # 2. All Hugim at capacity?
    available = [hug for hug, info in hugim_for_period.items() if len(info["enrolled"]) < info["capacity"]]
    if not available:
        return "All activities full in this period."

    # 3. Preference/duplication constraint prevents assignment?
    preferences = camper["preferences"][period]
    period_names = camper["assignments"].keys()
    def already_has_hug(hug):
        return any(
            camper["assignments"][p]["hug"] == hug
            for p in period_names
            if camper["assignments"][p]["hug"] is not None and p != period
        )
    # List Hugs available and not duplicated
    assignable = [hug for hug in available if not already_has_hug(hug)]
    if not assignable:
        return "No activity available without repeating across periods."

    # 4. Just couldn't match preference
    if not preferences:
        return "No preferences listed for this period."
    preferred_and_available = [hug for hug in preferences if hug in assignable]
    if not preferred_and_available:
        return "Preferences not available (full, not offered, or duplicate)."

    # 5. Fallback reason
    return "Unknown reason (please report)."
