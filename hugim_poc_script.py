import csv
import random
import os
import pandas as pd # Added pandas for better data handling and output
from collections import defaultdict

# --- Configuration ---
# Core Settings
NUM_ASSIGNMENTS_TARGET = 3 # How many Hugim each camper should be assigned
PREFERENCES_PER_CAMPER = 5 # How many preferences each camper submits

# Input Files (CSV format expected)
CAMPERS_DATA_FILE = 'campers.csv'
HUGIM_DATA_FILE = 'hugim.csv'
PREFERENCES_DATA_FILE = 'preferences.csv'

# Output Files
OUTPUT_ASSIGNMENTS_FILE = 'assignments_output.csv'
OUTPUT_STATS_FILE = 'stats_output.csv'
OUTPUT_UNASSIGNED_FILE = 'unassigned_campers_output.csv'

# Output Display Settings (for Colab/Terminal Summary)
NUM_ASSIGNMENTS_TO_PRINT = 15 # How many rows of assignments to print
NUM_UNASSIGNED_TO_PRINT = 15 # How many rows of unassigned campers to print

# --- Data Loading Functions ---

def load_hugim(filepath):
    """
    Loads Hugim data from a CSV file.
    Expected CSV format: HugName,Capacity
    Returns a dictionary: {hug_name: {'capacity': int, 'enrolled_campers': set()}}
    """
    hugim = {}
    if not os.path.exists(filepath):
        print(f"ERROR: Hugim data file not found at {filepath}")
        return None
    try:
        # Use pandas to read CSV, handles various encodings better
        df = pd.read_csv(filepath)
        df.columns = ['HugName', 'Capacity'] # Assume these are the first two columns
        print(f"Reading Hugim from {filepath} with header: {list(df.columns)}")
        for index, row in df.iterrows():
            hug_name = str(row['HugName']).strip()
            try:
                capacity = int(row['Capacity'])
                if hug_name and not pd.isna(row['HugName']):
                    hugim[hug_name] = {'capacity': capacity, 'enrolled_campers': set()}
                else:
                     print(f"Warning: Skipping row {index+2} with empty Hug name in {filepath}")
            except (ValueError, TypeError):
                print(f"Warning: Skipping row {index+2} with invalid capacity ('{row['Capacity']}') in {filepath}")
    except Exception as e:
        print(f"ERROR: Failed to read Hugim file {filepath}. Error: {e}")
        return None
    print(f"Loaded {len(hugim)} Hugim.")
    return hugim

def load_campers(filepath):
    """
    Loads camper data from a CSV file.
    Expected CSV format: CamperID,Got1stChoiceLastWeek (Yes/No)
    Returns a dictionary: {camper_id: {'got_1st_last_week': bool,
                                      'assigned_hugim': list(), # Now a list of tuples (hug_name, assignment_method)
                                      'preferences': list(),
                                      'needs_slots': NUM_ASSIGNMENTS_TARGET}}
    """
    campers = {}
    if not os.path.exists(filepath):
        print(f"ERROR: Campers data file not found at {filepath}")
        return None
    try:
        df = pd.read_csv(filepath)
        df.columns = ['CamperID', 'Got1stChoiceLastWeek'] # Assume these are the first two columns
        print(f"Reading Campers from {filepath} with header: {list(df.columns)}")
        for index, row in df.iterrows():
            camper_id = str(row['CamperID']).strip()
            got_1st_str = str(row['Got1stChoiceLastWeek']).strip().upper()
            got_1st = True if got_1st_str == 'YES' else False
            if camper_id and not pd.isna(row['CamperID']):
                campers[camper_id] = {
                    'got_1st_last_week': got_1st,
                    'assigned_hugim': [], # List of tuples: (hug_name, method)
                    'preferences': [],
                    'needs_slots': NUM_ASSIGNMENTS_TARGET
                }
            else:
                print(f"Warning: Skipping row {index+2} with empty CamperID in {filepath}")

    except Exception as e:
        print(f"ERROR: Failed to read Campers file {filepath}. Error: {e}")
        return None
    print(f"Loaded {len(campers)} campers.")
    return campers

def load_preferences(filepath, campers):
    """
    Loads camper preferences from a CSV file and adds them to the campers dict.
    Expected CSV format: CamperID,Pref1,Pref2,Pref3,Pref4,Pref5,... (up to PREFERENCES_PER_CAMPER)
    Updates the 'preferences' list in the campers dictionary.
    """
    if not campers:
        print("ERROR: Campers dictionary is empty, cannot load preferences.")
        return False
    if not os.path.exists(filepath):
        print(f"ERROR: Preferences data file not found at {filepath}")
        return False

    loaded_prefs_count = 0
    try:
        df = pd.read_csv(filepath)
        print(f"Reading Preferences from {filepath} with header: {list(df.columns)}")
        # Dynamically get preference column names (assuming they follow CamperID)
        pref_cols = df.columns[1:1 + PREFERENCES_PER_CAMPER]
        if len(pref_cols) < PREFERENCES_PER_CAMPER:
             print(f"Warning: Preferences file has fewer preference columns ({len(pref_cols)}) than configured ({PREFERENCES_PER_CAMPER}).")

        for index, row in df.iterrows():
             camper_id = str(row.iloc[0]).strip() # First column is CamperID
             if camper_id in campers:
                 prefs = [str(row[p]).strip() for p in pref_cols if p in row and not pd.isna(row[p]) and str(row[p]).strip()]
                 campers[camper_id]['preferences'] = prefs
                 loaded_prefs_count += 1
             else:
                 print(f"Warning: CamperID '{camper_id}' from preferences file (row {index+2}) not found in campers list. Skipping preferences.")
    except Exception as e:
        print(f"ERROR: Failed to read Preferences file {filepath}. Error: {e}")
        return False

    print(f"Loaded preferences for {loaded_prefs_count} campers.")
    missing_prefs = [cid for cid, data in campers.items() if not data['preferences']]
    if missing_prefs:
        print(f"Warning: {len(missing_prefs)} campers have no preferences loaded: {missing_prefs[:10]}...")
    return True


# --- Allocation Logic Functions ---

def run_preference_round(campers, hugim, preference_index, round_num):
    """
    Runs one round of allocation based on a specific preference level.
    Updates campers and hugim dictionaries in place.
    Stores the assignment method (e.g., 'Pref_1', 'Pref_2').
    """
    print(f"\n--- Running Preference Round {round_num} (Preference #{preference_index + 1}) ---")
    assignment_method = f"Pref_{preference_index + 1}"

    applicants_by_hug = defaultdict(list)
    assigned_hug_names_this_week = {cid: {assigned[0] for assigned in cdata['assigned_hugim']}
                                    for cid, cdata in campers.items()}

    for camper_id, camper_data in campers.items():
        if camper_data['needs_slots'] <= 0:
            continue

        if preference_index < len(camper_data['preferences']): 
            preferred_hug = camper_data['preferences'][preference_index]

            # Check if Hug exists and camper not already assigned this Hug
            if preferred_hug in hugim and preferred_hug not in assigned_hug_names_this_week.get(camper_id, set()):
                 applicants_by_hug[preferred_hug].append(
                     (camper_id, camper_data['needs_slots'], camper_data['got_1st_last_week'])
                 )

    print(f"Found applicants for {len(applicants_by_hug)} Hugim in this round.")

    processed_hug_count = 0
    assigned_count_round = 0
    sorted_hug_names = sorted(applicants_by_hug.keys())

    for hug_name in sorted_hug_names:
        applicants = applicants_by_hug[hug_name]
        hug_info = hugim[hug_name]
        available_spots = hug_info['capacity'] - len(hug_info['enrolled_campers'])
        demand = len(applicants)

        if available_spots <= 0:
            continue

        processed_hug_count += 1
        assigned_in_hug = 0
        winners = []

        if demand <= available_spots:
            winners = applicants
        else:
            applicants_with_random = [(app, random.random()) for app in applicants]
            applicants_with_random.sort(key=lambda x: (0 if not x[0][2] else 1, x[1]))
            winners_with_random = applicants_with_random[:available_spots]
            winners = [w[0] for w in winners_with_random]

        # Assign the winners
        for winner_data in winners:
            camper_id = winner_data[0]
            # Double check needs slots and not already assigned this hug
            current_assigned_hugs = {assigned[0] for assigned in campers[camper_id]['assigned_hugim']}
            if hug_name not in current_assigned_hugs and campers[camper_id]['needs_slots'] > 0:
                # Assign as tuple: (hug_name, method)
                campers[camper_id]['assigned_hugim'].append((hug_name, assignment_method))
                campers[camper_id]['needs_slots'] -= 1
                hugim[hug_name]['enrolled_campers'].add(camper_id) # Keep enrolled as set of IDs
                assigned_in_hug += 1

        if assigned_in_hug > 0:
             assigned_count_round += assigned_in_hug

    print(f"Processed {processed_hug_count} Hugim with applicants.")
    print(f"Assigned {assigned_count_round} spots in Preference Round {round_num}.")


def run_random_fill_round(campers, hugim):
    """
    Assigns remaining slots randomly. Stores assignment method as 'Random'.
    Updates campers and hugim dictionaries in place.
    """
    print("\n--- Running Random Filling Round ---")
    assignment_method = "Random"

    campers_needing_slots_list = [] # List of (camper_id, slots_needed)
    total_slots_needed = 0
    for camper_id, camper_data in campers.items():
        if camper_data['needs_slots'] > 0:
            campers_needing_slots_list.append((camper_id, camper_data['needs_slots']))
            total_slots_needed += camper_data['needs_slots']

    if not campers_needing_slots_list:
        print("No campers need additional slots. Skipping random fill.")
        return

    print(f"{len(campers_needing_slots_list)} campers need a total of {total_slots_needed} more slots.")

    available_spots_list = [] # List of (hug_name)
    total_available_spots = 0
    for hug_name, hug_info in hugim.items():
        available = hug_info['capacity'] - len(hug_info['enrolled_campers'])
        if available > 0:
            available_spots_list.extend([hug_name] * available)
            total_available_spots += available

    if not available_spots_list:
        print("No available spots in any Hugim. Cannot perform random fill.")
        return

    print(f"{total_available_spots} total spots available across all Hugim.")

    random.shuffle(campers_needing_slots_list)
    random.shuffle(available_spots_list)

    assigned_count_random = 0
    spot_idx = 0
    camper_idx = 0

    # Keep track of which campers we tried to assign in this pass to avoid infinite loops
    # if a camper cannot be assigned any remaining spot
    processed_in_pass = set()

    while total_slots_needed > 0 and spot_idx < len(available_spots_list):
        print(f"  Starting random assignment pass. Need to fill {total_slots_needed} slots. Available spots: {len(available_spots_list) - spot_idx}")
        slots_filled_this_pass = 0
        processed_in_pass.clear()

        # Iterate through campers *who still need slots*
        current_campers_needing = [c[0] for c in campers_needing_slots_list if campers[c[0]]['needs_slots'] > 0]
        random.shuffle(current_campers_needing) # Shuffle order for each pass

        camper_loop_idx = 0
        while camper_loop_idx < len(current_campers_needing) and spot_idx < len(available_spots_list):
            camper_id = current_campers_needing[camper_loop_idx]

            # Skip if already processed in this pass or no longer needs slots
            if camper_id in processed_in_pass or campers[camper_id]['needs_slots'] <= 0:
                camper_loop_idx += 1
                continue

            processed_in_pass.add(camper_id)
            current_assigned_hugs = {assigned[0] for assigned in campers[camper_id]['assigned_hugim']}

            # Try to find a suitable spot for this camper from the remaining shuffled spots
            assigned_spot_for_camper = False
            temp_spot_search_idx = spot_idx
            while temp_spot_search_idx < len(available_spots_list):
                potential_hug = available_spots_list[temp_spot_search_idx]

                if potential_hug not in current_assigned_hugs:
                     if len(hugim[potential_hug]['enrolled_campers']) < hugim[potential_hug]['capacity']:
                        # Assign!
                        campers[camper_id]['assigned_hugim'].append((potential_hug, assignment_method))
                        campers[camper_id]['needs_slots'] -= 1
                        hugim[potential_hug]['enrolled_campers'].add(camper_id)
                        assigned_count_random += 1
                        slots_filled_this_pass += 1
                        total_slots_needed -= 1 # Decrement total needed count

                        # Swap the used spot with the current spot_idx position and advance spot_idx
                        available_spots_list[temp_spot_search_idx], available_spots_list[spot_idx] = \
                            available_spots_list[spot_idx], available_spots_list[temp_spot_search_idx]
                        spot_idx += 1
                        assigned_spot_for_camper = True
                        break # Found a spot for this camper, move to next camper

                temp_spot_search_idx += 1 # Check next spot in the shuffled list

            # Move to the next camper regardless of whether a spot was found for the current one
            camper_loop_idx += 1
            # If a camper completed their slots, they won't be considered in the next pass inner loop

        # Safety check: If a pass completes with no assignments made but slots are still needed
        if slots_filled_this_pass == 0 and total_slots_needed > 0:
             print(f"  Warning: Could not fill any more slots in this random assignment pass ({total_slots_needed} needed). Stopping random fill.")
             break
        elif total_slots_needed > 0:
             print(f"  Finished pass, filled {slots_filled_this_pass} slots.")
        else:
             print(f"  Finished pass, filled {slots_filled_this_pass} slots. All needed slots filled.")


    print(f"Assigned {assigned_count_random} spots in the Random Filling Round.")
    final_needs = sum(c_data['needs_slots'] for c_data in campers.values() if c_data['needs_slots'] > 0)
    if final_needs > 0:
         print(f"Warning: After random fill, {final_needs} total slots still needed by campers.")


def run_allocation(campers, hugim):
    """Main function to orchestrate the allocation process."""
    if not campers or not hugim:
        print("ERROR: Cannot run allocation with empty campers or hugim data.")
        return

    for i in range(PREFERENCES_PER_CAMPER):
        run_preference_round(campers, hugim, preference_index=i, round_num=i + 1)

    run_random_fill_round(campers, hugim)
    print("\n--- Allocation Process Complete ---")


# --- Output Functions ---

def save_assignments(campers, filepath):
    """
    Saves the final assignments to a CSV file.
    Format: CamperID,Hug_Alef,Hug_Bet,Hug_Gimmel,...
    """
    print(f"\nSaving assignments to {filepath}...")
    assignments_data = []
    # Define Hebrew alphabet based headers (adjust if target changes)
    hebrew_headers = ["Alef", "Bet", "Gimmel", "Dalet", "Hey", "Vav"] # Add more if needed
    headers = ["CamperID"] + [f"Hug_{hebrew_headers[i]}" for i in range(NUM_ASSIGNMENTS_TARGET)]

    assigned_count = 0
    for camper_id, camper_data in sorted(campers.items()):
        # Get just the names, sort alphabetically for consistent output column order
        assigned_list = sorted([assignment[0] for assignment in camper_data['assigned_hugim']])
        padded_assigned = assigned_list + [''] * (NUM_ASSIGNMENTS_TARGET - len(assigned_list))
        row = [camper_id] + padded_assigned[:NUM_ASSIGNMENTS_TARGET]
        assignments_data.append(row)
        if assigned_list:
            assigned_count += 1

    try:
        df_assignments = pd.DataFrame(assignments_data, columns=headers)
        df_assignments.to_csv(filepath, index=False, encoding='utf-8')
        print(f"Successfully saved assignments for {assigned_count} campers.")
        return df_assignments # Return dataframe for printing summary
    except Exception as e:
        print(f"ERROR: Failed to save assignments file {filepath}. Error: {e}")
        return None

def save_unassigned_campers(campers, filepath):
    """
    Saves a list of campers who did not receive the target number of assignments.
    Format: CamperID, AssignmentsReceived, SlotsStillNeeded
    """
    print(f"\nSaving list of campers with incomplete assignments to {filepath}...")
    unassigned_data = []
    for camper_id, camper_data in sorted(campers.items()):
        if camper_data['needs_slots'] > 0:
            assignments_received = NUM_ASSIGNMENTS_TARGET - camper_data['needs_slots']
            unassigned_data.append([camper_id, assignments_received, camper_data['needs_slots']])

    if not unassigned_data:
        print("All campers received the target number of assignments.")
        if os.path.exists(filepath):
             try:
                 os.remove(filepath) # Remove empty file if it exists
                 print(f"Removed empty file: {filepath}")
             except Exception as e:
                 print(f"Warning: Could not remove empty unassigned file: {e}")
        return None # Return None if no unassigned

    try:
        df_unassigned = pd.DataFrame(unassigned_data, columns=["CamperID", "AssignmentsReceived", "SlotsStillNeeded"])
        df_unassigned.to_csv(filepath, index=False, encoding='utf-8')
        print(f"Successfully saved {len(unassigned_data)} campers with incomplete assignments.")
        return df_unassigned # Return dataframe for printing summary
    except Exception as e:
        print(f"ERROR: Failed to save unassigned campers file {filepath}. Error: {e}")
        return None


def calculate_and_save_stats(campers, hugim, filepath):
    """
    Calculates and saves statistics about the allocation, including preference satisfaction.
    Format: StatName, Value
    """
    print(f"\nCalculating and saving statistics to {filepath}...")
    stats = []
    pref_satisfaction = defaultdict(int) # Stores counts for Pref_1, Pref_2, ..., Random
    total_assigned_slots = 0
    campers_with_target_assignments = 0

    for camper_data in campers.values():
        num_assigned_this_camper = len(camper_data['assigned_hugim'])
        total_assigned_slots += num_assigned_this_camper
        if num_assigned_this_camper == NUM_ASSIGNMENTS_TARGET:
            campers_with_target_assignments += 1
        # Tally assignment methods
        for _, method in camper_data['assigned_hugim']:
            pref_satisfaction[method] += 1

    # Basic Counts
    stats.append(["Total Campers", len(campers)])
    stats.append(["Total Hugim", len(hugim)])
    stats.append(["Target Assignments per Camper", NUM_ASSIGNMENTS_TARGET])
    stats.append(["Total Assigned Slots", total_assigned_slots])
    stats.append(["Campers with Target Assignments", campers_with_target_assignments])
    percent_complete = (campers_with_target_assignments / len(campers) * 100) if campers else 0
    stats.append(["Percent Campers Fully Assigned", f"{percent_complete:.2f}%"])

    # Preference Satisfaction Stats
    stats.append(["--- Preference Satisfaction ---", "---"])
    sorted_methods = sorted(pref_satisfaction.keys(), key=lambda x: int(x.split('_')[1]) if x.startswith('Pref_') else 999) # Sort Pref_1, Pref_2.. then Random
    for method in sorted_methods:
         count = pref_satisfaction[method]
         percentage = (count / total_assigned_slots * 100) if total_assigned_slots > 0 else 0
         stats.append([f"Assignments via {method}", count])
         stats.append([f"Assignments via {method} (%)", f"{percentage:.2f}%"])

    # Hugim Fill Rates
    stats.append(["--- Hugim Stats ---", "---"])
    total_capacity = 0
    total_enrolled = 0
    for hug_name, hug_info in sorted(hugim.items()):
        capacity = hug_info['capacity']
        enrolled = len(hug_info['enrolled_campers'])
        fill_rate = (enrolled / capacity * 100) if capacity > 0 else 0
        stats.append([f"Hug: {hug_name} - Capacity", capacity])
        stats.append([f"Hug: {hug_name} - Enrolled", enrolled])
        stats.append([f"Hug: {hug_name} - Fill Rate", f"{fill_rate:.2f}%"])
        total_capacity += capacity
        total_enrolled += enrolled

    stats.append(["--- Overall Capacity ---", "---"])
    stats.append(["Total Capacity Across All Hugim", total_capacity])
    overall_fill_rate = (total_enrolled / total_capacity * 100) if total_capacity > 0 else 0
    stats.append(["Overall Fill Rate", f"{overall_fill_rate:.2f}%"])

    # Save Stats
    try:
        df_stats = pd.DataFrame(stats, columns=["Statistic", "Value"])
        df_stats.to_csv(filepath, index=False, encoding='utf-8')
        print(f"Successfully saved statistics.")
        return df_stats # Return dataframe for printing summary
    except Exception as e:
        print(f"ERROR: Failed to save statistics file {filepath}. Error: {e}")
        return None

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting Hugim Allocation POC Script (v2)...")

    # Install pandas if running in Colab and it's not already available
    try:
        import pandas
    except ImportError:
        print("Pandas not found, attempting to install...")
        import subprocess
        import sys
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
            import pandas as pd
            print("Pandas installed successfully.")
        except Exception as e:
            print(f"ERROR: Failed to install pandas. Please install it manually ('pip install pandas'). Error: {e}")
            sys.exit(1) # Exit if pandas cannot be installed/imported


    # 1. Load Data
    print("\n--- Loading Data ---")
    hugim_data = load_hugim(HUGIM_DATA_FILE)
    camper_data = load_campers(CAMPERS_DATA_FILE)
    prefs_loaded = load_preferences(PREFERENCES_DATA_FILE, camper_data)

    df_assignments_final = None
    df_unassigned_final = None
    df_stats_final = None

    if not hugim_data or not camper_data or not prefs_loaded:
         print("\nERROR: Halting script due to errors during data loading.")
    elif not any(data['preferences'] for data in camper_data.values()):
         print("\nERROR: No preferences were successfully loaded for any camper. Halting script.")
    else:
        # 2. Run Allocation
        print("\n--- Running Allocation Algorithm ---")
        run_allocation(camper_data, hugim_data)

        # 3. Save Results & Get DataFrames
        print("\n--- Saving Results ---")
        df_assignments_final = save_assignments(camper_data, OUTPUT_ASSIGNMENTS_FILE)
        df_unassigned_final = save_unassigned_campers(camper_data, OUTPUT_UNASSIGNED_FILE)
        df_stats_final = calculate_and_save_stats(camper_data, hugim_data, OUTPUT_STATS_FILE)

        # 4. Print Summary Output (Good for Colab)
        print("\n--- Allocation Summary ---")
        if df_stats_final is not None:
             print("\n** Key Statistics: **")
             # Print specific key stats for quick view
             key_stats_to_print = [
                 "Percent Campers Fully Assigned",
                 "Overall Fill Rate",
                 "Assignments via Pref_1",
                 "Assignments via Pref_2",
                 "Assignments via Pref_3",
                 "Assignments via Random"
                 ]
             # Use .loc for safe access, handle missing stats gracefully
             print(df_stats_final.loc[df_stats_final['Statistic'].isin(key_stats_to_print)].to_string(index=False, header=False))


        if df_assignments_final is not None:
            print(f"\n** Assignments Sample (First {NUM_ASSIGNMENTS_TO_PRINT} Campers): **")
            print(df_assignments_final.head(NUM_ASSIGNMENTS_TO_PRINT).to_string(index=False))
        else:
            print("\nNo assignment data to display.")

        if df_unassigned_final is not None:
            print(f"\n** Campers with Incomplete Assignments (First {NUM_UNASSIGNED_TO_PRINT}): **")
            print(df_unassigned_final.head(NUM_UNASSIGNED_TO_PRINT).to_string(index=False))
        else:
             # Check if the file creation was skipped because everyone was assigned
             if not any(c['needs_slots'] > 0 for c in camper_data.values()):
                  print("\n** All campers were assigned the target number of Hugim! **")
             else:
                  print("\nNo unassigned camper data to display (or saving failed).")


        print("\nScript finished.")
