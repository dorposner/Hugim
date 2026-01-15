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
        'config': f"{camp_name}_config",
        'periods': f"{camp_name}_periods",
        'preference_prefixes': f"{camp_name}_preference_prefixes",
        'hugim_data': f"{camp_name}_hugim_data",
        'camper_prefs': f"{camp_name}_camper_prefs"
    }

def read_config(camp_name):
    """
    Reads configuration and data from the Master Spreadsheet for a specific camp.
    Returns a dict with 'config', 'periods', 'preference_prefixes', 'hugim_df', 'prefs_df'.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return None

    sheets_service, _ = init_services()
    if not sheets_service:
        return None

    tabs = get_tab_names(camp_name)

    try:
        # Get sheet metadata to check which sheets exist
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=MASTER_SPREADSHEET_ID).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        ranges = []
        range_map = {} # Map index to key

        # Helper to add range if sheet exists
        def add_range(key, sheet_name, cell_range):
            if sheet_name in existing_titles:
                ranges.append(f"'{sheet_name}'!{cell_range}")
                range_map[len(ranges)-1] = key

        add_range('config', tabs['config'], 'A:B')
        add_range('periods', tabs['periods'], 'A:A')
        add_range('prefixes', tabs['preference_prefixes'], 'A:B')
        add_range('hugim', tabs['hugim_data'], 'A:ZZ')
        add_range('prefs', tabs['camper_prefs'], 'A:ZZ')

        if not ranges:
            return {}

        result = sheets_service.spreadsheets().values().batchGet(
            spreadsheetId=MASTER_SPREADSHEET_ID, ranges=ranges).execute()
        value_ranges = result.get('valueRanges', [])

        config_data = {}

        # Process results
        for i, val_range in enumerate(value_ranges):
            key = range_map.get(i)
            values = val_range.get('values', [])

            if key == 'config':
                config_dict = {}
                if values:
                    # Skip header if present (key, value)
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'key' else 0
                    for row in values[start_row:]:
                        if len(row) >= 2:
                            val = row[1]
                            try:
                                val = int(val)
                            except ValueError:
                                pass
                            config_dict[row[0]] = val
                config_data['config'] = config_dict

            elif key == 'periods':
                periods_list = []
                if values:
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'period_name' else 0
                    for row in values[start_row:]:
                        if row:
                            periods_list.append(row[0])
                config_data['periods'] = periods_list

            elif key == 'prefixes':
                prefixes_dict = {}
                if values:
                    start_row = 1 if len(values) > 0 and str(values[0][0]).lower() == 'period_name' else 0
                    for row in values[start_row:]:
                        if len(row) >= 2:
                            prefixes_dict[row[0]] = row[1]
                config_data['preference_prefixes'] = prefixes_dict

            elif key == 'hugim':
                if values:
                    header = values[0]
                    data = values[1:]
                    # Ensure we don't fail if empty data
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

        return config_data

    except HttpError as e:
        st.error(f"Error reading configuration: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error reading configuration: {e}")
        return None

def save_config(camp_name, config_data, hugim_df=None, prefs_df=None):
    """
    Writes configuration and optionally dataframes to the Master Google Sheet.
    config_data should match the structure returned by read_config.
    """
    if not GOOGLE_LIB_AVAILABLE:
        st.error("Google libraries not installed.")
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        st.error("Google credentials missing.")
        return False

    tabs = get_tab_names(camp_name)

    # Prepare data for writing

    # 1. config tab
    config_rows = [['key', 'value']]
    for k, v in config_data.get('config', {}).items():
        config_rows.append([str(k), str(v)])

    # 2. periods tab
    periods_rows = [['period_name']]
    for p in config_data.get('periods', []):
        periods_rows.append([str(p)])

    # 3. preference_prefixes tab
    prefixes_rows = [['period_name', 'prefix']]
    for p, prefix in config_data.get('preference_prefixes', {}).items():
        prefixes_rows.append([str(p), str(prefix)])

    data_payloads = [
        {'range': f"'{tabs['config']}'!A1", 'values': config_rows},
        {'range': f"'{tabs['periods']}'!A1", 'values': periods_rows},
        {'range': f"'{tabs['preference_prefixes']}'!A1", 'values': prefixes_rows}
    ]

    required_titles = [tabs['config'], tabs['periods'], tabs['preference_prefixes']]

    # 4. hugim_data tab
    if hugim_df is not None:
        hugim_rows = [hugim_df.columns.tolist()] + hugim_df.fillna('').astype(str).values.tolist()
        data_payloads.append({'range': f"'{tabs['hugim_data']}'!A1", 'values': hugim_rows})
        required_titles.append(tabs['hugim_data'])

    # 5. camper_prefs tab
    if prefs_df is not None:
        prefs_rows = [prefs_df.columns.tolist()] + prefs_df.fillna('').astype(str).values.tolist()
        data_payloads.append({'range': f"'{tabs['camper_prefs']}'!A1", 'values': prefs_rows})
        required_titles.append(tabs['camper_prefs'])

    body = {
        'valueInputOption': 'RAW',
        'data': data_payloads
    }

    try:
        # First, ensure sheets exist.
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=MASTER_SPREADSHEET_ID).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        requests = []
        for title in required_titles:
            if title not in existing_titles:
                requests.append({'addSheet': {'properties': {'title': title}}})

        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=MASTER_SPREADSHEET_ID,
                body={'requests': requests}
            ).execute()

        # Clear existing content before writing
        sheets_service.spreadsheets().values().batchClear(
            spreadsheetId=MASTER_SPREADSHEET_ID,
            body={'ranges': [f"'{t}'!A:ZZ" for t in required_titles]}
        ).execute()

        # Write new content
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=MASTER_SPREADSHEET_ID,
            body=body
        ).execute()

        return True

    except Exception as e:
        st.error(f"Raw Error from Google (save_config): {e}")
        return False
