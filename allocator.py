import random
from collections import defaultdict
import pandas as pd
from pathlib import Path   # <<<< Add this!

from data_helpers import fill_minimums
from data_helpers import get_unassignment_reason

PERIODS = None
PREFERENCES_PER_PERIOD = 5

HUGIM_DATA_FILE = 'hugim.csv'
PREFERENCES_DATA_FILE = 'preferences.csv'

OUTPUT_ASSIGNMENTS_FILE = Path("assignments_output.csv")    # <<<< CHANGE TO PATH
OUTPUT_STATS_FILE = Path("stats_output.csv")                # <<<< CHANGE TO PATH
OUTPUT_UNASSIGNED_FILE = Path("unassigned_campers_output.csv")   # <<<< CHANGE TO PATH

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ------------- FLEXIBLE DATA LOADERS ----------------

def load_hugim(path: str, mapping: dict):
    """
    Loads hugim/activity information from a CSV.
    Returns:
        dict of the form:
        {period: {hug_name: {'capacity': int, 'min': int, 'enrolled': set()}}}
    Skips any row with a non-integer Capacity or Minimum value, reporting the row.
    """
    import pandas as pd
    import streamlit as st  # or fallback to print below if not in Streamlit

    df = pd.read_csv(path)
    periods = mapping["Periods"]
    hugim = {period: {} for period in periods}
    rows_skipped = 0

    for i, row in df.iterrows():
        name = str(row[mapping["HugName"]]).strip()
        raw_capacity = row[mapping["Capacity"]]
        raw_min = row[mapping["Minimum"]]
        # Try casting Capacity and Minimum columns to integer
        try:
            cap = int(float(str(raw_capacity).strip()))
            min_cap = int(float(str(raw_min).strip()))
            if cap < 0 or min_cap < 0:
                raise ValueError
        except Exception:
            try:
                st.warning(f"Row {i+1} ('{name}') skipped: Capacity or Minimum not a valid integer "
                           f"(Capacity: {raw_capacity!r}, Minimum: {raw_min!r})")
            except Exception:
                print(f"Row {i+1} ('{name}') skipped: Capacity or Minimum not a valid integer "
                      f"(Capacity: {raw_capacity!r}, Minimum: {raw_min!r})")
            rows_skipped += 1
            continue

        for period in periods:
            value = row[period]
            offered = False
            try:
                if str(value).strip().lower() in {"1", "true", "yes"}:
                    offered = True
                elif isinstance(value, (int, float)) and value > 0:
                    offered = True
                elif str(value).strip() not in {"", "0", "false", "no", "nan"}:
                    # Accept e.g. literal TRUE case-insensitive
                    if str(value).strip().lower() in {"y", "t"}:
                        offered = True
            except Exception:
                pass
            if offered:
                hugim[period][name] = {
                    'capacity': cap,
                    'min': min_cap,
                    'enrolled': set()
                }

    if rows_skipped > 0:
        try:
            st.warning(f"{rows_skipped} activities were skipped due to invalid Capacity or Minimum values.")
        except Exception:
            print(f"{rows_skipped} activities were skipped due to invalid Capacity or Minimum values.")

    return hugim

def load_preferences(path: str, mapping: dict):
    """
    Returns: list of { 'CamperID': str, 'preferences': {period: [h1, h2, ...]}, ... }
    mapping: {"CamperID": ..., "PeriodPrefixes": {period_col: prefix_in_preferences_file}}
    """
    df = pd.read_csv(path)
    period_map = mapping["PeriodPrefixes"]  # e.g. {'Aleph': 'A', ...}

    campers = []
    max_pref_count = 0
    for prefix in period_map.values():
        prefs = [col for col in df.columns if col.startswith(prefix+'_')]
        max_pref_count = max(max_pref_count, len(prefs))
    global PREFERENCES_PER_PERIOD
    PREFERENCES_PER_PERIOD = max_pref_count

    # Check if "score" column exists (case-insensitive)
    score_column = None
    for col in df.columns:
        if col.lower() == "score":
            score_column = col
            break

    for _, row in df.iterrows():
        camper_id = str(row[mapping["CamperID"]]).strip()
        preferences = {}
        for period, prefix in period_map.items():
            prefs = []
            for i in range(1, PREFERENCES_PER_PERIOD+1):
                colname = f"{prefix}_{i}"
                if colname in row and pd.notna(row[colname]):
                    hug = str(row[colname]).strip()
                    if hug and hug not in prefs:
                        prefs.append(hug)
            preferences[period] = prefs

        # NEW: Load score if present
        score_val = 0
        if score_column is not None:
            try:
                csv_val = row[score_column]
                if pd.notna(csv_val):
                    score_val = float(csv_val)
            except Exception:
                score_val = 0

        campers.append({
            'CamperID': camper_id,
            'preferences': preferences,
            'assignments': {period: {'hug': None, 'how': None} for period in period_map},
            'score_history': [score_val] if score_val else []  # <-- starts with previous score
        })
    global PERIODS
    PERIODS = list(period_map.keys())
    return campers

# ------------- ALLOCATION ENGINE --------------
            
def assign_period(campers, hugim_for_period, period):
    periods = list(campers[0]['assignments'].keys())

    # Gather all previous assignments for each camper for cross-period check
    def already_has_hug(camper, hug):
        return any(
            camper['assignments'][p]['hug'] == hug
            for p in periods
            if camper['assignments'][p]['hug'] is not None and p != period
        )

    unassigned = set(i for i, camper in enumerate(campers) if camper['assignments'][period]['hug'] is None)

    # ----------- SCORE PRIORITY SECTION -----------
    def get_total_score(camper):
        return sum(camper.get('score_history', [])) if 'score_history' in camper else 0
    unassigned_list = list(unassigned)
    unassigned_list.sort(key=lambda idx: get_total_score(campers[idx]))
    # ----------------------------------------------

    # Try top 3 preferences
    for pref_rank in range(3):
        demanders = defaultdict(list)
        for idx in unassigned_list:
            camper = campers[idx]
            prefs = camper['preferences'][period]
            if len(prefs) > pref_rank:
                hug = prefs[pref_rank]
                if (
                    hug in hugim_for_period
                    and not already_has_hug(camper, hug)
                ):
                    demanders[hug].append(idx)
        # Randomize order within each hug
        for hug in demanders:
            random.shuffle(demanders[hug])
        for hug, candidates in demanders.items():
            spots = hugim_for_period[hug]['capacity'] - len(hugim_for_period[hug]['enrolled'])
            take = candidates[:spots]
            for idx in take:
                campers[idx]['assignments'][period]['hug'] = hug
                campers[idx]['assignments'][period]['how'] = f'Pref_{pref_rank+1}'
                hugim_for_period[hug]['enrolled'].add(campers[idx]['CamperID'])
        unassigned_list = [i for i in unassigned_list if campers[i]['assignments'][period]['hug'] is None]
    # Try preferences 4-5 (or however many)
    for pref_rank in range(3, PREFERENCES_PER_PERIOD):
        demanders = defaultdict(list)
        for idx in unassigned_list:
            camper = campers[idx]
            prefs = camper['preferences'][period]
            if len(prefs) > pref_rank:
                hug = prefs[pref_rank]
                if (
                    hug in hugim_for_period 
                    and not already_has_hug(camper, hug)
                ):
                    demanders[hug].append(idx)
        for hug in demanders:
            random.shuffle(demanders[hug])
        for hug, candidates in demanders.items():
            spots = hugim_for_period[hug]['capacity'] - len(hugim_for_period[hug]['enrolled'])
            take = candidates[:spots]
            for idx in take:
                campers[idx]['assignments'][period]['hug'] = hug
                campers[idx]['assignments'][period]['how'] = f'Pref_{pref_rank+1}'
                hugim_for_period[hug]['enrolled'].add(campers[idx]['CamperID'])
        unassigned_list = [i for i in unassigned_list if campers[i]['assignments'][period]['hug'] is None]
    # Fill remaining campers randomly (but don't violate the "once only per week" rule)
    available_hugim = [hug for hug, info in hugim_for_period.items() if len(info['enrolled']) < info['capacity']]
    random.shuffle(available_hugim)
    for idx in unassigned_list:
        camper = campers[idx]
        # NEW: skip random assignment if camper has no preferences for this period
        if not camper["preferences"][period]:
            continue
        for hug in available_hugim:
            info = hugim_for_period[hug]
            if len(info['enrolled']) < info['capacity'] and not already_has_hug(camper, hug):
                campers[idx]['assignments'][period]['hug'] = hug
                campers[idx]['assignments'][period]['how'] = 'Random'
                info['enrolled'].add(camper['CamperID'])
                break
    for idx in unassigned_list:
        camper = campers[idx]
        if camper['assignments'][period]['hug'] is None:
            camper['assignments'][period]['how'] = get_unassignment_reason(campers, idx, period, hugim_for_period)
            
def calculate_and_store_weekly_scores(campers):
    """Calculates and stores a satisfaction score (higher=better) for each camper for this round."""
    PREF_POINTS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
    for camper in campers:
        score = 0
        for period, assignment in camper['assignments'].items():
            how = assignment['how']
            if how and how.startswith('Pref_'):
                n = int(how.split('_')[1])
                score += PREF_POINTS.get(n, 0)
            # You may also decide if you want to count 'Random', 'Forced_minimum', etc as 0
        camper['score_history'].append(score)

def run_allocation(campers, hugim):
    for period in PERIODS:
        assign_period(campers, hugim[period], period)
    fill_minimums(campers, hugim)

# ---------- OUTPUT HELPERS ------------

def save_assignments(campers, path):
    if not campers:
        return
    periods = list(campers[0]['assignments'].keys())
    # Collect column headers for assignment
    cols = (
        ['CamperID']
        + [f'{period}_Assigned' for period in periods]
        + [f'{period}_How' for period in periods]
        + ['Week_Score', 'Cumulative_Score']
    )
    rows = []
    for camper in campers:
        week_score = camper['score_history'][-1] if camper['score_history'] else 0
        cumulative_score = sum(camper['score_history'])
        row = [camper['CamperID']]
        row += [camper['assignments'][period]['hug'] or '' for period in periods]
        row += [camper['assignments'][period]['how'] or '' for period in periods]
        row += [week_score, cumulative_score]
        rows.append(row)
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)

def save_unassigned(campers, path):
    if not campers:
        return
    periods = list(campers[0]['assignments'].keys())
    unassigned = []
    for camper in campers:
        for period in periods:
            if camper['assignments'][period]['hug'] is None:
                # This guarantees a non-None reason
                reason = camper['assignments'][period].get('how') or ''
                unassigned.append([camper['CamperID'], period, reason])
    if unassigned:
        pd.DataFrame(unassigned, columns=['CamperID', 'Period', 'Reason']).to_csv(path, index=False)

def save_stats(campers, hugim, path):
    # Gather period list from campers object
    if not campers:
        return
    periods = list(campers[0]['assignments'].keys())
    total = len(campers) * len(periods)
    got = [0] * 6  # 1st,2nd,3rd,4th,5th,random
    unassigned = 0
    for camper in campers:
        for period in periods:
            how = camper['assignments'][period]['how']
            if how and how.startswith('Pref_'):
                try:
                    pref_num = int(how.split('_')[1])
                except Exception:
                    pref_num = 6  # place in "random" if error
                if 1 <= pref_num <= 5:
                    got[pref_num - 1] += 1
                else:
                    got[5] += 1
            elif how == 'Random':
                got[5] += 1
            else:
                unassigned += 1
    stats = [
        ['Total assignments needed', total],
        ['Got first choice', got[0]],
        ['Got second choice', got[1]],
        ['Got third choice', got[2]],
        ['Got fourth choice', got[3]],
        ['Got fifth choice', got[4]],
        ['Randomly assigned', got[5]],
        ['Unassigned', unassigned],
        ['Percent with top-3', f"{(got[0]+got[1]+got[2])/total*100:.1f}%"],
        ['Percent random', f"{got[5]/total*100:.1f}%"],
        ['Percent unassigned', f"{unassigned/total*100:.1f}%"]
    ]
    stats_df = pd.DataFrame(stats, columns=['Stat', 'Value'])
    stats_df.to_csv(path, index=False)

    # Hugim per-period breakdown
    for period in periods:
        per_hug = []
        for hug, info in hugim[period].items():
            per_hug.append([
                hug,
                len(info['enrolled']),
                info['capacity'],
                info['capacity'] - len(info['enrolled'])
            ])
        per_hug_df = pd.DataFrame(per_hug, columns=['HugName', 'Assigned', 'Capacity', 'Free'])
        per_hug_path = path.with_name(path.stem + f'_{period}_hugim.csv')
        per_hug_df.to_csv(per_hug_path, index=False)


# -------------- MAIN ----------------

def main():
    print('Loading data ...')
    # For CLI/manual runs, you’ll want to pass mappings or set up fixed ones
    # Here's a template (you can remove main if just using Streamlit)
    hugim_mapping = {
        "HugName": "HugName",
        "Capacity": "Capacity",
        "Periods": ["Aleph", "Beth", "Gimmel"]
    }
    prefs_mapping = {
        "CamperID": "CamperID",
        "PeriodPrefixes": {"Aleph": "Aleph", "Beth": "Beth", "Gimmel": "Gimmel"}
    }
    hugim = load_hugim(HUGIM_DATA_FILE, mapping=hugim_mapping)
    campers = load_preferences(PREFERENCES_DATA_FILE, mapping=prefs_mapping)

    print('Running allocation...')
    run_allocation(campers, hugim)

    print('Saving results...')
    save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
    save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
    save_stats(campers, hugim, OUTPUT_STATS_FILE)

    print(f"✓ Done. Assignment file: {OUTPUT_ASSIGNMENTS_FILE}")

if __name__ == '__main__':
    main()
