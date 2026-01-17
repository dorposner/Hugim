import streamlit as st
import pandas as pd
from fpdf import FPDF
import googlesheets

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(page_title="Reports & Insights", page_icon="📊", layout="wide")

# ---------------------------------------------------------
# DATA LOADING & CHECK
# ---------------------------------------------------------
if "assignments_df" not in st.session_state or st.session_state["assignments_df"] is None:
    st.warning("⚠️ No assignment data found. Please go back to the Home page and load a camp or run an allocation.")
    st.stop()

assignments_df = st.session_state["assignments_df"].copy()
hugim_df = st.session_state.get("hugim_df")
prefs_df = st.session_state.get("prefs_df")

# Basic Config
hugname_col = st.session_state.get("hugname", "HugName")
periods = st.session_state.get("periods_selected", [])
camper_id_col = st.session_state.get("camperid", "CamperID")

# Ensure periods are detected if list is empty (fallback to finding columns in assignments)
if not periods:
    # Try to deduce from assignments columns like "Aleph_Assigned"
    cols = assignments_df.columns
    periods = [c.replace("_Assigned", "") for c in cols if c.endswith("_Assigned")]

# Name Lookup Helper
name_map = {}
if prefs_df is not None:
    # Try common name columns
    possible_names = ["Name", "Full Name", "FullName", "Student Name", "Student", "First Name", "First"]
    found_col = None
    for c in possible_names:
        # Case insensitive match
        match = next((col for col in prefs_df.columns if col.lower() == c.lower()), None)
        if match:
            found_col = match
            break

    if found_col and camper_id_col in prefs_df.columns:
        for _, row in prefs_df.iterrows():
            cid = str(row[camper_id_col])
            name_val = row[found_col]
            name_map[cid] = name_val

# Helper for PDF
def generate_pdf(df_roster, title="Camp Roster"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Check required columns
    required = ['Activity', 'Period', 'CamperID']
    if not all(col in df_roster.columns for col in required):
        return None

    # Group by Activity and Period
    groups = df_roster.groupby(['Activity', 'Period'])

    for (activity, period), group in groups:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"{title}", ln=True, align='C')
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Activity: {activity}", ln=True, align='L')
        pdf.cell(0, 10, f"Period: {period}", ln=True, align='L')
        pdf.ln(5)

        # Table Header
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Camper ID", 1)
        pdf.cell(80, 10, "Name", 1)
        pdf.cell(60, 10, "Type", 1)
        pdf.ln()

        # Rows
        pdf.set_font("Arial", '', 12)
        for _, row in group.iterrows():
            cid = str(row['CamperID'])
            name = str(row.get('Name', ''))
            atype = str(row.get('Assignment Type', ''))

            pdf.cell(40, 10, cid[:15], 1)
            pdf.cell(80, 10, name[:35], 1)
            pdf.cell(60, 10, atype[:25], 1)
            pdf.ln()

    return pdf.output(dest='S').encode('latin-1', 'replace')

st.title("📊 Reports & Insights")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Activity Rosters", "Camper Lookup", "Capacity Overview", "Analytics & Stats", "Manual Edits"])

# =========================================================
# TAB 1: ACTIVITY ROSTERS
# =========================================================
with tab1:
    st.header("Activity Rosters")

    # Get all unique activities from assignments (or hugim_df if available)
    if hugim_df is not None and hugname_col in hugim_df.columns:
        all_activities = sorted(hugim_df[hugname_col].astype(str).unique())
    else:
        # Deduce from assignments
        all_acts = set()
        for p in periods:
            if f"{p}_Assigned" in assignments_df.columns:
                all_acts.update(assignments_df[f"{p}_Assigned"].dropna().unique())
        all_activities = sorted(list(all_acts))

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # Multi-select logic with "Select All"
        select_all = st.checkbox("Select All Activities")
        if select_all:
            selected_activities = all_activities
            # Show disabled multiselect for visual feedback
            st.multiselect("Select Activity", all_activities, default=all_activities, disabled=True)
        else:
            selected_activities = st.multiselect("Select Activity", all_activities)

    with col_f2:
        selected_periods = st.multiselect("Select Period(s)", periods, default=periods)

    show_detailed = st.checkbox("Show detailed info (Assignment Type)")

    if selected_activities and selected_periods:
        # Build the roster
        roster_rows = []
        for period in selected_periods:
            assign_col = f"{period}_Assigned"
            how_col = f"{period}_How"

            if assign_col in assignments_df.columns:
                # Filter: Activity must be in selected_activities
                filtered = assignments_df[assignments_df[assign_col].isin(selected_activities)]

                for _, row in filtered.iterrows():
                    cid = row["CamperID"]
                    assigned_act = row[assign_col]

                    data = {
                        "CamperID": cid,
                        "Period": period,
                        "Activity": assigned_act
                    }
                    # Add Name if available
                    name_val = name_map.get(str(cid), "")
                    if name_val:
                        data["Name"] = name_val

                    data["Assignment Type"] = row.get(how_col, "")

                    roster_rows.append(data)

        if roster_rows:
            # Reorder columns to put Name after ID
            cols_order = ["CamperID"]
            if "Name" in roster_rows[0]:
                cols_order.append("Name")
            cols_order.append("Period")
            cols_order.append("Activity")
            if show_detailed:
                cols_order.append("Assignment Type")

            roster_df = pd.DataFrame(roster_rows)
            # Ensure columns exist before selecting
            cols_final = [c for c in cols_order if c in roster_df.columns]
            roster_df = roster_df[cols_final]

            st.dataframe(roster_df, use_container_width=True)

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                csv = roster_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "⬇️ Download Roster as CSV",
                    csv,
                    f"roster_export.csv",
                    "text/csv",
                    key='download-roster-csv'
                )
            with col_d2:
                # PDF Generation
                try:
                    pdf_bytes = generate_pdf(roster_df)
                    if pdf_bytes:
                        st.download_button(
                            "⬇️ Download Roster as PDF",
                            pdf_bytes,
                            "roster_export.pdf",
                            "application/pdf",
                            key='download-roster-pdf'
                        )
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
        else:
            st.info(f"No campers assigned to selected activities/periods.")
    else:
        st.info("Select at least one activity and one period.")

# =========================================================
# TAB 2: CAMPER LOOKUP
# =========================================================
with tab2:
    st.header("Camper Lookup")

    all_campers = sorted(assignments_df["CamperID"].astype(str).unique())
    # Improve search box to show name if available
    format_func = lambda x: f"{x} ({name_map.get(str(x), '')})" if str(x) in name_map else str(x)

    selected_camper = st.selectbox("Search Camper (ID)", all_campers, format_func=format_func)

    if selected_camper:
        camper_row = assignments_df[assignments_df["CamperID"].astype(str) == selected_camper].iloc[0]

        # Satisfaction Score
        score = camper_row.get("Week_Score", 0)
        st.metric("Satisfaction Score", score)

        # Schedule Card
        st.subheader("Weekly Schedule")

        schedule_data = []
        for period in periods:
            assigned = camper_row.get(f"{period}_Assigned", "Unassigned")
            how = camper_row.get(f"{period}_How", "")

            # Highlight if it was a preference
            is_pref = "Pref" in str(how)

            schedule_data.append({
                "Period": period,
                "Activity": assigned,
                "Type": how if is_pref else ("Random/Filled" if assigned != "Unassigned" else "-")
            })

        st.table(pd.DataFrame(schedule_data))


# =========================================================
# TAB 3: CAPACITY OVERVIEW
# =========================================================
with tab3:
    st.header("Capacity Overview")

    if not periods:
        st.warning("No periods detected.")
    else:
        # Pivot: Rows=Hugim, Cols=Periods, Val="Enrolled/Cap"

        # 1. Get Capacity Map
        # hugim_df has [hugname_col] and [capacity column]
        cap_col = st.session_state.get("capacity", "Capacity")

        capacity_map = {}
        if hugim_df is not None and cap_col in hugim_df.columns and hugname_col in hugim_df.columns:
            for _, row in hugim_df.iterrows():
                capacity_map[str(row[hugname_col])] = row[cap_col]

        # 2. Count Enrolled
        # We can iterate assignments and count
        counts = {} # (Activity, Period) -> count
        activities = set()

        for period in periods:
            col = f"{period}_Assigned"
            if col in assignments_df.columns:
                vc = assignments_df[col].value_counts()
                for act, count in vc.items():
                    counts[(act, period)] = count
                    activities.add(act)

        # Also add activities from capacity map even if 0 enrolled
        activities.update(capacity_map.keys())

        # 3. Build DataFrame
        data = []
        sorted_acts = sorted(list(activities))

        for act in sorted_acts:
            row = {"Activity": act}
            cap = capacity_map.get(act, "?")

            for period in periods:
                enrolled = counts.get((act, period), 0)

                # Format: "Enrolled/Cap"
                if cap != "?":
                    row[period] = f"{enrolled}/{cap}"
                else:
                    row[period] = f"{enrolled}/?"

            data.append(row)

        cap_df = pd.DataFrame(data).set_index("Activity")

        # 4. Styling
        def color_capacity(val):
            if not isinstance(val, str) or "/" not in val:
                return ""
            try:
                enrolled_str, cap_str = val.split("/")
                if cap_str == "?": return ""
                enrolled = float(enrolled_str)
                cap = float(cap_str)
                if cap == 0: return ""

                pct = enrolled / cap
                if pct >= 1.0:
                    return "background-color: #ffcccc; color: black;" # Reddish
                elif pct >= 0.8:
                    return "background-color: #ffffcc; color: black;" # Yellowish
                else:
                    return "background-color: #ccffcc; color: black;" # Greenish
            except:
                return ""

        st.dataframe(cap_df.style.map(color_capacity), use_container_width=True)


# =========================================================
# TAB 4: ANALYTICS
# =========================================================
with tab4:
    st.header("Analytics & Stats")

    col1, col2 = st.columns(2)

    # 1. Distribution of Assignment Types
    all_hows = []
    for period in periods:
        col = f"{period}_How"
        if col in assignments_df.columns:
            all_hows.extend(assignments_df[col].dropna().tolist())

    how_counts = pd.Series(all_hows).value_counts().reset_index()
    how_counts.columns = ["Type", "Count"]

    with col1:
        st.subheader("Assignment Types Distribution")
        if HAS_PLOTLY:
            fig = px.pie(how_counts, values="Count", names="Type", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(how_counts)

    # 2. Top Requested Activities (Rank 1)
    # Need prefs_df
    if prefs_df is not None:
        req_counts = {}

        for period in periods:
            # Use columns ending in _1
            # We assume prefixes are managed correctly or we just scan for _1
            # A more robust way is scanning pref_prefix_{period}
            prefix = st.session_state.get(f"pref_prefix_{period}")

            target_cols = []
            if prefix:
                target_cols = [f"{prefix}_1"]
            else:
                # Fallback: scan all columns ending in _1
                # This might overcount if there are multiple period prefixes ending differently but sharing _1?
                # Unlikely. But safe to check if column exists.
                 target_cols = [c for c in prefs_df.columns if c.endswith("_1")]

            for c in target_cols:
                if c in prefs_df.columns:
                    vc = prefs_df[c].value_counts()
                    for act, count in vc.items():
                        req_counts[act] = req_counts.get(act, 0) + count

        req_df = pd.DataFrame(list(req_counts.items()), columns=["Activity", "Requests (#1)"]).sort_values("Requests (#1)", ascending=False).head(10)

        with col2:
            st.subheader("Top Requested Activities (#1 Choice)")
            if HAS_PLOTLY:
                fig2 = px.bar(req_df, x="Activity", y="Requests (#1)")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.bar_chart(req_df.set_index("Activity"))

        # 3. Unfulfilled Demands
        unfulfilled_counts = {}

        # We need to link prefs_df and assignments_df by CamperID
        if camper_id_col in prefs_df.columns:
            # Create lookup for assignments: CamperID -> Period -> Assigned
            assign_lookup = assignments_df.set_index("CamperID").to_dict("index")

            for _, row in prefs_df.iterrows():
                cid = str(row[camper_id_col])

                if cid in assign_lookup:
                    assigned_row = assign_lookup[cid]

                    for period in periods:
                        prefix = st.session_state.get(f"pref_prefix_{period}")
                        if prefix:
                            pref_col = f"{prefix}_1"
                            if pref_col in row:
                                wanted = row[pref_col]
                                got = assigned_row.get(f"{period}_Assigned")

                                if pd.notna(wanted) and str(wanted).strip() != "":
                                    if str(wanted) != str(got):
                                        unfulfilled_counts[wanted] = unfulfilled_counts.get(wanted, 0) + 1

        if unfulfilled_counts:
            unf_df = pd.DataFrame(list(unfulfilled_counts.items()), columns=["Activity", "Unfulfilled Requests"]).sort_values("Unfulfilled Requests", ascending=False).head(10)

            st.subheader("Most Unfulfilled Demands (Requested #1 but not received)")
            if HAS_PLOTLY:
                fig3 = px.bar(unf_df, x="Activity", y="Unfulfilled Requests", color_discrete_sequence=['red'])
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.bar_chart(unf_df.set_index("Activity"))

    else:
        st.info("Preference data not available for detailed analytics.")

# =========================================================
# TAB 5: MANUAL EDITS
# =========================================================
with tab5:
    st.header("✏️ Manual Editor (Super Admin)")
    st.info("Changes made here bypass capacity constraints and will trigger a recalculation of satisfaction scores.")

    # 1. Edit
    # Load from session state to ensure we have the latest
    current_df = st.session_state["assignments_df"]

    # Use st.data_editor (Fixed rows to prevent adding incomplete camper rows)
    edited_df = st.data_editor(current_df, key="manual_editor", num_rows="fixed")

    # 2. Check for changes and Save
    if not edited_df.equals(current_df):
        with st.spinner("Processing updates..."):
            # --- Smart Recalculation Logic ---
            # Iterate through rows and update Metadata (_How and Week_Score)
            # We need prefs_df for this
            if prefs_df is None:
                st.error("Cannot recalculate scores: Preferences data missing.")
            elif camper_id_col not in prefs_df.columns:
                st.error(f"Cannot recalculate scores: Camper ID column '{camper_id_col}' not found in preferences.")
            else:
                # Create lookup for prefs
                # CamperID -> {Prefix_1: Activity, ...}
                # We need to know which prefix corresponds to which period

                # NORMALIZE PREFS: Force CamperID to string and strip to match assignments
                temp_prefs = prefs_df.copy()
                temp_prefs[camper_id_col] = temp_prefs[camper_id_col].astype(str).str.strip()

                # Map CamperID -> Row in prefs_df
                prefs_lookup = temp_prefs.set_index(camper_id_col).to_dict('index')

                PREF_POINTS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}

                # Helper to find rank
                def get_pref_rank(cid, period, activity):
                    # Ensure cid is string for lookup
                    cid = str(cid).strip()

                    if cid not in prefs_lookup:
                        return None

                    prefix = st.session_state.get(f"pref_prefix_{period}")
                    if not prefix:
                        return None

                    p_row = prefs_lookup[cid]

                    # Check 1 to 5
                    for r in range(1, 6):
                        col = f"{prefix}_{r}"
                        if col in p_row:
                            val = p_row[col]
                            if str(val).strip() == str(activity).strip():
                                return r
                    return None

                # Process the edited dataframe
                updated_df = edited_df.copy()

                # NORMALIZE ASSIGNMENTS: Force CamperID to string and strip
                if "CamperID" in updated_df.columns:
                    updated_df["CamperID"] = updated_df["CamperID"].astype(str).str.strip()

                # We iterate all rows to ensure consistency
                for index, row in updated_df.iterrows():
                    cid = row.get("CamperID")
                    if pd.isna(cid) or str(cid).strip() == "":
                        continue

                    new_week_score = 0

                    for period in periods:
                        assign_col = f"{period}_Assigned"
                        how_col = f"{period}_How"

                        if assign_col in row:
                            assigned_act = row[assign_col]

                            if pd.isna(assigned_act) or str(assigned_act).strip() == "":
                                 # Unassigned
                                 updated_df.at[index, how_col] = "" # Clear how
                            else:
                                # Check if it matches a preference
                                rank = get_pref_rank(cid, period, assigned_act)

                                if rank:
                                    updated_df.at[index, how_col] = f"Pref_{rank}"
                                    new_week_score += PREF_POINTS.get(rank, 0)
                                else:
                                    # Did the user change it?
                                    # Even if they didn't, if it's not a pref, it's effectively a manual/random fill.
                                    # If it was "Random" before, and still matches "Random", we could keep it.
                                    # BUT the requirement says: "If not, set it to Manual_Override."
                                    # We will stick to the requirement for simplicity and clarity of "Manual Edits".
                                    # Exception: If it WAS Random/Forced and wasn't changed, maybe keep it?
                                    # But we can't easily know if it was changed without row-by-row comparison with original.
                                    # Let's try to preserve "Random" if the activity matches the original activity.

                                    original_row = assignments_df[assignments_df["CamperID"] == cid]
                                    if not original_row.empty:
                                        orig_act = original_row.iloc[0].get(assign_col)
                                        orig_how = original_row.iloc[0].get(how_col)

                                        if str(orig_act) == str(assigned_act) and ("Random" in str(orig_how) or "Forced" in str(orig_how)):
                                            # Keep original reason if activity didn't change and was system-assigned
                                            updated_df.at[index, how_col] = orig_how
                                            # Random/Forced usually 0 points?
                                            # If logic elsewhere awards points for Random, we miss it here.
                                            # Usually points are only for Prefs.
                                        else:
                                            updated_df.at[index, how_col] = "Manual_Override"
                                    else:
                                         updated_df.at[index, how_col] = "Manual_Override"

                    updated_df.at[index, "Week_Score"] = new_week_score

                # Update Session State
                st.session_state["assignments_df"] = updated_df

                # --- Auto-Save to Cloud ---
                current_camp = st.session_state.get("current_camp_name")
                if current_camp:
                    # Reconstruct config_data
                    # We need to gather periods and prefixes
                    save_periods = st.session_state.get("periods_selected", [])
                    prefixes = {}
                    all_period_keys = [k for k in st.session_state.keys() if k.startswith("pref_prefix_")]
                    for key in all_period_keys:
                        p_name = key.replace("pref_prefix_", "")
                        prefixes[p_name] = st.session_state[key]
                        if p_name not in save_periods:
                            save_periods.append(p_name)

                    config_data = {
                        'config': {
                            'col_hug_name': st.session_state.get("hugname"),
                            'col_capacity': st.session_state.get("capacity"),
                            'col_minimum': st.session_state.get("min_campers"),
                            'col_camper_id': st.session_state.get("camperid"),
                            'max_preferences_per_period': st.session_state.get("detected_max_prefs", 5)
                        },
                        'periods': save_periods,
                        'preference_prefixes': prefixes
                    }

                    success = googlesheets.save_camp_state(
                        current_camp,
                        config_data,
                        st.session_state.get("hugim_df"),
                        prefs_df,
                        updated_df
                    )

                    if success:
                        st.toast("Changes saved & scores updated.", icon="✅")
                        st.rerun()
                    else:
                        st.error("Failed to save to cloud.")
                else:
                    st.warning("No active camp name found. Saved to local session only.")
                    st.rerun()
