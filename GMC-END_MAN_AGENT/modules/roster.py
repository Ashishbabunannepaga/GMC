import streamlit as st
import pandas as pd
from database import get_policy_members_as_df
from logic import reconcile_full_rosters, validate_endorsements

def render_roster(engine):
    st.title("👥 Master Roster & Reconciliation")
    st.markdown("---")

    client_id = st.session_state.get("selected_client_id")
    if not client_id:
        st.warning("⚠️ Please select an Active Client Workspace first.")
        return

    from sqlalchemy import text
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT id, policy_number FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()

    st.info(f"Target Master Policy: **{policy.policy_number}**")
    
    tab1, tab2 = st.tabs(["📋 View Live Database", "🔄 Auto-Reconcile Full Roster"])

    with tab1:
        st.subheader("Current Active Members")
        st.caption("This data pulls directly from the PostgreSQL database in real-time.")
        master_df = get_policy_members_as_df(engine, policy.id)
        
        if master_df.empty:
            st.warning("The Master Roster is empty.")
        else:
            st.dataframe(master_df.astype(str), height=400)
            csv = master_df.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Export Live Roster (CSV)", data=csv, file_name=f"Active_Roster_{policy.policy_number}.csv", mime="text/csv")

    with tab2:
        st.subheader("Upload Full HR Roster for Reconciliation")
        st.caption("Upload the complete active employee list. The system will automatically compare it against the live database and find Additions & Deletions.")
        
        uploaded_file = st.file_uploader("Upload New Complete HR Master Roster", type=["xlsx", "xls", "csv"])

        if uploaded_file:
            try:
                new_roster_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                st.success(f"Loaded new roster with {len(new_roster_df)} rows.")

                if st.button("Run Deep Reconciliation", type="primary"):
                    with st.spinner("Comparing against Database..."):
                        master_df = get_policy_members_as_df(engine, policy.id)
                        success, add_df, del_df = reconcile_full_rosters(master_df, new_roster_df)
                        
                        if success:
                            # Pass to validator to generate the green flags
                            val_add_df, val_del_df = validate_endorsements(master_df, add_df, del_df)
                            st.session_state.val_add_df = val_add_df
                            st.session_state.val_del_df = val_del_df
                            
                            st.success("✅ Reconciliation Complete! Go to 'Endorsements' to save the batch.")
                            st.rerun() # Navigate seamlessly
                        else:
                            st.error("Reconciliation failed. Ensure the new sheet has standard columns.")
            except Exception as e:
                st.error(f"Error: {str(e)}")