import streamlit as st
import pandas as pd
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

st.title("📊 Reports & Insights")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Activity Rosters", "Camper Lookup", "Capacity Overview", "Analytics & Stats"])

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

    # Filters (In main area to avoid sidebar clutter across tabs)
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_activity = st.selectbox("Select Activity", all_activities)
    with col_f2:
        selected_periods = st.multiselect("Select Period(s)", periods, default=periods)

    show_detailed = st.checkbox("Show detailed info (Assignment Type)")

    if selected_activity and selected_periods:
        # Build the roster
        roster_rows = []
        for period in selected_periods:
            assign_col = f"{period}_Assigned"
            how_col = f"{period}_How"

            if assign_col in assignments_df.columns:
                # Filter
                filtered = assignments_df[assignments_df[assign_col] == selected_activity]

                for _, row in filtered.iterrows():
                    cid = row["CamperID"]
                    data = {
                        "CamperID": cid,
                        "Period": period,
                    }
                    # Add Name if available
                    name_val = name_map.get(str(cid), "")
                    if name_val:
                        data["Name"] = name_val

                    if show_detailed:
                        data["Assignment Type"] = row.get(how_col, "")

                    roster_rows.append(data)

        if roster_rows:
            # Reorder columns to put Name after ID
            cols_order = ["CamperID"]
            if "Name" in roster_rows[0]:
                cols_order.append("Name")
            cols_order.append("Period")
            if show_detailed:
                cols_order.append("Assignment Type")

            roster_df = pd.DataFrame(roster_rows)
            # Ensure columns exist before selecting
            cols_final = [c for c in cols_order if c in roster_df.columns]
            roster_df = roster_df[cols_final]

            st.dataframe(roster_df, use_container_width=True)

            csv = roster_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Download Roster as CSV",
                csv,
                f"roster_{selected_activity}.csv",
                "text/csv",
                key='download-roster'
            )
        else:
            st.info(f"No campers assigned to {selected_activity} for selected periods.")
    else:
        st.info("Select an activity and at least one period.")

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
        camper_row = assignments_df[assignments_df["CamperID"] == selected_camper].iloc[0]

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
