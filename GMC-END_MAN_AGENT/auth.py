import streamlit as st
from sqlalchemy import text
import hashlib

def init_session_state():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    if "username" not in st.session_state: st.session_state.username = ""
    if "role" not in st.session_state: st.session_state.role = "user"
    if "logged_in_client_id" not in st.session_state: st.session_state.logged_in_client_id = None
    if "selected_client_id" not in st.session_state: st.session_state.selected_client_id = None
    if "selected_client_name" not in st.session_state: st.session_state.selected_client_name = None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_login(engine, username, password):
    try:
        clean_username = str(username).strip()
        clean_password = str(password).strip()
        
        with engine.connect() as conn:
            # ✨ NOW FETCHING ROLE AND CLIENT_ID
            user = conn.execute(text("""
                SELECT u.id, u.username, u.password_hash, u.role, u.client_id, c.client_name 
                FROM app_users u
                LEFT JOIN clients c ON u.client_id = c.id
                WHERE u.username = :user
            """), {"user": clean_username}).fetchone()
            
            if user:
                if user.password_hash == clean_password or user.password_hash == hash_password(clean_password):
                    st.session_state.authenticated = True
                    st.session_state.username = user.username
                    st.session_state.role = user.role
                    st.session_state.logged_in_client_id = user.client_id
                    
                    # If they are a client, lock them into their workspace automatically!
                    if user.role == 'client' and user.client_id:
                        st.session_state.selected_client_id = user.client_id
                        st.session_state.selected_client_name = user.client_name
                        st.session_state.current_page = "Workspace Dashboard"
                    else:
                        st.session_state.current_page = "Client Directory"
                        
                    return True
        return False
    except Exception as e:
        st.error(f"Login Error: {str(e)}")
        return False

def render_login(engine):
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #6366F1; font-weight: 800;'>🛡️ GMC Enterprise Portal</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Please sign in to continue</p>", unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Secure Login", use_container_width=True)
            
            if submitted:
                if verify_login(engine, username, password): st.rerun()
                else: st.error("Invalid Credentials. Please try again.")