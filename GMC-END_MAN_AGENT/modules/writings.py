import streamlit as st
import pandas as pd
from database import save_rate_card, get_all_rate_cards

def render_writings(engine):
    st.title("✍️ Writings Management (Rate Cards)")
    st.markdown("---")

    client_id = st.session_state.get("selected_client_id")
    if not client_id:
        st.warning("⚠️ Please select an Active Client Workspace from the sidebar first.")
        return

    from sqlalchemy import text
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT id, policy_number FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()
        
    if not policy:
        st.error("No active policy found.")
        return

    # 1. Upload Form
    with st.form("new_writing_form"):
        st.subheader("Upload New Rate Card")
        st.caption("Excel file should have Age Min, Age Max, and Sum Insured Columns (e.g., 500000).")
        writing_file = st.file_uploader("Upload Rate Card File (.xlsx, .xls, .csv)", type=["xlsx", "xls", "csv"])
        
        col1, col2, col3 = st.columns(3)
        writing_name = col1.text_input("Writing Name", placeholder="e.g., Year 2026 Rates")
        gst_rate_input = col2.number_input("GST Rate (%)", min_value=0.0, value=18.0, step=0.1)
        
        date_col1, date_col2 = st.columns(2)
        policy_start = date_col1.date_input("Policy Start Date")
        policy_end = date_col2.date_input("Policy End Date")
        
        if st.form_submit_button("Save & Activate New Writing", type="primary"):
            if writing_file and writing_name:
                try:
                    df = pd.read_excel(writing_file) if not writing_file.name.endswith('.csv') else pd.read_csv(writing_file)
                    # Clean out fully empty rows/cols
                    df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
                    df.columns = df.columns.astype(str)
                    rates_json = df.to_json(orient='split')
                    
                    success, msg = save_rate_card(engine, policy.id, writing_name, gst_rate_input, policy_start, policy_end, rates_json)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"Failed to read rate card: {str(e)}")
            else:
                st.error("Please provide a name and upload a file.")

    st.markdown("---")
    
    # 2. Existing Rate Cards
    st.subheader("Existing Rate Cards")
    cards = get_all_rate_cards(engine, policy.id)
    
    if len(cards) == 0:
        st.info("No rate cards uploaded yet.")
    else:
        for c in cards:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"📄 **{c['writing_name']}** (GST: {c['gst_rate']}%)")
            c2.write(f"{c['start_date']} to {c['end_date']}")
            if c['is_active']:
                c3.success("Active")
            else:
                c3.warning("Archived")