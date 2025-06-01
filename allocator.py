Great! Here’s a plan, followed by a **refactored version** of your `allocator.py` for your new system:

---

## **allocator.py changes required**
1. **Remove all age group logic (and ‘campers.csv’ usage).**
2. **Input will ONLY be:**
    - `hugim.csv` (containing per-period availability)
    - `preferences.csv` (5 ranked choices for each time period per camper: Aleph, Beth, Gimmel)
3. **Each Hug can run at Aleph, Beth, or Gimmel, possibly more than one period.**
4. **For each camper, assign ONE Hug per period (so 3 assignments/camper, one per timeslot).**
5. **Try to assign each camper each period to their top-3 preference for that period, subject to capacity.**
6. **Reporting/output should be per camper and per time period.**

---

Below is a **revised, self-contained `allocator.py`** with these requirements.  
**(You may need to update your helpers to match these interfaces!)**

---

```python
import os
import random
from collections import defaultdict
import pandas as pd

# ------------- CONFIG -------------
PERIODS = ['Aleph', 'Beth', 'Gimmel']
NUM_PERIODS = len(PERIODS)
PREFERENCES_PER_PERIOD = 5      # How many preferred choices per camper for each period
ASSIGNMENTS_PER_CAMPER = NUM_PERIODS  # Camper needs 1 hug per period

HUGIM_DATA_FILE        = 'hugim.csv'
PREFERENCES_DATA_FILE  = 'preferences.csv'

OUTPUT_ASSIGNMENTS_FILE = 'assignments_output.csv'
OUTPUT_STATS_FILE       = 'stats_output.csv'
OUTPUT_UNASSIGNED_FILE  = 'unassigned_campers_output.csv'

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ------------- DATA LOADERS ----------------

def load_hugim(path: str):
    """
    Returns: dict of form:
    {period: {hug_name: {'capacity': int, 'enrolled': set()}}}
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Hugim file not found: {path}')

    df = pd.read_csv(path)
    for col in ['HugName', 'Capacity']:
        if col not in df.columns:
            raise ValueError(f"Missing {col} in hugim.csv")

    # For each period, which hugim are possible & what's their capacity
    hugim = {period: {} for period in PERIODS}
    for _, row in df.iterrows():
        name = str(row['HugName']).strip()
        cap = int(row['Capacity'])
        for period in PERIODS:
            if period in row and int(row[period]) == 1:
                hugim[period][name] = {'capacity': cap, 'enrolled': set()}
    return hugim  # dict: period -> {hug_name: {capacity, enrolled}}

def load_preferences(path: str):
    """
    Returns: list of { 'CamperID': str, 'preferences': {period: [h1, h2, ... h5]} }
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Preferences file not found: {path}')
    df = pd.read_csv(path)
    campers = []
    for _, row in df.iterrows():
        camper_id = str(row['CamperID']).strip()
        preferences = {period: [] for period in PERIODS}
        for period in PERIODS:
            for i in range(1, PREFERENCES_PER_PERIOD+1):
                colname = f"{period}_{i}"
                if colname in row and pd.notna(row[colname]):
                    hug = str(row[colname]).strip()
                    if hug and hug not in preferences[period]:
                        preferences[period].append(hug)
        campers.append({
            'CamperID': camper_id,
            'preferences': preferences,
            'assignments': {period: {'hug': None, 'how': None} for period in PERIODS}
        })
    return campers

# ------------- ALLOCATION ENGINE --------------

def assign_period(campers, hugim_for_period, period):
    """
    campers: list of camper dicts
    hugim_for_period: {hug_name: {capacity, enrolled}}
    For this period:
    - Try to assign everyone to one hug from top-3 preferences, then from 4th/5th, then randomly.
    - Each camper gets at most one hug per period.
    """
    # Make a list of unassigned campers for this period
    unassigned = set(i for i, camper in enumerate(campers) if camper['assignments'][period]['hug'] is None)
    # Try top 3 preferences
    for pref_rank in range(3):
        demanders = defaultdict(list)  # hug_name -> [camper idx]
        for idx in unassigned:
            camper = campers[idx]
            prefs = camper['preferences'][period]
            if len(prefs) > pref_rank:
                hug = prefs[pref_rank]
                if hug in hugim_for_period:
                    demanders[hug].append(idx)
        # Randomize order within each hug
        for hug in demanders:
            random.shuffle(demanders[hug])
        # Assign as many as capacity allows
        for hug, candidates in demanders.items():
            spots = hugim_for_period[hug]['capacity'] - len(hugim_for_period[hug]['enrolled'])
            take = candidates[:spots]
            for idx in take:
                campers[idx]['assignments'][period]['hug'] = hug
                campers[idx]['assignments'][period]['how'] = f'Pref_{pref_rank+1}'
                hugim_for_period[hug]['enrolled'].add(campers[idx]['CamperID'])
        # Update unassigned list
        unassigned = set(i for i in unassigned if campers[i]['assignments'][period]['hug'] is None)
    # Try preferences 4-5
    for pref_rank in range(3, 5):
        demanders = defaultdict(list)
        for idx in unassigned:
            camper = campers[idx]
            prefs = camper['preferences'][period]
            if len(prefs) > pref_rank:
                hug = prefs[pref_rank]
                if hug in hugim_for_period:
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
        unassigned = set(i for i in unassigned if campers[i]['assignments'][period]['hug'] is None)
    # Fill remaining campers randomly
    available_hugim = [hug for hug, info in hugim_for_period.items() if len(info['enrolled']) < info['capacity']]
    random.shuffle(available_hugim)
    for idx in unassigned:
        for hug in available_hugim:
            info = hugim_for_period[hug]
            if len(info['enrolled']) < info['capacity']:
                campers[idx]['assignments'][period]['hug'] = hug
                campers[idx]['assignments'][period]['how'] = 'Random'
                info['enrolled'].add(campers[idx]['CamperID'])
                break

def run_allocation(campers, hugim):
    """Assign each camper in each period."""
    for period in PERIODS:
        assign_period(campers, hugim[period], period)

# ---------- OUTPUT HELPERS ------------

def save_assignments(campers, path):
    # One row per camper: CamperID, Aleph, Beth, Gimmel, Aleph_How, Beth_How, Gimmel_How
    rows = []
    cols = ['CamperID'] + [f'{period}_Assigned' for period in PERIODS] + [f'{period}_How' for period in PERIODS]
    for camper in campers:
        row = [camper['CamperID']]
        row += [camper['assignments'][period]['hug'] or '' for period in PERIODS]
        row += [camper['assignments'][period]['how'] or '' for period in PERIODS]
        rows.append(row)
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)

def save_unassigned(campers, path):
    unassigned = []
    for camper in campers:
        for period in PERIODS:
            if camper['assignments'][period]['hug'] is None:
                unassigned.append([camper['CamperID'], period])
    if unassigned:
        pd.DataFrame(unassigned, columns=['CamperID', 'Period']).to_csv(path, index=False)

def save_stats(campers, hugim, path):
    # Stats per period and overall
    total = len(campers) * len(PERIODS)
    got_1st = got_2nd = got_3rd = got_4th = got_5th = randomed = unassigned = 0
    for camper in campers:
        for period in PERIODS:
            how = camper['assignments'][period]['how']
            if how == 'Pref_1':
                got_1st += 1
            elif how == 'Pref_2':
                got_2nd += 1
            elif how == 'Pref_3':
                got_3rd += 1
            elif how == 'Pref_4':
                got_4th += 1
            elif how == 'Pref_5':
                got_5th += 1
            elif how == 'Random':
                randomed += 1
            else:
                unassigned += 1
    stats = [
        ['Total assignments needed', total],
        ['Got first choice', got_1st],
        ['Got second choice', got_2nd],
        ['Got third choice', got_3rd],
        ['Got fourth choice', got_4th],
        ['Got fifth choice', got_5th],
        ['Randomly assigned', randomed],
        ['Unassigned', unassigned],
        ['Percent with top-3', f"{(got_1st+got_2nd+got_3rd)/total*100:.1f}%"],
        ['Percent random', f"{randomed/total*100:.1f}%"],
        ['Percent unassigned', f"{unassigned/total*100:.1f}%"]
    ]
    stats_df = pd.DataFrame(stats, columns=['Stat', 'Value'])
    stats_df.to_csv(path, index=False)

    # Detailed Hugim usage table for each period
    for period in PERIODS:
        per_hug = []
        for hug, info in hugim[period].items():
            per_hug.append([
                hug,
                len(info['enrolled']),
                info['capacity'],
                info['capacity'] - len(info['enrolled'])
            ])
        per_hug_df = pd.DataFrame(per_hug, columns=['HugName', 'Assigned', 'Capacity', 'Free'])
        per_hug_df.to_csv(path.replace('.csv', f'_{period}_hugim.csv'), index=False)

# -------------- MAIN ----------------

def main():
    print('Loading data ...')
    hugim = load_hugim(HUGIM_DATA_FILE)
    campers = load_preferences(PREFERENCES_DATA_FILE)

    print('Running allocation...')
    run_allocation(campers, hugim)

    print('Saving results...')
    save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
    save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
    save_stats(campers, hugim, OUTPUT_STATS_FILE)

    print(f"✓ Done. Assignment file: {OUTPUT_ASSIGNMENTS_FILE}")

if __name__ == '__main__':
    main()
