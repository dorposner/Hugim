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
# HELPER FUNCTIONS
# ---------------------------------------------------------
def recalculate_all_metadata(assignments_df, prefs_df, periods, camper_id_col, pref_prefixes):
    """
    Recalculates metadata (_How, Week_Score) for the entire assignments dataframe
    based on the current assignments and preferences.
    """
    PREF_POINTS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}

    # Normalize Preferences
    normalized_prefs = {}
    if prefs_df is not None and camper_id_col in prefs_df.columns:
        for _, row in prefs_df.iterrows():
            raw_id = row[camper_id_col]
            if pd.isna(raw_id):
                continue
            cid = str(raw_id).strip()
            normalized_prefs[cid] = row
    
    # Create a copy to update
    updated_df = assignments_df.copy()

    # Normalize Assignments ID column just in case
    if "CamperID" in updated_df.columns:
        updated_df["CamperID"] = updated_df["CamperID"].astype(str).str.strip()

    for index, row in updated_df.iterrows():
        cid = row.get("CamperID")
        # Skip empty rows
        if pd.isna(cid) or str(cid).strip() == "":
            continue

        cid = str(cid).strip()
        pref_row = normalized_prefs.get(cid)

        week_score = 0

        for period in periods:
            assign_col = f"{period}_Assigned"
            how_col = f"{period}_How"

            if assign_col not in updated_df.columns:
                continue

            assigned_act = row.get(assign_col)

            # Handle empty assignment
            if pd.isna(assigned_act) or str(assigned_act).strip() == "" or str(assigned_act).lower() == "none":
                updated_df.at[index, how_col] = None
                continue

            assigned_act_str = str(assigned_act).strip()

            matched_rank = None
            if pref_row is not None:
                # CRITICAL FIX: Fallback to period name if prefix is missing
                prefix = pref_prefixes.get(period)
                if not prefix:
                    prefix = period # Default behavior
                
                if prefix:
                    for r in range(1, 6):
                        p_col = f"{prefix}_{r}"
                        if p_col in pref_row:
                            p_val = pref_row[p_col]
                            if pd.notna(p_val) and str(p_val).strip() == assigned_act_str:
                                matched_rank = r
                                break

            if matched_rank:
                updated_df.at[index, how_col] = f"Pref_{matched_rank}"
                week_score += PREF_POINTS.get(matched_rank, 0)
            else:
                updated_df.at[index, how_col] = "Manual_Override"

        updated_df.at[index, "Week_Score"] = week_score

    return updated_df

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

# Ensure periods are detected if list is empty (fallback)
if not periods:
    cols = assignments_df.columns
    periods = [c.replace("_Assigned", "") for c in cols if c.endswith("_Assigned")]

# Name Lookup Helper
name_map = {}
if prefs_df is not None:
    possible_names = ["Name", "Full Name", "FullName", "Student Name", "Student", "First Name", "First"]
    found_col = None
    for c in possible_names:
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

    required = ['Activity', 'Period', 'CamperID']
    if not all(col in df_roster.columns for col in required):
        return None

    groups = df_roster.groupby(['Activity', 'Period'])

    for (activity, period), group in groups:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"{title}", ln=True, align='C')
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Activity: {activity}", ln=True, align='L')
        pdf.cell(0, 10, f"Period: {period}", ln=True, align='L')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Camper ID", 1)
        pdf.cell(80, 10, "Name", 1)
        pdf.cell(60, 10, "Type", 1)
        pdf.ln()

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

    if hugim_df is not None and hugname_col in hugim_df.columns:
        all_activities = sorted(hugim_df[hugname_col].astype(str).unique())
    else:
        all_acts = set()
        for p in periods:
            if f"{p}_Assigned" in assignments_df.columns:
                all_acts.update(assignments_df[f"{p}_Assigned"].dropna().unique())
        all_activities = sorted(list(all_acts))

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        select_all = st.checkbox("Select All Activities")
        if select_all:
            selected_activities = all_activities
            st.multiselect("Select Activity", all_activities, default=all_activities, disabled=True)
        else:
            selected_activities = st.multiselect("Select Activity", all_activities)

    with col_f2:
        selected_periods = st.multiselect("Select Period(s)", periods, default=periods)

    show_detailed = st.checkbox("Show detailed info (Assignment Type)")

    if selected_activities and selected_periods:
        roster_rows = []
        for period in selected_periods:
            assign_col = f"{period}_Assigned"
            how_col = f"{period}_How"

            if assign_col in assignments_df.columns:
                filtered = assignments_df[assignments_df[assign_col].isin(selected_activities)]

                for _, row in filtered.iterrows():
                    cid = row["CamperID"]
                    assigned_act = row[assign_col]

                    data = {
                        "CamperID": cid,
                        "Period": period,
                        "Activity": assigned_act
                    }
                    name_val = name_map.get(str(cid), "")
                    if name_val:
                        data["Name"] = name_val

                    data["Assignment Type"] = row.get(how_col, "")
                    roster_rows.append(data)

        if roster_rows:
            cols_order = ["CamperID"]
            if "Name" in roster_rows[0]:
                cols_order.append("Name")
            cols_order.append("Period")
            cols_order.append("Activity")
            if show_detailed:
                cols_order.append("Assignment Type")

            roster_df = pd.DataFrame(roster_rows)
            cols_final = [c for c in cols_order if c in roster_df.columns]
            roster_df = roster_df[cols_final]

            st.dataframe(roster_df, use_container_width=True)

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                csv = roster_df.to_csv(index=False).encode('utf-8')
                st.download_button("⬇️ Download Roster as CSV", csv, "roster_export.csv", "text/csv")
            with col_d2:
                try:
                    pdf_bytes = generate_pdf(roster_df)
                    if pdf_bytes:
                        st.download_button("⬇️ Download Roster as PDF", pdf_bytes, "roster_export.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
        else:
            st.info("No campers assigned to selected activities/periods.")
    else:
        st.info("Select at least one activity and one period.")

# =========================================================
# TAB 2: CAMPER LOOKUP
# =========================================================
with tab2:
    st.header("Camper Lookup")
    all_campers = sorted(assignments_df["CamperID"].astype(str).unique())
    format_func = lambda x: f"{x} ({name_map.get(str(x), '')})" if str(x) in name_map else str(x)
    selected_camper = st.selectbox("Search Camper (ID)", all_campers, format_func=format_func)

    if selected_camper:
        camper_row = assignments_df[assignments_df["CamperID"].astype(str) == selected_camper].iloc[0]
        st.metric("Satisfaction Score", camper_row.get("Week_Score", 0))
        st.subheader("Weekly Schedule")

        schedule_data = []
        for period in periods:
            assigned = camper_row.get(f"{period}_Assigned", "Unassigned")
            how = camper_row.get(f"{period}_How", "")
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
        cap_col = st.session_state.get("capacity", "Capacity")
        capacity_map = {}
        if hugim_df is not None and cap_col in hugim_df.columns and hugname_col in hugim_df.columns:
            for _, row in hugim_df.iterrows():
                capacity_map[str(row[hugname_col])] = row[cap_col]

        counts = {}
        activities = set()
        for period in periods:
            col = f"{period}_Assigned"
            if col in assignments_df.columns:
                vc = assignments_df[col].value_counts()
                for act, count in vc.items():
                    counts[(act, period)] = count
                    activities.add(act)
        activities.update(capacity_map.keys())

        data = []
        for act in sorted(list(activities)):
            row = {"Activity": act}
            cap = capacity_map.get(act, "?")
            for period in periods:
                enrolled = counts.get((act, period), 0)
                row[period] = f"{enrolled}/{cap}" if cap != "?" else f"{enrolled}/?"
            data.append(row)

        cap_df = pd.DataFrame(data).set_index("Activity")
        def color_capacity(val):
            if not isinstance(val, str) or "/" not in val: return ""
            try:
                enrolled, cap = val.split("/")
                if cap == "?" or float(cap) == 0: return ""
                pct = float(enrolled) / float(cap)
                if pct >= 1.0: return "background-color: #ffcccc; color: black;"
                elif pct >= 0.8: return "background-color: #ffffcc; color: black;"
                return "background-color: #ccffcc; color: black;"
            except: return ""

        st.dataframe(cap_df.style.map(color_capacity), use_container_width=True)

# =========================================================
# TAB 4: ANALYTICS
# =========================================================
with tab4:
    st.header("Analytics & Stats")
    col1, col2 = st.columns(2)
    
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

    if prefs_df is not None:
        req_counts = {}
        for period in periods:
            prefix = st.session_state.get(f"pref_prefix_{period}", period) # Fallback here too
            target_cols = [f"{prefix}_1"] if prefix else []
            if not target_cols: # Fallback to scanning
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

# =========================================================
# TAB 5: MANUAL EDITS
# =========================================================
with tab5:
    st.header("✏️ Manual Editor (Super Admin)")
    st.info("Changes made here bypass capacity constraints and will trigger a recalculation of satisfaction scores.")

    current_df = st.session_state["assignments_df"]
    edited_df = st.data_editor(current_df, key="manual_editor", num_rows="fixed")

    if not edited_df.equals(current_df):
        with st.spinner("Processing updates (Full Recalculation)..."):
            # Prepare prefixes with fallback
            pref_prefixes = {}
            for p in periods:
                val = st.session_state.get(f"pref_prefix_{p}")
                if not val:
                    val = p # FALLBACK: Use period name as prefix
                pref_prefixes[p] = val

            updated_df = recalculate_all_metadata(edited_df, prefs_df, periods, camper_id_col, pref_prefixes)
            st.session_state["assignments_df"] = updated_df

            # Auto-Save
            current_camp = st.session_state.get("current_camp_name")
            if current_camp:
                # Reconstruct config
                save_periods = st.session_state.get("periods_selected", [])
                prefixes = {}
                for key in st.session_state.keys():
                    if key.startswith("pref_prefix_"):
                        prefixes[key.replace("pref_prefix_", "")] = st.session_state[key]
                
                # Add inferred prefixes to save config if missing
                for p, val in pref_prefixes.items():
                    if p not in prefixes:
                        prefixes[p] = val

                config_data = {
                    'config': {
                        'col_hug_name': st.session_state.get("hugname"),
                        'col_capacity': st.session_state.get("capacity"),
                        'col_minimum': st.session_state.get("min_campers"),
                        'col_camper_id': st.session_state.get("camperid"),
                        'max_preferences_per_period': st.session_state.get("detected_max_prefs", 5)
                    },
                    'periods': periods,
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
                st.rerun()
