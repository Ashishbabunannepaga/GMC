import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_activity_logs

def render_dashboard(engine):
    client_name = st.session_state.get("selected_client_name", "Unknown Client")
    client_id = st.session_state.get("selected_client_id")
    
    st.title(f"📊 Workspace Dashboard")
    st.markdown("---")
    
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT * FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()
        if not policy:
            st.warning("No policy details found.")
            return
            
        active_count = conn.execute(text("""
            SELECT COUNT(*) FROM active_policy_members 
            WHERE policy_id = :pid 
            AND (raw_data->>'STATUS OF INDIVIDUAL UHID' IS NULL OR raw_data->>'STATUS OF INDIVIDUAL UHID' != 'Cancelled')
        """), {"pid": policy.id}).scalar()
        
    col1, col2, col3 = st.columns(3)
    col1.metric("Policy Number", policy.policy_number)
    col2.metric("Insurer", policy.insurer_name if policy.insurer_name else "Not Set")
    col3.metric("Active Insured Members", f"{active_count:,}")
    
    st.markdown("---")
    
    # ✨ NEW: AUDIT TRAIL DISPLAY ✨
    st.subheader("📝 Recent Workspace Activity")
    st.caption("A chronological audit trail of actions performed in this workspace.")
    
    logs = get_activity_logs(engine, client_id)
    if logs:
        df_logs = pd.DataFrame(logs)
        df_logs.rename(columns={
            "created_at": "Timestamp", 
            "username": "User", 
            "action_type": "Action", 
            "details": "Details"
        }, inplace=True)
        # Format timestamp nicely
        df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp']).dt.strftime('%Y-%m-%d %I:%M %p')
        
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No activity logged yet.")