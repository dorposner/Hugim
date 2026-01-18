import streamlit as st
import pandas as pd
import googlesheets
import sys
from pathlib import Path

# Add parent directory to path to allow importing ui_utils
sys.path.append(str(Path(__file__).parent.parent))
import ui_utils

try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="Super Admin Dashboard", page_icon="🛡️", layout="wide")

ui_utils.render_sidebar()

# Security Lock
if not st.session_state.get("authenticated"):
    st.error("Please log in first.")
    st.stop()

if st.session_state.get("user_role") != "admin":
    st.error("Access Denied: Super Admin privileges required.")
    st.stop()

st.title("🛡️ Super Admin Dashboard")

# Navigation
tab1, tab2, tab3, tab4 = st.tabs(["Global Overview", "User Management", "Camp Operations", "Maintenance"])

# --- TAB 1: Global Overview ---
with tab1:
    st.header("Global Overview")

    if st.button("Refresh Data"):
        st.rerun()

    stats = googlesheets.get_global_stats()

    col1, col2 = st.columns(2)
    col1.metric("Total Users", stats['total_users'])
    col2.metric("Total Camps", stats['total_camps'])

    st.subheader("Users per Camp")
    users_per_camp = stats['users_per_camp']
    if not users_per_camp.empty:
        if PLOTLY_AVAILABLE:
            fig = px.bar(users_per_camp, x='camp_name', y='count', title="Users per Camp")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(users_per_camp.set_index('camp_name')['count'])
    else:
        st.info("No user data available.")

    st.subheader("All Users")
    all_users_df = googlesheets.get_all_users()
    st.dataframe(all_users_df, use_container_width=True)

    st.divider()
    st.subheader("Deep Camp Analytics")

    if st.button("🔄 Refresh Global Analytics"):
        progress_bar = st.progress(0, text="Fetching camp data...")

        def update_progress(p):
            progress_bar.progress(p, text=f"Fetching camp data... {int(p*100)}%")

        analytics_df = googlesheets.get_all_camps_analytics(progress_callback=update_progress)
        progress_bar.empty()
        st.session_state['global_analytics'] = analytics_df

    if 'global_analytics' in st.session_state:
        df_display = st.session_state['global_analytics']

        # Function to highlight cells
        def highlight_unassigned_bg(val):
            if isinstance(val, (int, float)) and val > 0:
                return 'background-color: #ffcccc; color: #990000'
            return ''

        # Apply styling
        st.dataframe(
            df_display.style.map(highlight_unassigned_bg, subset=['Unassigned Slots']),
            use_container_width=True
        )

# --- TAB 2: User Management ---
with tab2:
    st.header("User Management")

    st.subheader("Add New User")
    with st.form("create_user_form"):
        new_email = st.text_input("Email")
        new_password = st.text_input("Password", type="password")

        # Camp selection: can be existing or new
        camp_options = googlesheets.get_all_camp_names()
        camp_mode = st.radio("Camp Selection Mode", ["Select Existing", "Create New / Custom"])

        if camp_mode == "Select Existing":
            new_camp = st.selectbox("Camp Name", camp_options)
        else:
            new_camp = st.text_input("Camp Name (Custom)")

        new_role = st.selectbox("Role", ["user", "admin"])
        # Default enforce_unique to False if creating admin-assigned user (often adding to existing camp)
        # But if creating new camp, maybe we want to enforce it?
        # Actually, for admin override, let's default to False (allow flexibility) but let them check it.
        enforce_unique = st.checkbox("Enforce Unique Camp (Prevent duplicates if creating new)", value=False)

        submitted = st.form_submit_button("Create User")
        if submitted:
            if not new_email or not new_password or not new_camp:
                st.error("All fields are required.")
            else:
                success, msg = googlesheets.create_user(new_email, new_password, new_camp, enforce_unique_camp=enforce_unique)
                if success:
                    # If admin, update role immediately after creation (create_user defaults to 'user')
                    if new_role == "admin":
                         googlesheets.update_user_role(new_email, "admin")
                    st.success(f"User created: {msg}")
                    st.rerun()
                else:
                    st.error(f"Error: {msg}")

    st.divider()

    st.subheader("Edit User")

    # Reload users to get latest
    all_users = googlesheets.get_users()
    user_emails = [u['email'] for u in all_users]

    selected_email = st.selectbox("Select User to Edit", user_emails)

    if selected_email:
        # Find user object
        selected_user = next((u for u in all_users if u['email'] == selected_email), None)

        if selected_user:
            st.info(f"Editing: {selected_user['email']} | Current Role: {selected_user['role']} | Camp: {selected_user['camp_name']}")

            col_u1, col_u2, col_u3 = st.columns(3)

            with col_u1:
                with st.expander("Reset Password"):
                    new_pass = st.text_input("New Password", type="password", key="reset_pass")
                    if st.button("Update Password"):
                        if googlesheets.admin_reset_password(selected_email, new_pass):
                            st.success("Password updated.")
                        else:
                            st.error("Failed to update password.")

            with col_u2:
                with st.expander("Change Role"):
                    new_role_select = st.selectbox("New Role", ["user", "admin"], index=0 if selected_user['role'] == "user" else 1)
                    if st.button("Update Role"):
                        if googlesheets.update_user_role(selected_email, new_role_select):
                            st.success("Role updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update role.")

            with col_u3:
                with st.expander("Change Camp"):
                    current_camp_opts = googlesheets.get_all_camp_names()
                    # Ensure current camp is in options if it's weird
                    if selected_user['camp_name'] not in current_camp_opts:
                        current_camp_opts.append(selected_user['camp_name'])

                    new_camp_select = st.selectbox("Assign to Camp", current_camp_opts, index=current_camp_opts.index(selected_user['camp_name']) if selected_user['camp_name'] in current_camp_opts else 0)
                    if st.button("Update Camp"):
                        if googlesheets.update_user_camp(selected_email, new_camp_select):
                            st.success("Camp updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update camp.")

            st.markdown("### Danger Zone")
            if st.button("DELETE USER", type="primary"):
                if googlesheets.delete_user(selected_email):
                    st.success("User deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete user.")

# --- TAB 3: Camp Operations ---
with tab3:
    st.header("Camp Operations")

    existing_camps = googlesheets.get_all_camp_names()

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.subheader("Rename Camp")
        rename_camp_select = st.selectbox("Select Camp to Rename", [""] + existing_camps)
        rename_new_name = st.text_input("New Name")
        if st.button("Rename Camp"):
            if rename_camp_select and rename_new_name:
                if rename_new_name in existing_camps:
                    st.error("New name already exists!")
                else:
                    with st.spinner("Renaming tabs..."):
                        if googlesheets.rename_camp_tabs(rename_camp_select, rename_new_name):
                            st.success(f"Renamed {rename_camp_select} to {rename_new_name}")
                            st.rerun()
            else:
                st.error("Select a camp and enter a new name.")

    with col_c2:
        st.subheader("Delete Camp")
        delete_camp_select = st.selectbox("Select Camp to Delete", [""] + existing_camps)

        if "confirm_delete_admin" not in st.session_state:
            st.session_state.confirm_delete_admin = False

        if st.button("Delete Camp", key="del_btn_init"):
            if delete_camp_select:
                st.session_state.confirm_delete_admin = True
            else:
                st.error("Select a camp to delete.")

        if st.session_state.confirm_delete_admin and delete_camp_select:
            st.warning(f"Are you sure you want to delete all data for '{delete_camp_select}'? This cannot be undone.")
            if st.button("Yes, DELETE PERMANENTLY"):
                 with st.spinner("Deleting tabs..."):
                    if googlesheets.delete_camp_tabs(delete_camp_select):
                        st.success(f"Deleted {delete_camp_select}")
                        st.session_state.confirm_delete_admin = False
                        st.rerun()
            if st.button("Cancel"):
                st.session_state.confirm_delete_admin = False
                st.rerun()

# --- TAB 4: Maintenance ---
with tab4:
    st.header("Maintenance")
    st.write("System utilities.")

    if st.button("Empty Service Account Trash"):
        with st.spinner("Emptying trash..."):
            if googlesheets.force_empty_trash():
                st.success("Trash emptied successfully.")
            else:
                st.error("Failed to empty trash.")
