import json
import pandas as pd
import streamlit as st
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

@st.cache_resource
def get_db_engine():
    try:
        url_object = URL.create(
            drivername="postgresql+psycopg2",
            username=st.secrets["database"]["db_user"],
            password=st.secrets["database"]["db_pass"],
            host=st.secrets["database"]["db_host"],
            port=st.secrets["database"]["db_port"],
            database=st.secrets["database"]["db_name"]
        )
        
        # ✨ UPDATED FOR SUPABASE: Added connect_args={'sslmode': 'require'}
        return create_engine(
            url_object, 
            pool_pre_ping=True, 
            connect_args={'sslmode': 'require'}
        )
    except Exception as e:
        st.error(f"Database Connection Error: {str(e)}")
        raise e
    

def init_db(engine):
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS app_users (id SERIAL PRIMARY KEY, username VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(50) DEFAULT 'user', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, client_name VARCHAR(255) UNIQUE NOT NULL, client_code VARCHAR(100), corporate_group VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS policies (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, policy_number VARCHAR(255) NOT NULL, policy_type VARCHAR(50) NOT NULL, insurer_name VARCHAR(255), tpa_name VARCHAR(255), start_date DATE, end_date DATE, status VARCHAR(50) DEFAULT 'Active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS active_policy_members (id SERIAL PRIMARY KEY, policy_id INTEGER REFERENCES policies(id) ON DELETE CASCADE, employee_id VARCHAR(100), employee_name VARCHAR(255), uhid VARCHAR(100), relation VARCHAR(50), raw_data JSONB NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS client_templates (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, template_name VARCHAR(255) NOT NULL, action_type VARCHAR(100), columns_mapping JSONB NOT NULL, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS rate_cards (id SERIAL PRIMARY KEY, policy_id INTEGER REFERENCES policies(id) ON DELETE CASCADE, writing_name VARCHAR(255), gst_rate NUMERIC(5,2), start_date DATE, end_date DATE, is_active BOOLEAN DEFAULT TRUE, rates_json JSONB, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS endorsement_batches (id SERIAL PRIMARY KEY, policy_id INTEGER REFERENCES policies(id) ON DELETE CASCADE, batch_name VARCHAR(255) NOT NULL, is_synced BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS endorsement_records (id SERIAL PRIMARY KEY, batch_id INTEGER REFERENCES endorsement_batches(id) ON DELETE CASCADE, record_type VARCHAR(50) NOT NULL, raw_data JSONB NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
            
            # ✨ NEW: CASH DEPOSIT (CD) TABLES
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cd_statements (
                    id SERIAL PRIMARY KEY,
                    policy_id INTEGER REFERENCES policies(id) ON DELETE CASCADE,
                    statement_name VARCHAR(255) NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cd_transactions (
                    id SERIAL PRIMARY KEY,
                    statement_id INTEGER REFERENCES cd_statements(id) ON DELETE CASCADE,
                    transaction_date DATE,
                    transaction_type VARCHAR(255),
                    debit NUMERIC(12,2),
                    credit NUMERIC(12,2),
                    closing_balance NUMERIC(12,2),
                    raw_data JSONB NOT NULL
                )
            """))

            # --- ✨ NEW: CLIENT USER LINKING & AUDIT LOGS ✨ ---
            conn.execute(text("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE;"))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                    username VARCHAR(255),
                    action_type VARCHAR(255),
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("INSERT INTO app_users (username, password_hash, role) SELECT 'admin', 'admin123', 'admin' WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE username = 'admin')"))
    except SQLAlchemyError as e:
        st.error(f"Database Initialization Failed: {str(e)}")

# ==========================================
# CORE CLIENT & POLICY MANAGEMENT
# ==========================================
def get_all_clients(engine):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, client_name FROM clients ORDER BY client_name")).fetchall()
        return [{"id": row.id, "name": row.client_name} for row in result]

def insert_new_client_transaction(engine, client_data, policy_data, templates_list=[]):
    try:
        with engine.begin() as conn:
            existing = conn.execute(text("SELECT id FROM clients WHERE client_name = :name"), {"name": client_data["client_name"]}).fetchone()
            if existing: return False, "Client Name already exists.", None, None
            client_res = conn.execute(text("INSERT INTO clients (client_name, client_code, corporate_group) VALUES (:name, :code, :group) RETURNING id"), {"name": client_data["client_name"], "code": client_data.get("client_code", ""), "group": client_data.get("corporate_group", "")})
            client_id = client_res.scalar()
            policy_res = conn.execute(text("INSERT INTO policies (client_id, policy_number, policy_type, insurer_name, tpa_name, start_date, end_date) VALUES (:cid, :pnum, :ptype, :insurer, :tpa, :sdate, :edate) RETURNING id"), {"cid": client_id, "pnum": policy_data["policy_number"], "ptype": policy_data["policy_type"], "insurer": policy_data.get("insurer_name", ""), "tpa": policy_data.get("tpa_name", ""), "sdate": policy_data["start_date"], "edate": policy_data["end_date"]})
            policy_id = policy_res.scalar()
            for tpl in templates_list:
                conn.execute(text("INSERT INTO client_templates (client_id, template_name, action_type, columns_mapping) VALUES (:cid, :tname, :atype, :cols)"), {"cid": client_id, "tname": tpl["name"], "atype": tpl["action"], "cols": json.dumps(tpl["columns"])})
            return True, "Client Workspace created successfully.", client_id, policy_id
    except Exception as e:
        return False, f"Transaction failed: {str(e)}", None, None

def delete_client_workspace(engine, client_id):
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM clients WHERE id = :cid"), {"cid": client_id})
        return True, "Workspace permanently deleted."
    except Exception as e: return False, f"Deletion failed: {str(e)}"

# ==========================================
# MASTER ROSTER & TEMPLATES
# ==========================================
def bulk_insert_policy_members(engine, policy_id, members_list):
    try:
        with engine.begin() as conn:
            for row in members_list:
                conn.execute(text("INSERT INTO active_policy_members (policy_id, employee_id, employee_name, uhid, relation, raw_data) VALUES (:pid, :eid, :ename, :uhid, :rel, :raw)"), {"pid": policy_id, "eid": str(row.get("EMPLOYEE ID", "")), "ename": str(row.get("EMPLOYEE NAME", "")), "uhid": str(row.get("UHID", "")), "rel": str(row.get("RELATION", "")), "raw": json.dumps(row, default=str)})
        return True, f"Successfully inserted {len(members_list)} records."
    except Exception as e: return False, f"Bulk insert failed: {str(e)}"

def get_all_policy_members_for_finance(engine, policy_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT raw_data FROM active_policy_members WHERE policy_id = :pid"), {"pid": policy_id}).fetchall()
            if not result: return pd.DataFrame()
            return pd.DataFrame([json.loads(r.raw_data) if isinstance(r.raw_data, str) else r.raw_data for r in result])
    except: return pd.DataFrame()

def get_policy_members_as_df(engine, policy_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT raw_data FROM active_policy_members WHERE policy_id = :pid AND (raw_data->>'STATUS OF INDIVIDUAL UHID' IS NULL OR raw_data->>'STATUS OF INDIVIDUAL UHID' != 'Cancelled')"), {"pid": policy_id}).fetchall()
            if not result: return pd.DataFrame()
            return pd.DataFrame([json.loads(r.raw_data) if isinstance(r.raw_data, str) else r.raw_data for r in result])
    except: return pd.DataFrame()

def get_client_templates(engine, client_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT action_type, columns_mapping FROM client_templates WHERE client_id = :cid AND is_active = TRUE"), {"cid": client_id}).fetchall()
            return {r.action_type: (json.loads(r.columns_mapping) if isinstance(r.columns_mapping, str) else r.columns_mapping) for r in result}
    except: return {}

# ==========================================
# ENDORSEMENTS & WRITINGS
# ==========================================
def save_endorsement_batch(engine, policy_id, batch_name, additions_list, deletions_list):
    try:
        with engine.begin() as conn:
            batch_id = conn.execute(text("INSERT INTO endorsement_batches (policy_id, batch_name) VALUES (:pid, :bname) RETURNING id"), {"pid": policy_id, "bname": batch_name}).scalar()
            for row in additions_list: conn.execute(text("INSERT INTO endorsement_records (batch_id, record_type, raw_data) VALUES (:bid, 'Addition', :raw)"), {"bid": batch_id, "raw": json.dumps(row, default=str)})
            for row in deletions_list: conn.execute(text("INSERT INTO endorsement_records (batch_id, record_type, raw_data) VALUES (:bid, 'Deletion', :raw)"), {"bid": batch_id, "raw": json.dumps(row, default=str)})
        return True, f"Saved Batch '{batch_name}'."
    except Exception as e: return False, f"Save failed: {str(e)}"

def get_unsynced_batches(engine, policy_id):
    with engine.connect() as conn:
        return [{"id": r.id, "name": r.batch_name} for r in conn.execute(text("SELECT id, batch_name FROM endorsement_batches WHERE policy_id = :pid AND is_synced = FALSE"), {"pid": policy_id}).fetchall()]

def sync_batch_to_master(engine, batch_id, policy_id):
    try:
        with engine.begin() as conn:
            adds = conn.execute(text("SELECT raw_data FROM endorsement_records WHERE batch_id = :bid AND record_type = 'Addition'"), {"bid": batch_id}).fetchall()
            dels = conn.execute(text("SELECT raw_data FROM endorsement_records WHERE batch_id = :bid AND record_type = 'Deletion'"), {"bid": batch_id}).fetchall()
            for row in adds:
                rec = json.loads(row.raw_data) if isinstance(row.raw_data, str) else row.raw_data
                rec["STATUS OF INDIVIDUAL UHID"] = "Active"
                conn.execute(text("INSERT INTO active_policy_members (policy_id, employee_id, employee_name, uhid, relation, raw_data) VALUES (:pid, :eid, :ename, :uhid, :rel, :raw)"), {"pid": policy_id, "eid": str(rec.get("MEMBERID / EMPID", rec.get("EMPLOYEE ID", ""))), "ename": str(rec.get("INSURED NAME", rec.get("EMPLOYEE NAME", ""))), "uhid": str(rec.get("UHID", "")), "rel": str(rec.get("RELATION SHIP", rec.get("RELATION", ""))), "raw": json.dumps(rec, default=str)})
            for row in dels:
                rec = json.loads(row.raw_data) if isinstance(row.raw_data, str) else row.raw_data
                uhid = str(rec.get("UHID", ""))
                if uhid: conn.execute(text("UPDATE active_policy_members SET raw_data = jsonb_set(raw_data, '{STATUS OF INDIVIDUAL UHID}', '\"Cancelled\"', true) WHERE policy_id = :pid AND uhid = :uhid"), {"pid": policy_id, "uhid": uhid})
            conn.execute(text("UPDATE endorsement_batches SET is_synced = TRUE WHERE id = :bid"), {"bid": batch_id})
        return True, "Batch synced to master successfully."
    except Exception as e: return False, f"Sync Failed: {str(e)}"

def save_rate_card(engine, policy_id, writing_name, gst_rate, start_date, end_date, rates_json):
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE rate_cards SET is_active = FALSE WHERE policy_id = :pid"), {"pid": policy_id})
            conn.execute(text("INSERT INTO rate_cards (policy_id, writing_name, gst_rate, start_date, end_date, is_active, rates_json) VALUES (:pid, :name, :gst, :sdate, :edate, TRUE, :rjson)"), {"pid": policy_id, "name": writing_name, "gst": gst_rate, "sdate": start_date, "edate": end_date, "rjson": rates_json})
        return True, "Rate card saved."
    except Exception as e: return False, f"Save failed: {str(e)}"

def get_active_rate_card(engine, policy_id):
    with engine.connect() as conn: return conn.execute(text("SELECT * FROM rate_cards WHERE policy_id = :pid AND is_active = TRUE LIMIT 1"), {"pid": policy_id}).fetchone()

def get_all_rate_cards(engine, policy_id):
    with engine.connect() as conn: return [dict(r._mapping) for r in conn.execute(text("SELECT id, writing_name, is_active, start_date, end_date, gst_rate FROM rate_cards WHERE policy_id = :pid ORDER BY created_at DESC"), {"pid": policy_id}).fetchall()]

def get_batch_records(engine, batch_id):
    with engine.connect() as conn: return [dict(r._mapping) for r in conn.execute(text("SELECT record_type, raw_data FROM endorsement_records WHERE batch_id = :bid"), {"bid": batch_id}).fetchall()]

def get_all_batches(engine, policy_id):
    with engine.connect() as conn: return [{"id": r.id, "name": r.batch_name} for r in conn.execute(text("SELECT id, batch_name, created_at FROM endorsement_batches WHERE policy_id = :pid ORDER BY id DESC"), {"pid": policy_id}).fetchall()]

# ==========================================
# ✨ NEW: CD MANAGEMENT (CASH DEPOSIT)
# ==========================================

def save_cd_statement(engine, policy_id, statement_name, records):
    """Saves the uploaded CD CSV into the database."""
    try:
        with engine.begin() as conn:
            res = conn.execute(text("INSERT INTO cd_statements (policy_id, statement_name) VALUES (:pid, :name) RETURNING id"), {"pid": policy_id, "name": statement_name})
            statement_id = res.scalar()
            
            for row in records:
                conn.execute(text("""
                    INSERT INTO cd_transactions (statement_id, transaction_date, transaction_type, debit, credit, closing_balance, raw_data)
                    VALUES (:sid, :tdate, :ttype, :debit, :credit, :close_bal, :raw)
                """), {
                    "sid": statement_id,
                    "tdate": row.get('transaction_date') if pd.notna(row.get('transaction_date')) else None,
                    "ttype": str(row.get('transaction_type', '')),
                    "debit": float(row.get('debit', 0.0)),
                    "credit": float(row.get('credit', 0.0)),
                    "close_bal": float(row.get('closingbalance', 0.0)),
                    "raw": json.dumps(row, default=str)
                })
        return True, "CD Statement successfully saved to Ledger."
    except Exception as e:
        return False, str(e)

def get_latest_cd_balance(engine, policy_id):
    """Fetches the MOST RECENT closing balance by grabbing the physically last row of the latest statement."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT cd_transactions.closing_balance, cd_transactions.transaction_date 
                FROM cd_transactions 
                JOIN cd_statements ON cd_transactions.statement_id = cd_statements.id
                WHERE cd_statements.policy_id = :pid 
                ORDER BY cd_statements.id DESC, cd_transactions.id DESC 
                LIMIT 1
            """), {"pid": policy_id}).fetchone()
            
            if result:
                date_str = result.transaction_date.strftime('%Y-%m-%d') if result.transaction_date else "N/A"
                return float(result.closing_balance), date_str
            return 0.00, "N/A"
    except Exception as e:
        print(e)
        return 0.00, "N/A"
    
# ==========================================
# ✨ AUDIT TRAIL / ACTIVITY LOGS ✨
# ==========================================
def log_activity(engine, client_id, username, action_type, details):
    """Logs an action performed by a user in a specific workspace."""
    if not client_id: return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO activity_logs (client_id, username, action_type, details)
                VALUES (:cid, :uname, :action, :details)
            """), {"cid": client_id, "uname": username, "action": action_type, "details": details})
    except Exception as e:
        print(f"Failed to log activity: {e}")

def get_activity_logs(engine, client_id):
    """Fetches the audit trail for a specific workspace."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("""
                SELECT username, action_type, details, created_at 
                FROM activity_logs 
                WHERE client_id = :cid 
                ORDER BY created_at DESC LIMIT 100
            """), {"cid": client_id}).fetchall()
            return [dict(r._mapping) for r in res]
    except:
        return []
    

# ==========================================
# ✨ USER PROVISIONING & ACCESS MANAGEMENT ✨
# ==========================================
import hashlib

def hash_password(password):
    """Securely hashes passwords using SHA-256 before saving to DB."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_app_user(engine, username, password, role, client_id=None):
    """Creates a new user and securely hashes their password."""
    try:
        hashed_pw = hash_password(password)
        with engine.begin() as conn:
            # Check if username exists
            existing = conn.execute(text("SELECT id FROM app_users WHERE username = :u"), {"u": username}).fetchone()
            if existing:
                return False, "Username already exists! Please choose another."

            conn.execute(text("""
                INSERT INTO app_users (username, password_hash, role, client_id)
                VALUES (:u, :p, :r, :cid)
            """), {"u": username, "p": hashed_pw, "r": role, "cid": client_id})
        return True, f"User '{username}' created successfully."
    except Exception as e:
        return False, f"Failed to create user: {str(e)}"

def get_all_users(engine):
    """Fetches all users and their associated client workspace."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.id, u.username, u.role, c.client_name, u.created_at 
                FROM app_users u
                LEFT JOIN clients c ON u.client_id = c.id
                ORDER BY u.created_at DESC
            """)).fetchall()
            return [dict(r._mapping) for r in result]
    except:
        return []

def delete_app_user(engine, user_id):
    """Deletes a user's access to the system."""
    try:
        with engine.begin() as conn:
            # Prevent deleting the master admin
            role = conn.execute(text("SELECT role FROM app_users WHERE id = :id"), {"id": user_id}).scalar()
            if role == 'admin' and user_id == 1:
                return False, "Cannot delete the primary master admin."
                
            conn.execute(text("DELETE FROM app_users WHERE id = :id"), {"id": user_id})
        return True, "User access revoked."
    except Exception as e:
        return False, f"Deletion failed: {str(e)}"