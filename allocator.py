# allocator.py
#
# --------------------------------------------------------------
#  Simple Hugim Allocation Proof-of-Concept
#  • Reads campers, hugim (activities), and camper preferences
#  • Gives each camper exactly 3 different hugim if possible
#  • Five preference rounds (pref-1 … pref-5) + random fill
#  • Writes results and prints a short console summary
# --------------------------------------------------------------

import os
import random
from collections import defaultdict

import pandas as pd

# ---------------------------- CONFIG ---------------------------

NUM_ASSIGNMENTS_TARGET = 3      # each camper needs 3 hugim
PREFERENCES_PER_CAMPER = 5      # max preference columns in preferences.csv

CAMPERS_DATA_FILE      = 'campers.csv'
HUGIM_DATA_FILE        = 'hugim.csv'
PREFERENCES_DATA_FILE  = 'preferences.csv'

OUTPUT_ASSIGNMENTS_FILE = 'assignments_output.csv'
OUTPUT_STATS_FILE       = 'stats_output.csv'
OUTPUT_UNASSIGNED_FILE  = 'unassigned_campers_output.csv'

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ----------------------- DATA LOADERS --------------------------

def load_hugim(path: str) -> dict:
    """
    Returns {hug_name: {'capacity': int, 'enrolled': set(), 'age_group': str}}
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Hugim file not found: {path}')

    df = pd.read_csv(path)
    if 'HugName' not in df.columns or 'Capacity' not in df.columns or 'AgeGroup' not in df.columns:
        df.columns = ['HugName', 'Capacity', 'AgeGroup']   # fallback header

    hugim = {}
    for _, row in df.iterrows():
        name = str(row['HugName']).strip()
        if not name:
            continue
        try:
            cap = int(row['Capacity'])
        except ValueError:
            continue
        age_group = str(row['AgeGroup']).strip().capitalize()  # "Younger", "Older", or "All"
        hugim[name] = dict(
            capacity=cap,
            enrolled=set(),
            age_group=age_group
        )
    return hugim


def load_campers(path: str) -> dict:
    """
    Returns {camper_id: {'missed_first': bool, 'needs': 3,
                         'assigned': [], 'preferences': [], 'age_group': str}}
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Campers file not found: {path}')

    df = pd.read_csv(path)
    if 'CamperID' not in df.columns or 'Got1stChoiceLastWeek' not in df.columns or 'AgeGroup' not in df.columns:
        df.columns = ['CamperID', 'Got1stChoiceLastWeek', 'AgeGroup']

    campers = {}
    for _, row in df.iterrows():
        cid = str(row['CamperID']).strip()
        if not cid:
            continue
        missed = str(row['Got1stChoiceLastWeek']).strip().upper() != 'YES'
        age_group = str(row['AgeGroup']).strip().capitalize()  # "Younger" or "Older"
        campers[cid] = dict(
            missed_first=missed,
            needs=NUM_ASSIGNMENTS_TARGET,
            assigned=[],
            preferences=[],
            age_group=age_group
        )
    return campers


def load_preferences(path: str, campers: dict) -> None:
    """
    Fills campers[cid]['preferences'] with a list (up to 5 entries).
    Ignores duplicates and unknown campers.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f'Preferences file not found: {path}')

    df = pd.read_csv(path)
    pref_cols = df.columns[1:1 + PREFERENCES_PER_CAMPER]

    for _, row in df.iterrows():
        cid = str(row.iloc[0]).strip()
        if cid not in campers:
            continue
        prefs = []
        for col in pref_cols:
            if col not in row or pd.isna(row[col]):
                continue
            val = str(row[col]).strip()
            if val and val not in prefs:       # dedupe
                prefs.append(val)
        campers[cid]['preferences'] = prefs

# --------------------- ALLOCATION ENGINE -----------------------

def preference_round(campers: dict, hugim: dict, pref_idx: int) -> None:
    """One pass: everyone’s N-th choice, considering age group compatibility."""
    from collections import defaultdict
    applicants = defaultdict(list)  # {hug: [camper_id]}
    for cid, data in campers.items():
        if data['needs'] == 0:
            continue
        if pref_idx >= len(data['preferences']):
            continue
        hug = data['preferences'][pref_idx]
        if hug not in hugim:
            continue
        if hug in [h for h, _ in data['assigned']]:
            continue
        # Age group check!
        camper_age = data['age_group']
        hug_age = hugim[hug]['age_group']
        if hug_age != "All" and hug_age != camper_age:
            continue
        applicants[hug].append(cid)

    for hug, demanders in applicants.items():
        spots = hugim[hug]['capacity'] - len(hugim[hug]['enrolled'])
        if spots <= 0:
            continue

        # fairness: missed_first campers first, then random
        random.shuffle(demanders)
        demanders.sort(key=lambda c: 0 if campers[c]['missed_first'] else 1)

        winners = demanders[:spots]
        for cid in winners:
            campers[cid]['assigned'].append((hug, f'Pref_{pref_idx+1}'))
            campers[cid]['needs'] -= 1
            hugim[hug]['enrolled'].add(cid)


def random_fill(campers: dict, hugim: dict) -> None:
    seats = []
    for hug, info in hugim.items():
        seats.extend([hug] * (info['capacity'] - len(info['enrolled'])))
    random.shuffle(seats)

    for cid, data in campers.items():
        seat_idx = 0
        while data['needs'] > 0 and seat_idx < len(seats):
            hug = seats[seat_idx]
            seat_idx += 1
            if hug in [h for h, _ in data['assigned']]:
                continue
            # Age group check!
            camper_age = data['age_group']
            hug_age = hugim[hug]['age_group']
            if hug_age != "All" and hug_age != camper_age:
                continue
            campers[cid]['assigned'].append((hug, 'Random'))
            campers[cid]['needs'] -= 1
            hugim[hug]['enrolled'].add(cid)


def run_allocation(campers: dict, hugim: dict) -> None:
    for i in range(PREFERENCES_PER_CAMPER):
        preference_round(campers, hugim, i)
    random_fill(campers, hugim)

# ----------------------- OUTPUT HELPERS ------------------------

def save_assignments(campers: dict, path: str) -> None:
    rows = []
    headers = ['CamperID'] + [f'Hug_{i+1}' for i in range(NUM_ASSIGNMENTS_TARGET)]
    for cid, data in campers.items():
        hugs_only = [h for h, _ in data['assigned']]
        rows.append([cid] + hugs_only + [''] * (NUM_ASSIGNMENTS_TARGET - len(hugs_only)))
    pd.DataFrame(rows, columns=headers).to_csv(path, index=False)


def save_unassigned(campers: dict, path: str) -> None:
    unassigned = []
    for cid, data in campers.items():
        if data['needs'] > 0:
            unassigned.append([cid,
                               NUM_ASSIGNMENTS_TARGET - data['needs'],
                               data['needs']])
    if unassigned:
        pd.DataFrame(unassigned,
                     columns=['CamperID', 'AssignmentsReceived', 'StillNeeded']
                     ).to_csv(path, index=False)


def save_stats(campers: dict, hugim: dict, path: str) -> None:
    import pandas as pd

    # Key stats
    total_slots = sum(len(d['assigned']) for d in campers.values())
    full_campers = sum(1 for d in campers.values() if d['needs'] == 0)
    assignments_per_camper = [len(d['assigned']) for d in campers.values()]
    min_assigned = min(assignments_per_camper) if assignments_per_camper else 0
    max_assigned = max(assignments_per_camper) if assignments_per_camper else 0
    avg_assigned = (
        sum(assignments_per_camper) / len(assignments_per_camper)
        if assignments_per_camper else 0
    )

    first_choice_count = 0
    second_choice_count = 0
    third_choice_count = 0
    random_count = 0

    # 1. Campers who got NO choices
    campers_no_choices = 0
    for d in campers.values():
        assigned_types = [how for _, how in d['assigned']]
        if assigned_types and all(x == 'Random' for x in assigned_types):
            campers_no_choices += 1
        for h, how_assigned in d['assigned']:
            if how_assigned == 'Pref_1':
                first_choice_count += 1
            elif how_assigned == 'Pref_2':
                second_choice_count += 1
            elif how_assigned == 'Pref_3':
                third_choice_count += 1
            elif how_assigned == 'Random':
                random_count += 1

    stats = [
        ['Total campers', len(campers)],
        ['Total hugim', len(hugim)],
        ['Total assigned slots', total_slots],
        ['Campers fully assigned', full_campers],
        ['Percent fully assigned', f'{full_campers/len(campers)*100:.1f}%'],
        ['Average assignments per camper', f'{avg_assigned:.2f}'],
        ['Minimum assignments to a camper', min_assigned],
        ['Maximum assignments to a camper', max_assigned],
        ['Assignments as 1st choice', first_choice_count],
        ['Assignments as 2nd choice', second_choice_count],
        ['Assignments as 3rd choice', third_choice_count],
        ['Assignments by random fill', random_count],
        ['Campers who got NONE of their preferences', campers_no_choices],
    ]

    # 2. Hugim not full/empty stats and per-Hug table
    per_hug_rows = []
    not_full = 0
    empty = 0

    # Collect preference requests: {hug: set of camper IDs who requested it}
    requests = {hug: set() for hug in hugim}
    for cid, cdata in campers.items():
        for pref in cdata['preferences']:
            if pref in requests:
                requests[pref].add(cid)

    for hug, info in hugim.items():
        allocated = len(info['enrolled'])
        capacity = info['capacity']
        requested = len(requests[hug])
        free = capacity - allocated
        status = "Full" if allocated == capacity else ("Empty" if allocated == 0 else "Not full")
        if allocated == 0:
            empty += 1
        if allocated < capacity:
            not_full += 1
        per_hug_rows.append([
            hug,
            allocated,
            requested,
            free,
            capacity,
            status
        ])

    # Now add the new stats to the main stats table
    stats += [
        ['Hugim not full', not_full],
        ['Empty hugim', empty],
    ]

    # Write two CSVs (recommended), or write stats then per-hug breakdown to the same file (not a real CSV, but demo):
    stats_df = pd.DataFrame(stats, columns=['Stat', 'Value'])
    per_hug_df = pd.DataFrame(per_hug_rows, columns=['HugName', 'Allocated', 'Requested', 'Free Spots', 'Capacity', 'Status'])

    # Option 1: Save as two files:
    stats_df.to_csv(path, index=False)
    per_hug_df.to_csv(path.replace('.csv', '_hugim.csv'), index=False)

    # Option 2: Or (less recommended) save both in the same file, with a blank line in between for manual reading:
    # with open(path, 'w', encoding='utf-8') as f:
    #     stats_df.to_csv(f, index=False)
    #     f.write('\n')
    #     per_hug_df.to_csv(f, index=False)

# ----------------------------- MAIN ----------------------------

def main() -> None:
    print('Loading data …')
    hugim   = load_hugim(HUGIM_DATA_FILE)
    campers = load_campers(CAMPERS_DATA_FILE)
    load_preferences(PREFERENCES_DATA_FILE, campers)

    print('Running allocation …')
    run_allocation(campers, hugim)

    print('Saving results …')
    save_assignments(campers, OUTPUT_ASSIGNMENTS_FILE)
    save_unassigned(campers, OUTPUT_UNASSIGNED_FILE)
    save_stats(campers, hugim, OUTPUT_STATS_FILE)

    # quick console summary
    full = sum(1 for d in campers.values() if d['needs'] == 0)
    print(f'✓ Done.  {full}/{len(campers)} campers got all '
          f'{NUM_ASSIGNMENTS_TARGET} hugim.')

if __name__ == '__main__':
    main()
