import streamlit as st
from database import get_db_engine, init_db, delete_client_workspace, get_all_clients
from auth import init_session_state, render_login
from modules.onboarding import render_onboarding
from modules.endorsements import render_endorsements
from modules.writings import render_writings
from modules.finance import render_finance
from modules.directory import render_directory
from modules.dashboard import render_dashboard
from modules.roster import render_roster
from modules.cd_management import render_cd_management
from modules.user_management import render_user_management

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="GMC Endorsement Calculation Portal", layout="wide", initial_sidebar_state="expanded")

engine = get_db_engine()
init_db(engine)
init_session_state()

if "current_page" not in st.session_state: st.session_state.current_page = "Client Directory"
if "theme" not in st.session_state: st.session_state.theme = "Dark"

# ==========================================
# 100% NATIVE CSS 
# ==========================================
def inject_native_css():
    is_dark = st.session_state.theme == "Dark"
    bg_color = "#0B0F19" if is_dark else "#F8FAFC"
    sidebar_bg = "#111827" if is_dark else "#FFFFFF"
    accent = "#6366F1" if is_dark else "#3B82F6"
    text_primary = "#F9FAFB" if is_dark else "#0F172A"
    text_secondary = "#9CA3AF" if is_dark else "#64748B"
    border_color = "rgba(255,255,255,0.05)" if is_dark else "rgba(0,0,0,0.05)"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
        .stApp {{ background-color: {bg_color}; }}
        [data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_color}; }}
        
        /* 🔴 NATIVE MENU HACK */
        [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{ display: none !important; }} 
        [data-testid="stSidebar"] div[role="radiogroup"] > label {{
            padding: 10px 14px;
            margin-bottom: 4px;
            border-radius: 10px;
            transition: all 0.2s ease;
            cursor: pointer;
            border: 1px solid transparent;
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{ background-color: {border_color}; }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] {{
            background-color: {accent}1A !important;
            border-left: 4px solid {accent} !important;
            border-radius: 4px 10px 10px 4px;
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] p {{
            color: {accent} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stSidebar"] div[role="radiogroup"] > label p {{
            font-size: 15px; font-weight: 600; color: {text_secondary}; margin: 0;
        }}

        /* Standard Button Styling */
        [data-testid="stSidebar"] .stButton > button {{
            background-color: transparent; border: 1px solid {border_color}; color: {text_secondary};
            border-radius: 10px; height: 44px; font-weight: 600; transition: all 0.2s ease;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background-color: {accent}1A; color: {accent}; border-color: {accent}; transform: translateY(-2px);
        }}
        </style>
    """, unsafe_allow_html=True)
    return accent, text_primary, text_secondary

accent, text_primary, text_secondary = inject_native_css()

# ==========================================
# DYNAMIC SIDEBAR
# ==========================================
def render_sidebar():
    with st.sidebar:
        # Modern App Header
        st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; margin-bottom: 25px;">
                <div style="background: linear-gradient(135deg, {accent}, #818CF8); padding:10px; border-radius:12px; box-shadow: 0 4px 14px {accent}50; flex-shrink: 0;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                </div>
                <h2 style="margin:0; font-weight:800; font-size: 14px; line-height: 1.2; color:{text_primary};">
                    GMC Endorsement<br><span style="color:{accent};">Calculation Portal</span>
                </h2>
            </div>
        """, unsafe_allow_html=True)

        is_admin = st.session_state.get("role") == "admin"

        # --- VIEW 1: INSIDE A WORKSPACE ---
        if st.session_state.get("selected_client_id"):
            st.markdown(f"<div style='margin-bottom: 5px; font-size:11px; color:{text_secondary}; text-transform:uppercase; font-weight:800; letter-spacing:1px;'>Active Workspace</div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"<div style='font-weight:700; font-size:15px; color:{text_primary}; margin-bottom: 10px;'>🏢 {st.session_state.selected_client_name}</div>", unsafe_allow_html=True)
            
            # ✨ ONLY ADMINS CAN SWITCH WORKSPACES ✨
            if is_admin:
                with col2:
                    if st.button("✕", help="Switch Workspace"):
                        st.session_state.selected_client_id = None
                        st.session_state.selected_client_name = None
                        st.session_state.current_page = "Client Directory"
                        st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            
            pages = ["📊 Dashboard", "🔄 Active Policies", "📝 Endorsements", "🏷️ Rate Cards", "💸 Cash Deposit", "🏦 Finance"]
            page_mapping = {
                "📊 Dashboard": "Workspace Dashboard", "🔄 Active Policies": "Roster Management",
                "📝 Endorsements": "Process Endorsements", "🏷️ Rate Cards": "Writings Management",
                "💸 Cash Deposit": "CD Management", "🏦 Finance": "Financial Statement"
            }
            reverse_mapping = {v: k for k, v in page_mapping.items()}
            current_ui_name = reverse_mapping.get(st.session_state.current_page, "📊 Dashboard")
            
            selected = st.radio("Menu", pages, index=pages.index(current_ui_name), label_visibility="collapsed")
            
            if st.session_state.current_page != page_mapping[selected]:
                st.session_state.current_page = page_mapping[selected]; st.rerun()
            
            # ✨ ONLY ADMINS CAN DELETE WORKSPACES ✨
            if is_admin:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚙️ Settings"):
                    if st.button("🗑️ Delete Workspace", use_container_width=True):
                        success, msg = delete_client_workspace(engine, st.session_state.selected_client_id)
                        if success:
                            st.session_state.selected_client_id = None
                            st.session_state.current_page = "Client Directory"; st.rerun()

        # --- VIEW 2: GLOBAL ADMIN VIEW ---
        # 🔴 THE FIX: THIS ELIF IS NOW PROPERLY INDENTED OUTSIDE THE WORKSPACE IF BLOCK!
        elif is_admin:
            st.markdown(f"<div style='margin-bottom: 15px; font-size:11px; color:{text_secondary}; text-transform:uppercase; font-weight:800; letter-spacing:1px;'>Admin Hub</div>", unsafe_allow_html=True)
            
            pages = ["🌐 Client Directory", "➕ Create Workspace", "🔐 User Management"]
            page_mapper = {
                "🌐 Client Directory": "Client Directory", 
                "➕ Create Workspace": "Create Client",
                "🔐 User Management": "User Management"
            }
            reverse_mapping = {v: k for k, v in page_mapper.items()}
            current_ui_name = reverse_mapping.get(st.session_state.current_page, "🌐 Client Directory")
            
            selected = st.radio("Global Menu", pages, index=pages.index(current_ui_name), label_visibility="collapsed")
            
            if st.session_state.current_page != page_mapper[selected]:
                st.session_state.current_page = page_mapper[selected]
                st.rerun()

        # ==========================================
        # BOTTOM CONTROLS
        # ==========================================
        st.markdown("<div style='margin-top: 100px;'></div>", unsafe_allow_html=True) 
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            theme_icon = "🌞 Light" if st.session_state.theme == "Dark" else "🌙 Dark"
            if st.button(theme_icon, use_container_width=True):
                st.session_state.theme = "Light" if st.session_state.theme == "Dark" else "Dark"; st.rerun()
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False; st.rerun()

# ==========================================
# ROUTER
# ==========================================
def main():
    if not st.session_state.authenticated: render_login(engine); return
    render_sidebar()
    page = st.session_state.current_page
    if page == "Client Directory": render_directory(engine)
    elif page == "Create Client": render_onboarding(engine)
    elif page == "User Management": render_user_management(engine)
    elif page == "Workspace Dashboard": render_dashboard(engine)
    elif page == "Roster Management": render_roster(engine)
    elif page == "Process Endorsements": render_endorsements(engine)
    elif page == "Writings Management": render_writings(engine)
    elif page == "CD Management": render_cd_management(engine)
    elif page == "Financial Statement": render_finance(engine)

if __name__ == "__main__": main()