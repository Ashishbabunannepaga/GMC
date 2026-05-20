import streamlit as st
import pandas as pd
from sqlalchemy import text

# ==========================================
# DATABASE SYNC PAGE
# ==========================================

def render_database_sync(engine):

    st.title("Database Sync")

    selected_client = st.session_state.get(
        "selected_client"
    )

    # ==========================================
    # CLIENT CHECK
    # ==========================================

    if not selected_client:

        st.warning(
            "Please Select Client From Sidebar"
        )

        return

    st.success(
        f"Active Client: {selected_client}"
    )

    st.markdown("---")

    # ==========================================
    # UPLOAD
    # ==========================================

    uploaded_file = st.file_uploader(

        "Upload Active Policy Sheet",

        type=["xlsx", "xls", "csv"],

        key="database_sync_upload"
    )

    if uploaded_file:

        try:

            # ==========================================
            # READ FILE
            # ==========================================

            if uploaded_file.name.endswith(".csv"):

                df = pd.read_csv(
                    uploaded_file
                )

            else:

                df = pd.read_excel(
                    uploaded_file
                )

            # ==========================================
            # BASIC INFO
            # ==========================================

            st.success(
                "File Loaded Successfully"
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "Rows",
                    len(df)
                )

            with col2:

                st.metric(
                    "Columns",
                    len(df.columns)
                )

            with col3:

                st.metric(
                    "Duplicates",
                    df.duplicated().sum()
                )

            st.markdown("---")

            # ==========================================
            # DETECTED COLUMNS
            # ==========================================

            st.subheader("Detected Columns")

            st.write(
                list(df.columns)
            )

            st.markdown("---")

            # ==========================================
            # VALIDATION ENGINE
            # ==========================================

            st.subheader("Validation Results")

            mandatory_columns = [

                "UHID",
                "INSURED NAME",
                "SUM INSURED"
            ]

            missing_columns = []

            for col in mandatory_columns:

                if col not in df.columns:

                    missing_columns.append(col)

            if len(missing_columns) > 0:

                st.error(
                    f"Missing Columns: {missing_columns}"
                )

            else:

                st.success(
                    "Mandatory Columns Validated"
                )

            # ==========================================
            # NULL CHECKS
            # ==========================================

            null_summary = df.isnull().sum()

            null_summary = (
                null_summary[
                    null_summary > 0
                ]
            )

            if len(null_summary) > 0:

                st.warning(
                    "Columns With Missing Values"
                )

                st.dataframe(
                    null_summary
                )

            else:

                st.success(
                    "No Missing Values"
                )

            # ==========================================
            # DUPLICATE CHECK
            # ==========================================

            duplicate_rows = df[
                df.duplicated()
            ]

            if len(duplicate_rows) > 0:

                st.warning(
                    f"{len(duplicate_rows)} Duplicate Rows Found"
                )

            else:

                st.success(
                    "No Duplicate Rows"
                )

            st.markdown("---")

            # ==========================================
            # DATA PREVIEW
            # ==========================================

            st.subheader("Preview")

            st.dataframe(
                df.head(10).astype(str),
                width='stretch'
            )

            st.markdown("---")

            # ==========================================
            # SAVE TO DATABASE
            # ==========================================

            if st.button(

                "Push Active Policies To Database",

                width='stretch',

                key="push_policy_db_btn"
            ):

                with engine.begin() as conn:

                    # ==========================================
                    # CREATE TABLE
                    # ==========================================

                    conn.execute(text("""

                        CREATE TABLE IF NOT EXISTS active_policy_members (

                            id SERIAL PRIMARY KEY,

                            client_name TEXT,

                            raw_data JSONB

                        )

                    """))

                    # ==========================================
                    # INSERT ROWS
                    # ==========================================

                    inserted = 0

                    for _, row in df.iterrows():

                        row_dict = (
                            row.fillna("")
                            .to_dict()
                        )

                        conn.execute(text("""

                            INSERT INTO active_policy_members (

                                client_name,
                                raw_data

                            )

                            VALUES (

                                :client_name,
                                :raw_data
                            )

                        """), {

                            "client_name": selected_client,

                            "raw_data": (
                                str(row_dict)
                            )
                        })

                        inserted += 1

                st.success(
                    f"{inserted} rows inserted successfully"
                )

                st.balloons()

        except Exception as e:

            st.error(str(e))