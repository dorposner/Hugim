import streamlit as st
import time

def render_sidebar():
    """
    Renders the common sidebar elements:
    - User Info
    - Logout Button
    - Admin Visibility Logic (hiding Super Admin from non-admins)
    """

    # 1. Admin Visibility Logic
    user_role = st.session_state.get('user_role', 'user')

    if user_role != 'admin':
        # CSS to hide the specific link to Super Admin page.
        # Streamlit sidebar nav items are usually <li> elements.
        # We target the one containing "Super Admin".
        hide_admin_css = """
        <style>
            div[data-testid="stSidebarNav"] li:has(span:contains("Super Admin")) {
                display: none;
            }
            /* Fallback/Alternative selector if :has is not supported or structure differs */
            div[data-testid="stSidebarNav"] a[href*="Super_Admin"] {
                display: none;
            }
            /* Try to hide by text content if possible (tricky in pure CSS without :has, but :has is widely supported now) */
        </style>
        <script>
            // JS fallback to ensure it is hidden if CSS :has fails
            const observer = new MutationObserver((mutations) => {
                const items = document.querySelectorAll('div[data-testid="stSidebarNav"] li');
                items.forEach(item => {
                    if (item.innerText.includes("Super Admin")) {
                        item.style.display = 'none';
                    }
                });
            });
            observer.observe(document.body, { childList: true, subtree: true });
        </script>
        """
        # Note: script injection via markdown unsafe_allow_html works for style, but JS might need components.html or similar.
        # For now, we rely on CSS. :has is supported in Chrome/Edge/Safari/Firefox (recent versions).
        st.markdown(hide_admin_css, unsafe_allow_html=True)

    # 2. User Info & Logout
    # We check if authenticated. If not, maybe we don't show this?
    # But usually this is called on pages where we expect auth or Home where we check auth.
    if st.session_state.get("authenticated"):
        user_email = st.session_state.get("user_email", "Unknown")
        current_camp = st.session_state.get("current_camp_name", "None")

        st.sidebar.markdown("---") # Separator
        st.sidebar.markdown(f"**👤 Logged in as:** `{user_email}`")
        st.sidebar.markdown(f"**🏕️ Camp:** `{current_camp}`")

        if st.sidebar.button("Logout", key="universal_logout_btn"):
            st.session_state.clear()
            st.rerun()
