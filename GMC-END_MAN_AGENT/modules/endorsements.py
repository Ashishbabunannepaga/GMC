import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_policy_members_as_df, get_client_templates, save_endorsement_batch, get_unsynced_batches, sync_batch_to_master
from logic import parse_hr_endorsement_sheet, validate_endorsements
from utils import generate_action_excel

def render_endorsements(engine):
    st.title("Endorsement Processing Engine")
    st.markdown("---")

    client_id = st.session_state.get("selected_client_id")
    if not client_id:
        st.warning("⚠️ Please select an Active Client Workspace from the sidebar first.")
        return

    # Handle success messages gracefully
    if "batch_saved_msg" in st.session_state and st.session_state.batch_saved_msg:
        st.success(st.session_state.batch_saved_msg)
        st.balloons()
        st.session_state.batch_saved_msg = None
        
    if "batch_sync_msg" in st.session_state and st.session_state.batch_sync_msg:
        st.success(st.session_state.batch_sync_msg)
        st.session_state.batch_sync_msg = None

    from sqlalchemy import text
    with engine.connect() as conn:
        policy = conn.execute(text("SELECT id, policy_number FROM policies WHERE client_id = :cid"), {"cid": client_id}).fetchone()
        
    if not policy:
        st.error("No active policy found for this client.")
        return

    policy_id = policy.id
    st.info(f"Target Master Policy: **{policy.policy_number}**")

    saved_templates = get_client_templates(engine, client_id)

    st.subheader("1. Upload HR Endorsement Sheet")
    uploaded_file = st.file_uploader("Upload Excel/CSV File", type=["xlsx", "xls", "csv"])

    if uploaded_file:
        try:
            hr_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.success("File Loaded successfully.")

            if "val_add_df" not in st.session_state:
                st.session_state.val_add_df = None
                st.session_state.val_del_df = None

            if st.button("Tally & Validate Endorsements", type="primary"):
                with st.spinner("Validating against Master Database..."):
                    success, add_df, del_df = parse_hr_endorsement_sheet(hr_df)
                    if not success:
                        st.error("Failed to parse the HR sheet structure.")
                        return

                    master_df = get_policy_members_as_df(engine, policy_id)
                    val_add_df, val_del_df = validate_endorsements(master_df, add_df, del_df)
                    
                    st.session_state.val_add_df = val_add_df
                    st.session_state.val_del_df = val_del_df

            if st.session_state.val_add_df is not None:
                val_add_df = st.session_state.val_add_df
                val_del_df = st.session_state.val_del_df
                
                st.markdown("---")
                st.subheader("📊 Validation Results")
                
                tab1, tab2 = st.tabs([f"🟢 Additions ({len(val_add_df)})", f"🔴 Deletions ({len(val_del_df)})"])
                
                with tab1:
                    if not val_add_df.empty:
                        safe_add_df = val_add_df.copy().astype(str)
                        st.dataframe(safe_add_df)
                        if "Addition" in saved_templates:
                            excel_data = generate_action_excel(val_add_df, saved_templates["Addition"], action_flag="A")
                            st.download_button("⬇️ Download Output (Addition Format)", data=excel_data, file_name="Additions_Action.xlsx")
                with tab2:
                    if not val_del_df.empty:
                        safe_del_df = val_del_df.copy().astype(str)
                        st.dataframe(safe_del_df)
                        if "Deletion" in saved_templates:
                            excel_data = generate_action_excel(val_del_df, saved_templates["Deletion"], action_flag="D")
                            st.download_button("⬇️ Download Output (Deletion Format)", data=excel_data, file_name="Deletions_Action.xlsx")

                st.markdown("---")
                st.subheader("💾 Commit Batch to Database")
                col1, col2 = st.columns([3, 1])
                with col1:
                    current_time_str = datetime.now().strftime('%d %b %Y - %I:%M %p')
                    batch_name = st.text_input("Batch Name", value=f"Endorsement Batch - {current_time_str}")
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("Save Batch Record", type="primary", width='stretch'):
                        add_list = val_add_df.to_dict(orient="records") if not val_add_df.empty else []
                        del_list = val_del_df.to_dict(orient="records") if not val_del_df.empty else []
                        
                        success, msg = save_endorsement_batch(engine, policy_id, batch_name, add_list, del_list)
                        if success:
                            st.session_state.batch_saved_msg = msg
                            st.session_state.val_add_df = None
                            st.session_state.val_del_df = None
                            st.rerun()
                        else:
                            st.error(msg)
                            
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

    # ==========================================
    # SYNC TO MASTER DB SECTION
    # ==========================================
    st.markdown("---")
    st.subheader("🔄 Sync Batches to Master Active Sheet")
    st.caption("Apply saved batches to the Master Database. Deletions will be soft-deleted (status set to Cancelled).")

    unsynced_batches = get_unsynced_batches(engine, policy_id)
    
    if len(unsynced_batches) > 0:
        batch_options = {b["name"]: b["id"] for b in unsynced_batches}
        selected_batch_name = st.selectbox("Select Batch to Sync", list(batch_options.keys()))
        
        if st.button("Sync Selected Batch to Master", type="primary"):
            with st.spinner("Updating Master Roster..."):
                selected_id = batch_options[selected_batch_name]
                sync_success, sync_msg = sync_batch_to_master(engine, selected_id, policy_id)
                
                if sync_success:
                    st.session_state.batch_sync_msg = sync_msg
                    st.rerun()
                else:
                    st.error(sync_msg)
    else:
        st.info("All batches have been synced. The Master Roster is fully up to date.")