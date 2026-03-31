import pandas as pd
import os

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Update this filename to match the file you want to process
file_name = 'input/MID_Data.xlsx'  # or 'MID_Data.xlsx - Sheet1.csv'

# Output filename
output_file = 'results/Hourly_Demand_Distribution.csv'

# ---------------------------------------------------------
# 1. LOAD DATA ROBUSTLY
# ---------------------------------------------------------
def load_data(file_path):
    print(f"Attempting to load: {file_path}")
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() in ['.xlsx', '.xls']:
        # Read as Excel
        try:
            return pd.read_excel(file_path)
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            raise
    else:
        # Read as CSV (try utf-8 first, then latin1)
        try:
            return pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            print("UTF-8 failed, trying 'latin1' encoding...")
            return pd.read_csv(file_path, encoding='latin1')

try:
    df = load_data(file_name)
    print("File loaded successfully.")
    print("Columns found:", df.columns.tolist())
except FileNotFoundError:
    print(f"Error: The file '{file_name}' was not found in the directory.")
    print("Please check the file name in the 'CONFIGURATION' section above.")
    exit()

# ---------------------------------------------------------
# 2. DATA CLEANING
# ---------------------------------------------------------
# Clean column names (remove whitespace)
df.columns = df.columns.str.strip()

# Map the typos in your source file to clean names
# Adjust keys (left side) if your specific file has different spellings
column_map = {
    'occupatipon': 'Occupation',
    'Eduction': 'Education',
    'Shpping': 'Shopping',
    'Errands': 'Errands',
    'Leisure': 'Leisure',
    'accompainiment': 'Accompaniment'
}

# Verify that required columns exist before proceeding
# We find which columns from the map are actually in the df
available_cols = [c for c in column_map.keys() if c in df.columns]
if not available_cols:
    # Fallback: maybe the user already fixed the headers?
    # If headers are already correct, we just use them.
    column_map = {c: c for c in ['Occupation', 'Education', 'Shopping', 'Errands', 'Leisure', 'Accompaniment'] if c in df.columns}

# ---------------------------------------------------------
# 3. CALCULATE HOURLY DISTRIBUTION
# ---------------------------------------------------------
# Logic: distribute period demand into hours
periods_config = [
    {
        'row_idx': 0, # early morning (5 to before 8 a.m.)
        'hours': ['5-6', '6-7', '7-8'],
        'weights': [0.25, 0.50, 0.25] # Peak at 6-7
    },
    {
        'row_idx': 1, # morning (8 to before 10 am)
        'hours': ['8-9', '9-10'],
        'weights': [0.5, 0.5]
    },
    {
        'row_idx': 2, # morning (10 am to before 1 pm)
        'hours': ['10-11', '11-12', '12-13'],
        'weights': [1/3, 1/3, 1/3]
    },
    {
        'row_idx': 3, # midday (1 p.m. to just before 4 p.m.)
        'hours': ['13-14', '14-15', '15-16'],
        'weights': [1/3, 1/3, 1/3]
    },
    {
        'row_idx': 4, # afternoon (4 pm to before 7 pm)
        'hours': ['16-17', '17-18', '18-19'],
        'weights': [1/3, 1/3, 1/3]
    },
    {
        'row_idx': 5, # evenings (7 pm to before 10 pm)
        'hours': ['19-20', '20-21', '21-22'],
        'weights': [1/3, 1/3, 1/3]
    },
    {
        'row_idx': 6, # at night (10 pm to before 5 am)
        'hours': ['22-23', '23-24', '0-1', '1-2', '2-3', '3-4', '4-5'],
        'weights': [1/7]*7
    }
]

new_data = []

for config in periods_config:
    row_idx = config['row_idx']
    hours = config['hours']
    weights = config['weights']
    
    # Check if row_idx is valid
    if row_idx >= len(df):
        print(f"Warning: Row index {row_idx} out of bounds. Stopping.")
        break
        
    for i, hour in enumerate(hours):
        weight = weights[i]
        new_row = {'Display_Time': hour}
        
        for old_col, new_col in column_map.items():
            if old_col in df.columns:
                val = df.at[row_idx, old_col]
                # Ensure value is numeric
                try:
                    val = float(val)
                except:
                    val = 0.0
                new_row[new_col] = val * weight
                
        new_data.append(new_row)

# ---------------------------------------------------------
# 4. SAVE RESULTS
# ---------------------------------------------------------
result_df = pd.DataFrame(new_data)

# Reorder if columns exist
final_cols = ['Display_Time', 'Occupation', 'Education', 'Shopping', 'Errands', 'Leisure', 'Accompaniment']
existing_final_cols = [c for c in final_cols if c in result_df.columns]
result_df = result_df[existing_final_cols]

result_df.to_csv(output_file, index=False)
print(f"Successfully created '{output_file}'")
print(result_df.head(10))