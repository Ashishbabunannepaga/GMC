import pandas as pd
import io

def generate_action_excel(dataframe, template_columns, action_flag):
    """
    Takes the processed Endorsement data, aligns it perfectly with the 
    TPA's template columns, and returns an Excel file buffer for download.
    """
    # Create an empty dataframe with ONLY the required TPA columns
    output_df = pd.DataFrame(columns=template_columns)
    
    # Standardize our dataframe columns for easier matching (lowercase, stripped)
    df_lower_cols = {str(col).strip().lower(): col for col in dataframe.columns}
    
    # Map the data
    for col in template_columns:
        target_lower = str(col).strip().lower()
        
        # If the template column exists in our data, copy it over
        if target_lower in df_lower_cols:
            actual_col = df_lower_cols[target_lower]
            output_df[col] = dataframe[actual_col]
            
    # Inject the Flag Status (A, D, or M) if the template asks for it
    flag_col_match = next((c for c in template_columns if "FLAG" in str(c).upper()), None)
    if flag_col_match:
        output_df[flag_col_match] = action_flag
        
    # Generate the Excel File in Memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        output_df.to_excel(writer, index=False, sheet_name=f'Action_{action_flag}')
        
    return buffer.getvalue()