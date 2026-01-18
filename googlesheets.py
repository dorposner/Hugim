import streamlit as st
import pandas as pd
import bcrypt
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Try to import Google libraries
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIB_AVAILABLE = True
except ImportError:
    GOOGLE_LIB_AVAILABLE = False

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

MASTER_SPREADSHEET_ID = "1E3PXe2LQfscI9vjJVqJRsBK9rhCRV8J-6rcrGMn_7XM"
USERS_DB_TAB_NAME = 'users_db'

def get_credentials():
    """Retrieves credentials from Streamlit secrets."""
    if "gcp_service_account" in st.secrets:
        return service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
    return None

def get_folder_id():
    """Retrieves the drive folder ID from Streamlit secrets."""
    try:
        # Check nested [drive] section first
        if "drive" in st.secrets and "folder_id" in st.secrets["drive"]:
            return st.secrets["drive"]["folder_id"]
        # Fallback to top-level key
        return st.secrets.get("drive_folder_id")
    except FileNotFoundError:
        return None

def init_services():
    """Initializes Google Sheets and Drive services."""
    creds = get_credentials()
    if not creds:
        return None, None

    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return sheets_service, drive_service

def force_empty_trash():
    """Empty trash to free up space."""
    try:
        _, drive_service = init_services()
        if drive_service:
            drive_service.files().emptyTrash().execute()
            return True
    except Exception as e:
        st.error(f"Error emptying trash: {e}")
    return False

def get_tab_names(camp_name):
    """Generates tab names based on camp name prefix."""
    return {
        'settings': f"{camp_name}_settings",
        'hugim_data': f"{camp_name}_hugim_data",
        'camper_prefs': f"{camp_name}_camper_prefs",
        'assignments': f"{camp_name}_assignments"
    }

def get_all_camp_names(spreadsheet_id=None):
    """
    Returns a list of unique camp names based on tab prefixes in the Master Sheet.
    Checks for both new '_settings' and legacy '_config' suffixes.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return []

    sheets_service, _ = init_services()
    if not sheets_service:
        return []

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        sheets = sheet_metadata.get('sheets', [])

        camp_names = set()
        for sheet in sheets:
            title = sheet['properties']['title']
            if title.endswith('_settings'):
                camp_name = title.replace('_settings', '')
                camp_names.add(camp_name)
            elif title.endswith('_config'):
                # Legacy support
                camp_name = title.replace('_config', '')
                camp_names.add(camp_name)

        return sorted(list(camp_names))
    except Exception as e:
        st.error(f"Error fetching camp names: {e}")
        return []

def rename_camp_tabs(old_name, new_name, spreadsheet_id=None):
    """
    Renames all tabs belonging to a camp from old_name to new_name.
    Handles both new '_settings' structure and legacy tabs because it matches by prefix.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        return False

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        # Get all sheets to find matches
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        sheets = sheet_metadata.get('sheets', [])

        requests = []
        old_prefix = f"{old_name}_"
        new_prefix = f"{new_name}_"

        for sheet in sheets:
            title = sheet['properties']['title']
            if title.startswith(old_prefix):
                sheet_id = sheet['properties']['sheetId']
                # Replace the prefix
                new_title = title.replace(old_prefix, new_prefix, 1)

                requests.append({
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'title': new_title
                        },
                        'fields': 'title'
                    }
                })

        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={'requests': requests}
            ).execute()
            return True
        else:
            st.warning(f"No tabs found for camp '{old_name}'")
            return False

    except Exception as e:
        st.error(f"Error renaming camp tabs: {e}")
        return False

def delete_camp_tabs(camp_name, spreadsheet_id=None):
    """
    Deletes all tabs belonging to a camp.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        return False

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        # Get all sheets to find matches
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        sheets = sheet_metadata.get('sheets', [])

        requests = []
        prefix = f"{camp_name}_"

        for sheet in sheets:
            title = sheet['properties']['title']
            if title.startswith(prefix):
                sheet_id = sheet['properties']['sheetId']
                requests.append({
                    'deleteSheet': {
                        'sheetId': sheet_id
                    }
                })

        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={'requests': requests}
            ).execute()
            return True
        else:
            st.warning(f"No tabs found for camp '{camp_name}'")
            return False

    except Exception as e:
        st.error(f"Error deleting camp tabs: {e}")
        return False

def read_config(camp_name, spreadsheet_id=None):
    """
    Reads configuration and data from the Master Spreadsheet for a specific camp.
    Returns a dict with 'config', 'periods', 'preference_prefixes', 'hugim_df', 'prefs_df'.
    Supports both new '_settings' tab and legacy '_config', '_periods', '_preference_prefixes' tabs.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return None

    sheets_service, _ = init_services()
    if not sheets_service:
        return None

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID
    tabs = get_tab_names(camp_name)

    # Legacy tab names for fallback
    legacy_tabs = {
        'config': f"{camp_name}_config",
        'periods': f"{camp_name}_periods",
        'preference_prefixes': f"{camp_name}_preference_prefixes"
    }

    try:
        # Get sheet metadata to check which sheets exist
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        ranges = []
        range_map = {} # Map index to key

        # Determine if we are using new settings or legacy
        use_legacy = False
        if tabs['settings'] not in existing_titles and legacy_tabs['config'] in existing_titles:
             use_legacy = True

        # Helper to add range if sheet exists
        def add_range(key, sheet_name, cell_range):
            if sheet_name in existing_titles:
                ranges.append(f"'{sheet_name}'!{cell_range}")
                range_map[len(ranges)-1] = key

        if use_legacy:
            add_range('legacy_config', legacy_tabs['config'], 'A:B')
            add_range('legacy_periods', legacy_tabs['periods'], 'A:A')
            add_range('legacy_prefixes', legacy_tabs['preference_prefixes'], 'A:B')
        else:
            add_range('settings', tabs['settings'], 'A:E')

        add_range('hugim', tabs['hugim_data'], 'A:ZZ')
        add_range('prefs', tabs['camper_prefs'], 'A:ZZ')
        add_range('assignments', tabs['assignments'], 'A:ZZ')

        if not ranges:
            return {}

        result = sheets_service.spreadsheets().values().batchGet(
            spreadsheetId=sid, ranges=ranges).execute()
        value_ranges = result.get('valueRanges', [])

        config_data = {
            'config': {},
            'periods': [],
            'preference_prefixes': {}
        }

        # Process results
        for i, val_range in enumerate(value_ranges):
            key = range_map.get(i)
            values = val_range.get('values', [])

            if key == 'settings':
                # Parse new settings tab
                # Cols A-B: Config
                # Cols D-E: Periods/Prefixes
                if values:
                    # Skip header if present
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'key' else 0
                    for row in values[start_row:]:
                        # Parse config (A-B)
                        if len(row) >= 2 and row[0]:
                             val = row[1]
                             try:
                                 val = int(val)
                             except ValueError:
                                 pass
                             config_data['config'][row[0]] = val

                        # Parse periods/prefixes (D-E)
                        # Row indices 3 (D) and 4 (E)
                        if len(row) >= 4:
                            period_name = row[3]
                            if period_name:
                                config_data['periods'].append(period_name)
                                if len(row) >= 5:
                                    config_data['preference_prefixes'][period_name] = row[4]
                                else:
                                     # Prefix might be missing or empty
                                     config_data['preference_prefixes'][period_name] = ""

            elif key == 'legacy_config':
                if values:
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'key' else 0
                    for row in values[start_row:]:
                        if len(row) >= 2:
                            val = row[1]
                            try:
                                val = int(val)
                            except ValueError:
                                pass
                            config_data['config'][row[0]] = val

            elif key == 'legacy_periods':
                if values:
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'period_name' else 0
                    for row in values[start_row:]:
                        if row:
                            config_data['periods'].append(row[0])

            elif key == 'legacy_prefixes':
                if values:
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'period_name' else 0
                    for row in values[start_row:]:
                        if len(row) >= 2:
                            config_data['preference_prefixes'][row[0]] = row[1]

            elif key == 'hugim':
                if values:
                    header = values[0]
                    data = values[1:]
                    if data:
                        config_data['hugim_df'] = pd.DataFrame(data, columns=header)
                    else:
                        config_data['hugim_df'] = pd.DataFrame(columns=header)

            elif key == 'prefs':
                if values:
                    header = values[0]
                    data = values[1:]
                    if data:
                        config_data['prefs_df'] = pd.DataFrame(data, columns=header)
                    else:
                        config_data['prefs_df'] = pd.DataFrame(columns=header)

            elif key == 'assignments':
                if values:
                    header = values[0]
                    data = values[1:]
                    if data:
                        config_data['assignments_df'] = pd.DataFrame(data, columns=header)
                    else:
                        config_data['assignments_df'] = pd.DataFrame(columns=header)

        return config_data

    except HttpError as e:
        st.error(f"Error reading configuration: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error reading configuration: {e}")
        return None

def save_camp_state(camp_name, config_data, hugim_df=None, prefs_df=None, assignments_df=None, spreadsheet_id=None):
    """
    Writes configuration and optionally dataframes (including assignments) to the Master Google Sheet.
    Uses the new '[CampName]_settings' tab structure.
    Also handles migration by deleting legacy tabs if they exist.
    """
    if not GOOGLE_LIB_AVAILABLE:
        st.error("Google libraries not installed.")
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        st.error("Google credentials missing.")
        return False

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID
    tabs = get_tab_names(camp_name)

    # Prepare data for writing

    # settings tab data
    # Combine Config (A-B) and Periods/Prefixes (D-E) into one list of rows
    config_items = list(config_data.get('config', {}).items())
    periods = config_data.get('periods', [])
    prefixes = config_data.get('preference_prefixes', {})

    # Determine max rows needed
    max_rows = max(len(config_items), len(periods))

    settings_rows = [['key', 'value', '', 'period_name', 'prefix']] # Header

    for i in range(max_rows):
        row = ['', '', '', '', '']

        # Cols A-B
        if i < len(config_items):
            row[0] = str(config_items[i][0])
            row[1] = str(config_items[i][1])

        # Col C is empty spacer

        # Cols D-E
        if i < len(periods):
            p = periods[i]
            row[3] = str(p)
            row[4] = str(prefixes.get(p, ''))

        settings_rows.append(row)

    data_payloads = [
        {'range': f"'{tabs['settings']}'!A1", 'values': settings_rows}
    ]

    required_titles = [tabs['settings']]

    # hugim_data tab
    if hugim_df is not None:
        hugim_rows = [hugim_df.columns.tolist()] + hugim_df.fillna('').astype(str).values.tolist()
        data_payloads.append({'range': f"'{tabs['hugim_data']}'!A1", 'values': hugim_rows})
        required_titles.append(tabs['hugim_data'])

    # camper_prefs tab
    if prefs_df is not None:
        prefs_rows = [prefs_df.columns.tolist()] + prefs_df.fillna('').astype(str).values.tolist()
        data_payloads.append({'range': f"'{tabs['camper_prefs']}'!A1", 'values': prefs_rows})
        required_titles.append(tabs['camper_prefs'])

    # assignments tab
    if assignments_df is not None:
        assignments_rows = [assignments_df.columns.tolist()] + assignments_df.fillna('').astype(str).values.tolist()
        data_payloads.append({'range': f"'{tabs['assignments']}'!A1", 'values': assignments_rows})
        required_titles.append(tabs['assignments'])

    body = {
        'valueInputOption': 'RAW',
        'data': data_payloads
    }

    try:
        # First, ensure sheets exist.
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        requests = []
        for title in required_titles:
            if title not in existing_titles:
                requests.append({'addSheet': {'properties': {'title': title}}})

        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={'requests': requests}
            ).execute()

        # Clear existing content before writing
        # Explicitly using batchClear to ensure no old data remains (e.g. ghost rows)
        sheets_service.spreadsheets().values().batchClear(
            spreadsheetId=sid,
            body={'ranges': [f"'{t}'!A:ZZ" for t in required_titles]}
        ).execute()

        # Write new content
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=sid,
            body=body
        ).execute()

        # Clean up legacy tabs if they exist
        legacy_tabs = [
            f"{camp_name}_config",
            f"{camp_name}_periods",
            f"{camp_name}_preference_prefixes"
        ]

        delete_requests = []
        for sheet in sheet_metadata.get('sheets', []):
            if sheet['properties']['title'] in legacy_tabs:
                delete_requests.append({
                    'deleteSheet': {'sheetId': sheet['properties']['sheetId']}
                })

        if delete_requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={'requests': delete_requests}
            ).execute()

        return True

    except Exception as e:
        st.error(f"Raw Error from Google (save_camp_state): {e}")
        return False

def init_user_db(spreadsheet_id=None):
    """Checks if users_db tab exists, creates it if not."""
    if not GOOGLE_LIB_AVAILABLE:
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        return False

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sid).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        if USERS_DB_TAB_NAME not in existing_titles:
            # Create the sheet
            requests = [{
                'addSheet': {
                    'properties': {'title': USERS_DB_TAB_NAME}
                }
            }]
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={'requests': requests}
            ).execute()

            # Add headers
            headers = [['email', 'password_hash', 'camp_name', 'role', 'created_at']]
            body = {
                'values': headers
            }
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"{USERS_DB_TAB_NAME}!A1",
                valueInputOption='RAW',
                body=body
            ).execute()
        return True
    except Exception as e:
        st.error(f"Error initializing user DB: {e}")
        return False

def hash_password(password):
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Verifies a password against a hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False

def get_users(spreadsheet_id=None):
    """Retrieves all users from the database."""
    if not GOOGLE_LIB_AVAILABLE:
        return []

    sheets_service, _ = init_services()
    if not sheets_service:
        return []

    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        # Ensure DB exists
        if not init_user_db(spreadsheet_id):
             return []

        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sid, range=f"{USERS_DB_TAB_NAME}!A:E").execute()
        values = result.get('values', [])

        if not values:
            return []

        # headers = values[0]
        data = values[1:]

        users = []
        for i, row in enumerate(data):
            if len(row) >= 1: # Minimal required fields
                user = {
                    'row_idx': i + 2, # +1 for header, +1 for 0-based index
                    'email': row[0],
                    'password_hash': row[1] if len(row) > 1 else '',
                    'camp_name': row[2] if len(row) > 2 else '',
                    'role': row[3] if len(row) > 3 else 'user',
                    'created_at': row[4] if len(row) > 4 else ''
                }
                users.append(user)
        return users
    except Exception:
        return []

def get_all_users(spreadsheet_id=None):
    """Returns the entire users_db content as a pandas DataFrame (hiding password hashes)."""
    users = get_users(spreadsheet_id)
    if not users:
        return pd.DataFrame(columns=['email', 'camp_name', 'role', 'created_at'])

    df = pd.DataFrame(users)
    # Drop password_hash and row_idx for display
    return df.drop(columns=['password_hash', 'row_idx'], errors='ignore')

def create_user(email, password, camp_name, spreadsheet_id=None, enforce_unique_camp=True):
    """
    Creates a new user.
    enforce_unique_camp: If True, ensures no other user has this camp name.
                         If False, allows multiple users to share a camp (for Admin adding staff).
    """
    if not GOOGLE_LIB_AVAILABLE:
        return False, "Google libraries not loaded."

    # Normalize
    email = email.lower().strip()
    camp_name = camp_name.strip()

    if not email or not password or not camp_name:
        return False, "All fields are required."

    # Init DB to ensure it exists
    if not init_user_db(spreadsheet_id):
        return False, "Could not access User DB."

    # Check existing users
    users = get_users(spreadsheet_id)
    for u in users:
        if u['email'] == email:
            return False, "Email already registered."

        if enforce_unique_camp:
            if u['camp_name'].lower() == camp_name.lower():
                 return False, "Camp Name already associated with another user."

    if enforce_unique_camp:
        # Check existing camp tabs (globally) to prevent hijacking existing camp data
        all_camps = get_all_camp_names(spreadsheet_id)
        if any(c.lower() == camp_name.lower() for c in all_camps):
            return False, "Camp Name already exists in the system."

    # Create user
    hashed = hash_password(password)
    created_at = datetime.datetime.now().isoformat()

    row = [email, hashed, camp_name, 'user', created_at]

    sheets_service, _ = init_services()
    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        body = {
            'values': [row]
        }
        sheets_service.spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{USERS_DB_TAB_NAME}!A1",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        return True, "User created successfully."
    except Exception as e:
        return False, f"Error creating user: {e}"

def update_user_role(email, new_role, spreadsheet_id=None):
    """Updates the role for a specific user."""
    return _update_user_field(email, 3, new_role, spreadsheet_id)

def update_user_camp(email, new_camp, spreadsheet_id=None):
    """Updates the camp association for a user."""
    return _update_user_field(email, 2, new_camp, spreadsheet_id)

def admin_reset_password(email, new_password, spreadsheet_id=None):
    """Hashes the new password and updates the user record."""
    hashed = hash_password(new_password)
    return _update_user_field(email, 1, hashed, spreadsheet_id)

def get_all_camps_analytics(progress_callback=None):
    """
    Iterates through all camps and returns a summary DataFrame.
    Calculates Campers, Activities, Periods, and Unassigned Slots.
    """
    camp_names = get_all_camp_names()
    analytics_data = []

    total_camps = len(camp_names)

    for idx, camp in enumerate(camp_names):
        # Update progress
        if progress_callback and total_camps > 0:
            progress_callback((idx + 1) / total_camps)

        row = {
            'Camp Name': camp,
            'Campers': 0,
            'Activities': 0,
            'Periods': 0,
            'Unassigned Slots': 0,
            'Status': 'OK'
        }

        try:
            config_data = read_config(camp)
            if config_data:
                # Campers
                if 'prefs_df' in config_data:
                    row['Campers'] = len(config_data['prefs_df'])

                # Activities
                if 'hugim_df' in config_data:
                    row['Activities'] = len(config_data['hugim_df'])

                # Periods
                if 'periods' in config_data:
                    row['Periods'] = len(config_data['periods'])

                # Unassigned Slots
                if 'assignments_df' in config_data:
                    df_assign = config_data['assignments_df']
                    assigned_cols = [c for c in df_assign.columns if str(c).endswith('_Assigned')]

                    unassigned_count = 0
                    for col in assigned_cols:
                        s = df_assign[col]
                        # Treat None, NaN as missing
                        mask = s.isna()
                        # Treat empty strings as missing
                        mask = mask | (s.astype(str).str.strip() == '')
                        # Treat 'None' or 'nan' string literal as missing (just in case)
                        mask = mask | (s.astype(str).str.lower().isin(['nan', 'none']))

                        unassigned_count += mask.sum()

                    row['Unassigned Slots'] = int(unassigned_count)
            else:
                 row['Status'] = 'Error (Read Failed)'
        except Exception as e:
            row['Status'] = f'Error: {str(e)}'

        analytics_data.append(row)

    return pd.DataFrame(analytics_data)

def delete_user(email, spreadsheet_id=None):
    """Removes a user from users_db."""
    if not GOOGLE_LIB_AVAILABLE:
        return False

    users = get_users(spreadsheet_id)
    target_row = None
    for u in users:
        if u['email'] == email:
            target_row = u['row_idx']
            break

    if not target_row:
        return False

    sheets_service, _ = init_services()
    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    try:
        # We use batchUpdate with deleteDimension
        # Note: row_idx is 1-based (Excel style), API uses 0-based index.
        # But wait, get_users logic for row_idx:
        # header is row 1.
        # data starts row 2.
        # u['row_idx'] = i + 2.
        # So if i=0 (first data row), row_idx=2.
        # deleteDimension uses 0-based index. Row 1 is index 0. Row 2 is index 1.
        # So we need to delete index = target_row - 1.

        delete_index = target_row - 1

        request = {
            'deleteDimension': {
                'range': {
                    'sheetId': _get_sheet_id(sheets_service, sid, USERS_DB_TAB_NAME),
                    'dimension': 'ROWS',
                    'startIndex': delete_index,
                    'endIndex': delete_index + 1
                }
            }
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=sid,
            body={'requests': [request]}
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting user: {e}")
        return False

def get_global_stats(spreadsheet_id=None):
    """Returns a dictionary with global stats."""
    users = get_users(spreadsheet_id)
    all_camps = get_all_camp_names(spreadsheet_id)

    df_users = pd.DataFrame(users)
    if df_users.empty:
        users_per_camp = pd.DataFrame(columns=['camp_name', 'count'])
    else:
        users_per_camp = df_users['camp_name'].value_counts().reset_index()
        users_per_camp.columns = ['camp_name', 'count']

    return {
        'total_users': len(users),
        'total_camps': len(all_camps),
        'users_per_camp': users_per_camp
    }

def _update_user_field(email, col_idx, value, spreadsheet_id=None):
    """Helper to update a specific cell for a user. col_idx is 0-based relative to A."""
    if not GOOGLE_LIB_AVAILABLE:
        return False

    users = get_users(spreadsheet_id)
    target_row = None
    for u in users:
        if u['email'] == email:
            target_row = u['row_idx']
            break

    if not target_row:
        return False

    sheets_service, _ = init_services()
    sid = spreadsheet_id or MASTER_SPREADSHEET_ID

    # Convert col_idx to letter.
    # 0=A, 1=B, 2=C, 3=D, 4=E
    col_letter = chr(65 + col_idx)
    range_name = f"{USERS_DB_TAB_NAME}!{col_letter}{target_row}"

    try:
        body = {
            'values': [[value]]
        }
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sid,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user field: {e}")
        return False

def _get_sheet_id(service, spreadsheet_id, sheet_name):
    """Helper to get sheetId from sheet name."""
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in sheet_metadata.get('sheets', []):
        if sheet['properties']['title'] == sheet_name:
            return sheet['properties']['sheetId']
    return None

def authenticate_user(email, password, spreadsheet_id=None):
    """Authenticates a user and returns their data."""
    if not GOOGLE_LIB_AVAILABLE:
        return None

    email = email.lower().strip()

    # Ensure DB exists (first run)
    init_user_db(spreadsheet_id)

    users = get_users(spreadsheet_id)
    for u in users:
        if u['email'] == email:
            if check_password(password, u['password_hash']):
                return u
            else:
                return None
    return None
