# 🏕️ CYJ Hugim Activity Allocation Web App

A flexible, user-friendly Streamlit application for assigning campers to activities ("Hugim") at summer camps, fully respecting camper preferences and activity constraints.

> **Recent Update**: Fixed Activity class initialization to properly handle required 'periods' parameter.

## ✨ Features

- **Flexible Data Input**: Upload CSV files for activities and camper preferences
- **In-Browser Editing**: Edit activities and camper preferences directly in the admin interface
- **Robust Allocation**: Assigns campers based on ranked preferences and activity constraints
- **State Persistence**: Saves application state between sessions
- **Responsive UI**: Clean, modern interface with real-time updates
- **Data Validation**: Ensures data integrity with comprehensive validation

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/dorposner/Hugim.git
   cd Hugim
   ```

2. **Set up a virtual environment (recommended)**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the application**
   ```bash
   streamlit run app.py
   ```
   The application will open in your default web browser at http://localhost:8501/

5. **Login**
   - Username: `admin`
   - Password: `admin123`

   > **Security Note**: Change the default credentials in production!

## 📁 Project Structure

```
src/
├── models/                  # Data models
│   ├── __init__.py
│   ├── camper.py           # Camper model and preferences
│   └── period.py           # Period and activity models
│
├── pages/
│   └── admin/
│       └── dashboard.py    # Main admin interface
│
├── utils/
│   ├── __init__.py
│   ├── state.py           # Session state management
│   ├── loaders.py         # Data loading and saving
│   ├── editors.py         # Data editing interfaces
│   └── ui/
│       ├── __init__.py
│       └── components.py  # Reusable UI components
│
└── data/
    ├── uploads/          # Uploaded CSV files
    └── state/             # Application state files
```

## 📝 File Formats

### Activities (hugim.csv)
```csv
HugName,Capacity,Minimum,Aleph,Beth,Gimmel
Art Room,12,6,1,0,1
Soccer,20,8,1,1,0
```
- **HugName**: Activity name
- **Capacity**: Maximum number of campers
- **Minimum**: Minimum campers needed to run the activity
- **Period columns (Aleph, Beth, Gimmel)**: 1 if offered in that period, 0 otherwise

### Preferences (preferences.csv)
```csv
CamperID,Aleph_1,Aleph_2,Beth_1,Beth_2,Gimmel_1,Gimmel_2
1001,Soccer,Art,Art,Soccer,Soccer,Art
1002,Art,Soccer,Soccer,Art,Art,Soccer
```
- **CamperID**: Unique identifier for each camper
- **Period_N**: N-th preference for the period (e.g., Aleph_1 = 1st choice for Aleph period)

## 🛠️ Development

### Project Structure

```
src/
├── models/           # Data models and business logic
│   ├── __init__.py
│   ├── activity.py   # Activity model and related logic
│   ├── camper.py     # Camper model and preferences
│   └── period.py     # Period and scheduling logic
├── pages/            # Streamlit page modules
│   ├── admin/        # Admin interface
│   └── camper/       # Camper interface
└── utils/            # Utility functions
    ├── editors.py    # Data editing interfaces
    ├── loaders.py    # Data loading utilities
    └── state.py      # Session state management
```

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/dorposner/Hugim.git
   cd Hugim
   ```

2. **Set up development environment**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   
   # Install development dependencies
   pip install -r requirements-dev.txt
   ```

3. **Run the development server**
   ```bash
   streamlit run app.py
   ```

### Testing

Run the test suite:
```bash
pytest tests/
```

### Code Style

This project follows PEP 8 style guidelines. Before committing, please run:
```bash
black .
flake8
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Icons by [EmojiOne](https://www.joypixels.com/)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

📊 Outputs
assignments_output.csv — main allocation results.
stats_output.csv — summary statistics and period-by-period hugim breakdowns.
unassigned_campers_output.csv — who could not be placed and why.

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
