import streamlit as st
from database import get_all_clients

def render_directory(engine):
    st.markdown("""
        <style>
        section[data-testid="stMain"] .stButton > button {
            height: 90px;
            width: 100%;
            border-radius: 12px;
            border: 1px solid rgba(150, 150, 150, 0.15) !important;
            background: linear-gradient(145deg, rgba(255,255,255,0.03) 0%, rgba(0,0,0,0.05) 100%) !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            padding: 10px !important;
        }
        section[data-testid="stMain"] .stButton > button:hover {
            border-color: #6366F1 !important;
            background: rgba(99, 102, 241, 0.05) !important;
            transform: translateY(-4px); 
            box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.25);
        }
        section[data-testid="stMain"] .stButton > button p {
            font-size: 0.9rem !important; 
            font-weight: 700 !important;
            white-space: normal !important; 
            line-height: 1.2;
            margin: 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Updated Official Title
    st.title("🛡️ GMC Endorsement Calculation Portal")
    st.markdown("---")
    
    clients = get_all_clients(engine)
    if not clients:
        st.info("No clients found. Go to 'Create Workspace' in the sidebar.")
        return

    # Super-fast Search Bar
    col1, col2 = st.columns([1, 2])
    with col1:
        search_query = st.text_input("🔍 Search Workspaces...", placeholder="Type a client name...")

    filtered_clients = [c for c in clients if search_query.lower() in c['name'].lower()]

    if not filtered_clients:
        st.warning("No clients match your search.")
        return

    st.write("")
    
    # Render the dynamic 4-column Grid
    cols = st.columns(5)
    for idx, client in enumerate(filtered_clients):
        with cols[idx % 4]:
            if st.button(f"\n{client['name']}", key=f"enter_{client['id']}", width='stretch'):
                st.session_state.selected_client_id = client['id']
                st.session_state.selected_client_name = client['name']
                st.session_state.current_page = "Workspace Dashboard"
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)