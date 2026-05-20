import pandas as pd
import numpy as np
import json
import io
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from dateutil import parser as date_parser
import traceback

# ==========================================
# ENTERPRISE DATA SCRUBBER & DATE PARSER
# ==========================================

def intelligent_scrubber(df):
    df = df.fillna("")
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d').fillna("")
        if df[col].dtype == object:
            df[col] = df[col].astype(str)
            df[col] = df[col].replace(["nan", "NaN", "NaT", "<NA>", "None"], "")
            df[col] = df[col].apply(lambda x: "" if str(x).strip().startswith("###") else x)
            df[col] = df[col].str.strip()
    return df

def parse_universal_date(date_str):
    if not date_str or str(date_str).strip().lower() in ["nan", "nat", "none", ""]:
        return pd.NaT
    try:
        return pd.to_datetime(date_str, format='mixed')
    except:
        try:
            parsed = date_parser.parse(str(date_str))
            return pd.to_datetime(parsed)
        except:
            return pd.NaT

# ==========================================
# MODULE 1: MASTER ONBOARDING
# ==========================================

def process_policy_dataframe(df):
    try:
        df = intelligent_scrubber(df)
        records = df.to_dict(orient="records")
        
        alias_map = {
            "EMPLOYEE ID": ["employee id", "emp id", "empid", "id", "memberid / empid", "memberid"],
            "EMPLOYEE NAME": ["insured name", "employee name", "emp name", "name", "member name"],
            "UHID": ["uhid", "individual uhid", "tpa id", "health id"],
            "RELATION": ["relationshi", "relationship", "relation", "rel", "relation ship"]
        }
        
        for row in records:
            lower_keys = {str(k).strip().lower(): k for k in row.keys()}
            for standard_key, aliases in alias_map.items():
                if standard_key not in row:
                    for alias in aliases:
                        if alias in lower_keys:
                            row[standard_key] = row[lower_keys[alias]]
                            break 
        return True, records
    except Exception as e:
        return False, str(e)

# ==========================================
# MODULE 2: ENDORSEMENT ENGINE
# ==========================================

def parse_hr_endorsement_sheet(df):
    try:
        df = intelligent_scrubber(df)
        additions, deletions = [], []
        current_mode = "additions" 
        first_col = df.columns[0]

        for _, row in df.iterrows():
            val = str(row[first_col]).strip().lower()
            if val == "additions": current_mode = "additions"; continue
            elif val == "deletions": current_mode = "deletions"; continue
            if not val and len("".join([str(v) for v in row.values]).strip()) == 0: continue

            if current_mode == "additions": additions.append(row.to_dict())
            else: deletions.append(row.to_dict())
                
        return True, pd.DataFrame(additions), pd.DataFrame(deletions)
    except Exception as e:
        return False, str(e), None

def validate_endorsements(master_df, add_df, del_df):
    if not master_df.empty:
        master_df['EMP_REL_KEY'] = master_df.get('EMPLOYEE ID', pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + master_df.get('RELATION', pd.Series(dtype=str)).astype(str).str.strip().str.upper()
        master_uhids = master_df.get('UHID', pd.Series(dtype=str)).astype(str).str.strip().str.upper().tolist()
        master_keys = master_df['EMP_REL_KEY'].tolist()
    else:
        master_keys, master_uhids = [], []

    validated_additions = []
    if not add_df.empty:
        emp_id_col = next((c for c in add_df.columns if "EMP" in str(c).upper() or "MEMBERID" in str(c).upper()), None)
        rel_col = next((c for c in add_df.columns if "RELATION" in str(c).upper()), None)
        name_col = next((c for c in add_df.columns if "NAME" in str(c).upper()), None)
        dob_col = next((c for c in add_df.columns if "DOB" in str(c).upper() or "BIRTH" in str(c).upper()), None)
        doj_col = next((c for c in add_df.columns if "DOJ" in str(c).upper() or "JOINING" in str(c).upper()), None)
        gender_col = next((c for c in add_df.columns if "GENDER" in str(c).upper() or "SEX" in str(c).upper()), None)
        
        for idx, row in add_df.iterrows():
            status = "🟢 Ready to Process"
            flags = []
            
            emp_id = str(row.get(emp_id_col, "")).strip() if emp_id_col else ""
            relation = str(row.get(rel_col, "")).strip() if rel_col else ""
            
            if not emp_id: flags.append("Missing EMP ID")
            if not relation: flags.append("Missing Relation")
            if name_col and not str(row.get(name_col, "")).strip(): flags.append("Missing Name")
            if dob_col and not str(row.get(dob_col, "")).strip(): flags.append("Missing DOB")
            if doj_col and not str(row.get(doj_col, "")).strip(): flags.append("Missing DOJ")
            if gender_col and not str(row.get(gender_col, "")).strip(): flags.append("Missing Gender")
            
            comp_key = f"{emp_id.upper()}_{relation.upper()}"
            if comp_key in master_keys and emp_id != "": flags.append("Appending to Existing Policy")
                
            error_flags = [f for f in flags if f != "Appending to Existing Policy"]
            if len(error_flags) > 0: status = "🟠 Correction Needed"

            row_data = row.to_dict()
            row_data["Validation Status"] = status
            row_data["Flags"] = " | ".join(flags)
            validated_additions.append(row_data)

    validated_deletions = []
    if not del_df.empty:
        actual_uhid_col = next((c for c in del_df.columns if "UHID" in str(c).upper()), None)
        for idx, row in del_df.iterrows():
            status = "🟢 Ready to Delete"
            flags = []
            uhid = str(row.get(actual_uhid_col, "")).strip() if actual_uhid_col else ""

            if uhid.upper() not in master_uhids and uhid != "":
                status = "🔴 Error"
                flags.append("UHID Not Found in Active Master DB")
            elif not uhid:
                status = "🔴 Missing Data"
                flags.append("Missing UHID")

            row_data = row.to_dict()
            row_data["Validation Status"] = status
            row_data["Flags"] = " | ".join(flags)
            validated_deletions.append(row_data)

    return pd.DataFrame(validated_additions), pd.DataFrame(validated_deletions)

# ==========================================
# MODULE 3: FINANCIAL ENGINE
# ==========================================

def normalize_si(value):
    if pd.isna(value) or value is None or str(value).strip() == "": return None
    val_str = str(value).strip().replace(',', '').replace(' ', '')
    if val_str.endswith('.0'): val_str = val_str[:-2]
    return val_str

def process_financial_batch(batch_records, rate_card, master_df):
    try:
        if hasattr(rate_card, '_mapping'): rc = rate_card._mapping
        elif isinstance(rate_card, dict): rc = rate_card
        else: rc = rate_card.__dict__

        rate_card_data = rc['rates_json']
        if isinstance(rate_card_data, dict):
            rate_card_data = json.dumps(rate_card_data)

        rates_df = pd.read_json(io.StringIO(rate_card_data), orient='split')
        if any('Unnamed' in str(c) for c in rates_df.columns):
            rates_df.columns = rates_df.iloc[0]
            rates_df = rates_df[1:].reset_index(drop=True)
            
        rates_df.columns = [normalize_si(c) for c in rates_df.columns]
        rates_df['calc_min_age'] = pd.to_numeric(rates_df.iloc[:, 0].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
        rates_df['calc_max_age'] = pd.to_numeric(rates_df.iloc[:, 1].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(999)
        
        policy_start = parse_universal_date(rc['start_date'])
        policy_end = parse_universal_date(rc['end_date'])
        policy_days = (policy_end - policy_start).days + 1
        gst_rate = Decimal(str(rc['gst_rate'])) / Decimal(100)

        results = []
        for record in batch_records:
            action = record['record_type']
            raw = record['raw_data']
            if isinstance(raw, str): raw = json.loads(raw)
            
            name = str(raw.get('INSURED NAME', raw.get('EMPLOYEE NAME', 'Unknown')))
            emp_id = str(raw.get('MEMBERID / EMPID', raw.get('EMPLOYEE ID', '')))
            uhid = str(raw.get('UHID', ''))
            
            dob_str = str(raw.get('DOB', ''))
            si_raw = str(raw.get('SUM INSURED', ''))
            
            if action == 'Deletion' and not master_df.empty:
                db_match = pd.DataFrame()
                if uhid and 'UHID' in master_df.columns:
                    db_match = master_df[master_df['UHID'] == uhid]
                if db_match.empty and emp_id:
                    emp_col = next((c for c in master_df.columns if "EMP" in str(c).upper() or "MEMBERID" in str(c).upper()), None)
                    if emp_col: db_match = master_df[master_df[emp_col] == emp_id]

                if not db_match.empty:
                    db_row = db_match.iloc[0]
                    if not dob_str or str(dob_str).lower() in ["nan", "nat", ""]: 
                        dob_str = str(db_row.get('DATE OF BIRTH', db_row.get('DOB', '')))
                    if not si_raw or str(si_raw).lower() in ["nan", "nat", ""]: 
                        si_raw = str(db_row.get('SUM INSURED', db_row.get('SUM_INSURED', '')))

            if action == 'Addition':
                event_date_str = str(raw.get('DOJ', raw.get('DOC', '')))
            else:
                event_date_str = str(raw.get('DOS', raw.get('DOE', raw.get('DOC', ''))))
            
            row_out = {
                "Action": "A" if action == "Addition" else "D",
                "Emp ID": emp_id, "Name": name, "UHID": uhid,
                "Status": "Error", "Total Premium": 0.0, "Base Premium": 0.0, "GST": 0.0, "Remarks": ""
            }

            try:
                event_date = parse_universal_date(event_date_str)
                dob_dt = parse_universal_date(dob_str)
                
                if pd.isna(event_date): raise ValueError(f"Missing/Invalid Event Date (DOJ/DOS): '{event_date_str}'")
                if pd.isna(dob_dt): raise ValueError(f"Missing/Invalid DOB: '{dob_str}'")
                
                age = relativedelta(event_date, dob_dt).years
                norm_si = normalize_si(si_raw)
                
                if not norm_si: raise ValueError(f"Invalid Sum Insured: '{si_raw}'")

                age_row = rates_df[(age >= rates_df['calc_min_age']) & (age <= rates_df['calc_max_age'])]
                if age_row.empty: raise ValueError(f"Age {age} is outside rate card bands.")
                if norm_si not in age_row.columns: raise ValueError(f"Sum Insured '{norm_si}' not found in Rate Card.")
                
                annual_premium = Decimal(str(age_row.iloc[0][norm_si]))
                effective_date = max(event_date, policy_start)
                remaining_days = (policy_end - effective_date).days + 1

                if remaining_days <= 0:
                    base_prem = Decimal('0.00')
                else:
                    daily_rate = annual_premium / Decimal(policy_days)
                    base_prem = (daily_rate * Decimal(remaining_days)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                gst_amt = (base_prem * gst_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_prem = base_prem + gst_amt
                
                row_out.update({
                    "Status": "Success", "Remarks": f"Age {age}, Days: {remaining_days}", 
                    "Remaining Days": remaining_days, "Base Premium": float(base_prem), 
                    "GST": float(gst_amt), "Total Premium": float(total_prem)
                })
            except Exception as e:
                row_out["Remarks"] = str(e)
                
            results.append(row_out)
            
        return True, pd.DataFrame(results), "Success"
    except Exception as e:
        error_details = traceback.format_exc()
        return False, pd.DataFrame(), f"System Error: {str(e)}\n\nDetailed Traceback:\n{error_details}"

# ==========================================
# MODULE 4: TRUE RECONCILIATION ENGINE
# ==========================================

def reconcile_full_rosters(master_df, new_roster_df):
    """
    Compares the current database master against a newly uploaded full HR roster.
    Automatically calculates Additions and Deletions by comparing unique IDs.
    """
    try:
        success, new_records = process_policy_dataframe(new_roster_df)
        if not success: return False, None, None
        
        new_df = pd.DataFrame(new_records)
        
        if master_df.empty:
            return True, new_df, pd.DataFrame()
            
        # Create Unique Keys (EMP_ID + RELATION)
        master_df['UNIQ_KEY'] = master_df.get('EMPLOYEE ID', '').astype(str).str.strip().str.upper() + "_" + master_df.get('RELATION', '').astype(str).str.strip().str.upper()
        
        emp_id_col = next((c for c in new_df.columns if "EMP" in str(c).upper() or "MEMBERID" in str(c).upper()), None)
        rel_col = next((c for c in new_df.columns if "RELATION" in str(c).upper()), None)
        
        if not emp_id_col or not rel_col:
            return False, None, None 
            
        new_df['UNIQ_KEY'] = new_df[emp_id_col].astype(str).str.strip().str.upper() + "_" + new_df[rel_col].astype(str).str.strip().str.upper()

        # 1. ADDITIONS (In New, but NOT in Master)
        additions_df = new_df[~new_df['UNIQ_KEY'].isin(master_df['UNIQ_KEY'])].copy()
        
        # 2. DELETIONS (In Master, but NOT in New)
        deletions_df = master_df[~master_df['UNIQ_KEY'].isin(new_df['UNIQ_KEY'])].copy()

        additions_df.drop(columns=['UNIQ_KEY'], inplace=True, errors='ignore')
        deletions_df.drop(columns=['UNIQ_KEY'], inplace=True, errors='ignore')

        return True, additions_df, deletions_df
    except Exception as e:
        return False, str(e), None
    
# --- ADD THIS TO THE BOTTOM OF logic.py ---

def process_cd_dataframe(df):
    """Parses and cleans the Cash Deposit Ledger CSV."""
    try:
        df = intelligent_scrubber(df)
        
        # Standardize columns to lowercase, no spaces
        df.columns = [str(c).strip().lower().replace(" ", "") for c in df.columns]
        
        records = df.to_dict(orient="records")
        valid_records = []
        
        for row in records:
            # We only want rows that have an actual Closing Balance
            if str(row.get('closingbalance', '')) != "":
                
                # Convert financial columns to floats safely
                for num_col in ['debit', 'credit', 'closingbalance']:
                    val = str(row.get(num_col, '0')).replace(',', '')
                    try: row[num_col] = float(val) if val else 0.0
                    except: row[num_col] = 0.0
                
                # Find the best date (Entered Date or Effective Date)
                date_str = str(row.get('entereddate', row.get('effectivedate', '')))
                dt = parse_universal_date(date_str)
                row['transaction_date'] = dt if pd.notna(dt) else None
                
                # Standardize transaction type
                row['transaction_type'] = str(row.get('transaction_type', row.get('particulars', '')))
                
                valid_records.append(row)
                
        return True, valid_records
    except Exception as e:
        return False, str(e)