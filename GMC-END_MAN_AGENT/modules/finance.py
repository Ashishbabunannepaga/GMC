import streamlit as st
import pandas as pd
from database import get_all_batches, get_active_rate_card, get_batch_records, get_all_policy_members_for_finance, get_latest_cd_balance
from logic import process_financial_batch

def render_finance(engine):
    st.title("🏦 Financial Statement & Auditor")
    st.markdown("---")

    client_id = st.session_state.get("selected_client_id")
    from sqlalchemy import text
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT id FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()
    policy_id = policy.id

    # AUTO-FETCH CD BALANCE
    opening_balance, as_of_date = get_latest_cd_balance(engine, policy_id)

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Ledger Status")
        st.metric("Available CD Balance", f"₹ {opening_balance:,.2f}", delta=f"Last updated: {as_of_date}", delta_color="off")
        st.caption("Balance is auto-pulled from your Cash Deposit Ledger.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.subheader("Calculate Endorsement")
        batches = get_all_batches(engine, policy_id)
        if len(batches) == 0:
            st.info("No endorsement batches found. Process endorsements first.")
            return
            
        batch_options = {f"{b['name']}": b['id'] for b in batches}
        selected_batch = st.selectbox("Select Batch", list(batch_options.keys()))
        calc_trigger = st.button("Calculate Required Funds", type="primary", width='stretch')

    with col2:
        if calc_trigger:
            rate_card = get_active_rate_card(engine, policy_id)
            if not rate_card:
                st.error("No active Rate Card found.")
                return

            with st.spinner("Calculating..."):
                batch_id = batch_options[selected_batch]
                records = get_batch_records(engine, batch_id)
                master_df = get_all_policy_members_for_finance(engine, policy_id) 
                
                success, results_df, error_msg = process_financial_batch(records, rate_card, master_df)
                
                if success and not results_df.empty:
                    total_required = results_df[(results_df['Action'] == 'A') & (results_df['Status'] == 'Success')]['Total Premium'].sum()
                    total_released = results_df[(results_df['Action'] == 'D') & (results_df['Status'] == 'Success')]['Total Premium'].sum()
                    
                    net_cost = total_required - total_released
                    closing_balance = opening_balance - net_cost
                    
                    # 🔴 INSUFFICIENT FUNDS ALERT ENGINE 🔴
                    if closing_balance < 0:
                        st.error(f"🚨 **INSUFFICIENT FUNDS:** You are short by ₹ {abs(closing_balance):,.2f}.")
                        st.warning("The Insurer will reject this endorsement until the CD account is topped up.")
                        
                        email_body = f"Subject: URGENT: Insufficient CD Balance for Endorsements\n\nDear Client,\n\nPlease deposit ₹ {abs(closing_balance):,.2f} into your Virtual CD Account to process the {selected_batch} endorsements immediately.\n\nCurrent Balance: ₹ {opening_balance:,.2f}\nRequired Premium: ₹ {net_cost:,.2f}"
                        st.download_button("📩 Generate Fund Request Email Template", data=email_body, file_name="Fund_Request.txt", type="primary")
                        st.markdown("---")

                    st.subheader("Financial Summary")
                    m1, m2, m3 = st.columns(3)
                    m1.error(f"📉 Gross Cost\n₹ {total_required:,.2f}")
                    m2.success(f"📈 Gross Refund\n₹ {total_released:,.2f}")
                    if closing_balance < 0:
                        m3.error(f"🏦 Projected Balance\n₹ {closing_balance:,.2f}")
                    else:
                        m3.info(f"🏦 Projected Balance\n₹ {closing_balance:,.2f}")
                    
                    st.write("**Line-by-Line Breakdown**")
                    styled_df = results_df.style.map(lambda val: 'color: #ff4b4b' if val == 'Error' else 'color: #21c354', subset=['Status'])
                    st.dataframe(styled_df, width='stretch')

                else:
                    st.error("🚨 Critical System Failure.")
                    st.code(error_msg)