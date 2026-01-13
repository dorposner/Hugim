import streamlit as st
import pandas as pd
from datetime import datetime

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

def find_sheet(camp_name, folder_id):
    """
    Searches for a Google Sheet with the exact name in the specified folder.
    Returns the file ID if found, else None.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return None

    _, drive_service = init_services()
    if not drive_service:
        return None

    # Escape single quotes in camp_name to prevent query injection
    sanitized_name = camp_name.replace("'", "\\'")
    query = f"name = '{sanitized_name}' and '{folder_id}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    try:
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
    except Exception as e:
        st.error(f"Error searching for sheet: {e}")
    return None

def create_sheet(camp_name, folder_id):
    """
    Creates a new Google Sheet in the specified folder.
    Returns the file ID.
    """
    if not GOOGLE_LIB_AVAILABLE:
        st.error("Google libraries not installed.")
        return None

    sheets_service, drive_service = init_services()
    if not sheets_service or not drive_service:
        st.error("Google credentials missing.")
        return None

    # Create the spreadsheet directly in the target folder using Drive API
    file_metadata = {
        'name': camp_name,
        'parents': [folder_id],
        'mimeType': 'application/vnd.google-apps.spreadsheet'
    }
    try:
        file = drive_service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')

    except HttpError as e:
        if e.resp.status == 403:
            st.error("Error creating sheet: Permission denied. Please ensure the 'Google Sheets API' and 'Google Drive API' are enabled in your Google Cloud Project.")
        else:
            st.error(f"Error creating sheet: {e}")
        return None
    except Exception as e:
        st.error(f"Error creating sheet: {e}")
        return None

def read_config(spreadsheet_id):
    """
    Reads configuration from the Google Sheet.
    Returns a dict with 'config', 'periods', 'preference_prefixes'.
    """
    if not GOOGLE_LIB_AVAILABLE:
        return None

    sheets_service, _ = init_services()
    if not sheets_service:
        return None

    try:
        # Read all relevant ranges. Assuming standard tab names.
        ranges = ['config!A:B', 'periods!A:A', 'preference_prefixes!A:B']
        result = sheets_service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=ranges).execute()
        value_ranges = result.get('valueRanges', [])

        config_data = {}

        # 1. config tab
        config_values = value_ranges[0].get('values', [])
        config_dict = {}
        if config_values:
            # Skip header if it exists and looks like key/value
            start_row = 1 if len(config_values) > 0 and config_values[0][0].lower() == 'key' else 0
            for row in config_values[start_row:]:
                if len(row) >= 2:
                    val = row[1]
                    # Try to convert to int if possible
                    try:
                        val = int(val)
                    except ValueError:
                        pass
                    config_dict[row[0]] = val
        config_data['config'] = config_dict

        # 2. periods tab
        periods_values = value_ranges[1].get('values', [])
        periods_list = []
        if periods_values:
            start_row = 1 if len(periods_values) > 0 and periods_values[0][0].lower() == 'period_name' else 0
            for row in periods_values[start_row:]:
                if row:
                    periods_list.append(row[0])
        config_data['periods'] = periods_list

        # 3. preference_prefixes tab
        prefixes_values = value_ranges[2].get('values', [])
        prefixes_dict = {}
        if prefixes_values:
            start_row = 1 if len(prefixes_values) > 0 and prefixes_values[0][0].lower() == 'period_name' else 0
            for row in prefixes_values[start_row:]:
                if len(row) >= 2:
                    prefixes_dict[row[0]] = row[1]
        config_data['preference_prefixes'] = prefixes_dict

        return config_data

    except HttpError as e:
        st.error(f"Error reading configuration: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error reading configuration: {e}")
        return None

def save_config(spreadsheet_id, config_data):
    """
    Writes configuration to the Google Sheet.
    config_data should match the structure returned by read_config.
    """
    if not GOOGLE_LIB_AVAILABLE:
        st.error("Google libraries not installed.")
        return False

    sheets_service, _ = init_services()
    if not sheets_service:
        st.error("Google credentials missing.")
        return False

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

    data = [
        {'range': 'config!A1', 'values': config_rows},
        {'range': 'periods!A1', 'values': periods_rows},
        {'range': 'preference_prefixes!A1', 'values': prefixes_rows}
    ]

    body = {
        'valueInputOption': 'RAW',
        'data': data
    }

    try:
        # First, ensure sheets exist.
        # We'll just try to write. If tabs don't exist, we might need to create them.
        # But `batchUpdate` with `addSheet` is complex to check existence.
        # Simple approach: Check sheet properties first.
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existing_titles = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]

        requests = []
        required_titles = ['config', 'periods', 'preference_prefixes']
        for title in required_titles:
            if title not in existing_titles:
                requests.append({'addSheet': {'properties': {'title': title}}})

        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()

        # Now write data (this clears existing data in the range and writes new)
        # Note: update logic doesn't clear the whole sheet, just the range.
        # If the list shrank, we might have leftover rows.
        # Better to clear first or overwrite with empty strings if needed.
        # For simplicity, we'll assume the list grows or stays similar,
        # but to be safe, let's clear the sheets.

        clear_requests = []
        for title in required_titles:
             # Find sheetId
            sheet_id_num = next(s['properties']['sheetId'] for s in sheet_metadata.get('sheets', []) if s['properties']['title'] == title)
            # Actually we can re-fetch metadata if we added sheets, but let's just use range names for clear.
            # wait, spreadsheets().values().clear() works on ranges.
            pass

        # We will use batchClear
        sheets_service.spreadsheets().values().batchClear(
            spreadsheetId=spreadsheet_id,
            body={'ranges': [f'{t}!A:Z' for t in required_titles]}
        ).execute()

        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        return True

    except Exception as e:
        st.error(f"Error saving configuration: {e}")
        return False
