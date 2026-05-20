import streamlit as st
import pandas as pd
from database import save_cd_statement, get_latest_cd_balance
from logic import process_cd_dataframe

def render_cd_management(engine):
    st.title("💸 Cash Deposit (CD) Ledger")
    st.markdown("---")

    client_id = st.session_state.get("selected_client_id")
    if not client_id:
        st.warning("⚠️ Please select an Active Client Workspace from the sidebar first.")
        return

    from sqlalchemy import text
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT id, policy_number FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()

    current_balance, as_of_date = get_latest_cd_balance(engine, policy.id)

    # Top Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current CD Balance", f"₹ {current_balance:,.2f}", delta=f"As of: {as_of_date}", delta_color="off")
    with col2:
        st.info("Upload the latest CD Statement from the Insurer to automatically update your available balance for Premium Calculations.")

    st.markdown("---")
    st.subheader("Upload New CD Statement")
    
    with st.form("cd_upload_form"):
        statement_name = st.text_input("Statement Name (e.g., Q3 CD Ledger)", value="CD Statement Update")
        uploaded_file = st.file_uploader("Upload Insurer CSV/Excel", type=["csv", "xlsx", "xls"])
        
        if st.form_submit_button("Upload to Ledger", type="primary"):
            if uploaded_file and statement_name:
                try:
                    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    success, clean_records = process_cd_dataframe(df)
                    
                    if success and clean_records:
                        save_success, msg = save_cd_statement(engine, policy.id, statement_name, clean_records)
                        if save_success:
                            st.success(f"{msg} Reloading balance...")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Failed to parse CD data. Ensure 'closingbalance' column exists.")
                except Exception as e:
                    st.error(f"File error: {str(e)}")
            else:
                st.warning("Please provide a name and upload a file.")