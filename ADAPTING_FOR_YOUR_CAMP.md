# How to Adapt the Hugim Allocator for Your Camp

This application is designed to allocate campers to activities ("Hugim") based on their preferences and activity constraints (capacity, minimum enrollment). While it was originally built for CYJ Texas (using periods like Aleph, Beth, Gimmel), it can be easily adapted for any camp schedule.

## 1. Concepts

*   **Period**: A block of time during the day or week when activities happen (e.g., "Morning", "Afternoon", "Period 1").
*   **Hug (Activity)**: An activity offered during a period (e.g., "Soccer", "Art", "Drama").
*   **Preferences**: Each camper ranks their choices for each period.
*   **Capacity/Minimum**: Each activity has a maximum number of campers (Capacity) and a minimum number required to run (Minimum).

## 2. Configuration via UI

The application allows you to define your camp's structure directly in the web interface. You do not need to edit any code.

1.  **Upload Files**: Upload your `hugim.csv` (Activities) and `preferences.csv` (Camper Choices).
2.  **Match Columns**:
    *   **Periods**: Select the columns in `hugim.csv` that represent your periods. For example, if you have columns named "Morning" and "Afternoon" with 1s and 0s indicating availability, select those.
    *   **Preferences**: For each period you defined, tell the system which columns in `preferences.csv` correspond to it. You do this by selecting a **Prefix**.
        *   *Example*: If you have columns `M_1`, `M_2`, `M_3` for "Morning" preferences, select the prefix `M`.

## 3. Creating Your CSV Files

To get started, you can copy the provided sample files and modify them.

### `hugim.csv` (Activities List)

This file lists all activities and their constraints.

**Required Columns:**
*   **HugName**: The name of the activity.
*   **Capacity**: Maximum number of campers.
*   **Minimum**: Minimum number of campers required.
*   **Period Columns**: One column for each period in your schedule. Use `1` (or `TRUE`, `Yes`) if the activity is offered in that period, and `0` otherwise.

**Example:**
```csv
HugName,Capacity,Minimum,Period_1,Period_2
Soccer,20,8,1,1
Art,15,5,1,0
Drama,12,4,0,1
```

### `preferences.csv` (Camper Choices)

This file lists each camper's ranked preferences for each period.

**Required Columns:**
*   **CamperID**: A unique identifier for the camper (name, ID number, etc.).
*   **Preference Columns**: For each period, you need columns representing the camper's 1st choice, 2nd choice, etc.
    *   The column names should follow a pattern like `Prefix_Rank`.
    *   *Example*: `P1_1` (Period 1, 1st choice), `P1_2` (Period 1, 2nd choice).

**Example:**
```csv
CamperID,P1_1,P1_2,P1_3,P2_1,P2_2,P2_3
1001,Soccer,Art,Drama,Drama,Soccer,Art
1002,Art,Soccer,,Drama,Art,
```

## 4. Running the Allocation

1.  Start the app.
2.  Upload your custom CSV files.
3.  In the **"Match your columns"** section:
    *   Select your Period columns (e.g., `Period_1`, `Period_2`).
    *   Map `Period_1` to prefix `P1` and `Period_2` to prefix `P2`.
4.  Click **Run Allocation**.

## 5. Google Sheets Persistence Configuration

To enable saving and loading camp configurations to Google Drive, you must configure the secrets.

### Step 1: Create a Google Drive Folder
1.  Create a folder in Google Drive.
2.  Note the **Folder ID** from the URL (the string of characters at the end).
    *   Example: `https://drive.google.com/drive/folders/12345ABCDE...` -> ID is `12345ABCDE...`

### Step 2: Set up a Google Service Account
1.  Go to the Google Cloud Console.
2.  Create a new Service Account.
3.  Create and download a JSON key for this account.
4.  **Important:** In Google Drive, share your folder with the Service Account's email address (found in the JSON file), giving it **Editor** access.

### Step 3: Configure `secrets.toml`
Create a file named `.streamlit/secrets.toml` in your project directory and add the following:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."

[drive]
folder_id = "YOUR_FOLDER_ID_HERE"
```

Replace the values in `[gcp_service_account]` with those from your downloaded JSON key.
