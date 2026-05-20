import streamlit as st
import pandas as pd
from database import insert_new_client_transaction, bulk_insert_policy_members
from logic import process_policy_dataframe

def render_onboarding(engine):
    st.title("Create New Client Workspace")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["1. Corporate & Policy Details", "2. Master Roster Upload", "3. Action Templates"])
    
    # ==========================
    # TAB 1: DETAILS
    # ==========================
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            client_name = st.text_input("Client Name *", placeholder="e.g., Acme Corp")
            client_code = st.text_input("Client Code", placeholder="e.g., ACME001")
            corporate_group = st.text_input("Corporate Group")
        with col2:
            policy_type = st.selectbox("Policy Type *", ["GMC", "GPA", "GTL"])
            policy_number = st.text_input("Policy Number *")
            insurer_name = st.text_input("Insurer Name")
            start_date = st.date_input("Policy Start Date")
            end_date = st.date_input("Policy End Date")

    # ==========================
    # TAB 2: ROSTER
    # ==========================
    with tab2:
        st.subheader("Universal Master Roster")
        st.info("⚠️ You MUST upload the active policy members here before creating the client.")
        
        uploaded_roster = st.file_uploader("Upload Active Policy", type=["xlsx", "xls", "csv"], key="roster_up")
        
        roster_df = None
        if uploaded_roster:
            try:
                if uploaded_roster.name.endswith('.csv'):
                    roster_df = pd.read_csv(uploaded_roster)
                else:
                    roster_df = pd.read_excel(uploaded_roster)
                st.success(f"Master Roster Loaded: {len(roster_df)} records found.")
            except Exception as e:
                st.error(f"Error reading file. If using .xls, ensure 'xlrd' is installed. Error: {str(e)}")

    # ==========================
    # TAB 3: TEMPLATES & SUBMIT
    # ==========================
    with tab3:
        st.subheader("TPA Output Format Templates")
        st.caption("Upload sample .xlsx, .xls, or .csv files from the TPA to map future endorsement outputs.")
        
        tpl_col1, tpl_col2, tpl_col3 = st.columns(3)
        templates_to_save = []
        
        with tpl_col1:
            add_file = st.file_uploader("Addition Template (A)", type=["xlsx", "xls", "csv"], key="add_tpl")
            if add_file:
                cols = pd.read_excel(add_file).columns.tolist() if not add_file.name.endswith('.csv') else pd.read_csv(add_file).columns.tolist()
                templates_to_save.append({"name": "Addition_Template", "action": "Addition", "columns": cols})
                st.success("Addition Template Mapped")
                
        with tpl_col2:
            del_file = st.file_uploader("Deletion Template (D)", type=["xlsx", "xls", "csv"], key="del_tpl")
            if del_file:
                cols = pd.read_excel(del_file).columns.tolist() if not del_file.name.endswith('.csv') else pd.read_csv(del_file).columns.tolist()
                templates_to_save.append({"name": "Deletion_Template", "action": "Deletion", "columns": cols})
                st.success("Deletion Template Mapped")
                
        with tpl_col3:
            mod_file = st.file_uploader("Correction Template (M)", type=["xlsx", "xls", "csv"], key="mod_tpl")
            if mod_file:
                cols = pd.read_excel(mod_file).columns.tolist() if not mod_file.name.endswith('.csv') else pd.read_csv(mod_file).columns.tolist()
                templates_to_save.append({"name": "Correction_Template", "action": "Correction", "columns": cols})
                st.success("Correction Template Mapped")

        st.markdown("---")
        st.info("✅ Final Step: Ensure Details and Roster are filled out in the previous tabs before clicking Create.")
        
        # 🔴 FIX: Changed width='stretch' to use_container_width=True
        if st.button("Create Client Workspace", type="primary", use_container_width=True):
            
            if not client_name or not policy_number:
                st.error("Please go back to Tab 1 and fill in Client Name and Policy Number.")
                return
                
            if roster_df is None:
                st.error("Please go to Tab 2 and upload the Master Roster file before continuing.")
                return

            with st.spinner("Provisioning Workspace & Ingesting Data..."):
                client_data = {"client_name": client_name, "client_code": client_code, "corporate_group": corporate_group}
                policy_data = {"policy_number": policy_number, "policy_type": policy_type, "insurer_name": insurer_name, "start_date": str(start_date), "end_date": str(end_date)}

                success, msg, client_id, policy_id = insert_new_client_transaction(engine, client_data, policy_data, templates_to_save)
                
                if success:
                    data_success, cleaned_data_list = process_policy_dataframe(roster_df)
                    if data_success:
                        insert_success, insert_msg = bulk_insert_policy_members(engine, policy_id, cleaned_data_list)
                        if insert_success:
                            st.success(f"Workspace fully configured. {insert_msg}")
                            st.balloons()
                        else:
                            st.error(f"Roster insertion failed: {insert_msg}")
                    else:
                        st.error("Failed to parse roster data.")
                else:
                    st.error(msg)
