import streamlit as st
import pandas as pd
from database import get_all_clients, create_app_user, get_all_users, delete_app_user

def render_user_management(engine):
    st.title("🔐 User & Access Control")
    st.markdown("---")

    # Only Admins should be here!
    if st.session_state.get("role") != "admin":
        st.error("Access Denied: Only Global Admins can manage users.")
        return

    col1, col2 = st.columns([1, 2])

    # ==========================================
    # CREATE NEW USER FORM
    # ==========================================
    with col1:
        st.subheader("Create New Credential")
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Username *", placeholder="e.g., technogen_hr")
            new_password = st.text_input("Temporary Password *", type="password", help="Client can change this later.")
            
            role = st.selectbox("System Role", ["client", "admin"])
            
            # If role is client, we MUST assign them to a workspace
            client_id = None
            if role == "client":
                clients = get_all_clients(engine)
                if not clients:
                    st.warning("No workspaces exist yet. Create a workspace first.")
                    st.form_submit_button("Create User", disabled=True)
                else:
                    client_options = {c['name']: c['id'] for c in clients}
                    selected_workspace = st.selectbox("Assign to Workspace *", list(client_options.keys()))
                    client_id = client_options[selected_workspace]
            
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Create User", type="primary", use_container_width=True)
            
            if submitted:
                if not new_username or not new_password:
                    st.error("Username and Password are required.")
                else:
                    with st.spinner("Provisioning credentials..."):
                        success, msg = create_app_user(engine, new_username, new_password, role, client_id)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # ==========================================
    # MANAGE EXISTING USERS
    # ==========================================
    with col2:
        st.subheader("Active System Users")
        users = get_all_users(engine)
        
        if not users:
            st.info("No users found.")
            return

        df = pd.DataFrame(users)
        df['client_name'] = df['client_name'].fillna("GLOBAL ADMIN")
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d %b %Y')
        
        # Display the users table cleanly
        st.dataframe(
            df[['username', 'role', 'client_name', 'created_at']], 
            use_container_width=True, 
            hide_index=True
        )

        st.markdown("---")
        st.subheader("Revoke Access")
        st.caption("Select a user to permanently delete their credentials. (They will be immediately logged out).")
        
        # Safe deletion UI
        user_options = {f"{u['username']} ({u['role'].upper()})": u['id'] for u in users}
        del_user_name = st.selectbox("Select User to Delete", list(user_options.keys()))
        
        if st.button("Revoke Credentials", type="primary"):
            del_user_id = user_options[del_user_name]
            success, msg = delete_app_user(engine, del_user_id)
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)