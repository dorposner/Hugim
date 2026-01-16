import streamlit as st
import pandas as pd
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
