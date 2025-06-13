CYJ Hugim Activity Allocation Web App
A flexible, user-friendly Streamlit application for assigning campers to activities (“Hugim”) at summer camps, fully respecting camper preferences and activity constraints.

💡 Features
Flexible Data Input: Upload your own CSV files for activities and camper preferences.
Robust Allocation Algorithm: Assigns campers to Hugim based on ranked preferences, activity capacity, and minimums, with no duplicate assignments for the same camper in a week.
Handles Cancellations/Reallocation: Cancels under-enrolled activities and automatically reallocates their campers.
Powerful Reporting: Summarizes preference satisfaction, visualizes statistics, and provides detailed tables of assignments and unassigned campers.
Downloadable Outputs: All key data (assignments, stats, unassigned campers) downloadable in CSV format.
🚀 Quick Start
1. Clone the Repository
BASH

cd cyj-hugim-allocation
2. Install Dependencies
BASH

pip install -r requirements.txt
3. Launch the App
BASH

streamlit run streamlit_app.py
Visit http://localhost:8501/ in your browser.

📝 Input File Formats
hugim.csv
Contains the activity roster and availability:

HugName	Capacity	Minimum	Aleph	Beth	Gimmel
Art Room	12	6	1	0	1
Soccer	20	8	1	1	0
Aleph, Beth, Gimmel columns = period columns (can be changed/mapped in-app).
preferences.csv
Each camper’s ordered activity choices for each period.

CamperID	Aleph_1	Aleph_2	...	Beth_1	beth_2	...	Gimmel_5
1001	Soccer	Art	...	Art	Soccer	...	Soccer
Add as many preferences per period as you want (columns must be named with Period_PreferenceRank).

🛠️ How It Works
Upload your activities (hugim.csv) and preferences (preferences.csv) files.
Map each file’s columns to the expected roles.
Edit uploaded data directly in the browser if needed.
Run allocation — the app:
Assigns campers to activities based on ranked preferences.
Randomly assigns any campers who cannot be given their stated preferences, while preventing repeats.
Cancels activities that don’t meet minimums and reallocates affected campers.
Download results and view visual summaries.
📊 Outputs
assignments_output.csv — main allocation results.
stats_output.csv — summary statistics and period-by-period hugim breakdowns.
unassigned_campers_output.csv — who could not be placed and why.
All outputs can be downloaded from the Streamlit UI.

⚙️ Advanced Features
Multi-week “cumulative score” support.
Detailed “reasons” for unassigned cases.
Graceful handling of upload or mapping errors.
Extensible: period names, number of preferences, and column headers all customizable.
🌐 Deployment
Ready for Streamlit Cloud or self-hosted (see deployment)!
No database needed; app works solely with CSV files.
🙋 FAQ
Q: Can a camper get assigned to the same activity twice?
A: No, assignments enforce unique Hug per camper per week, unless you disable that constraint in the code.

Q: What happens to activities with too few sign-ups?
A: They are canceled and campers are reallocated.

Q: How do I add more periods or preferences per period?
A: Adjust your files accordingly and map columns in the UI.

🖋️ Credits & License
Developed and maintained by Dor Posner
Contact: dorposner@gmail.com
MIT License

📬 Feedback & Contributions
Suggestions and pull requests welcome!
Open an issue or email: dorposner@gmail.com

Enjoy efficient and fair Hug allocations for your camp!
