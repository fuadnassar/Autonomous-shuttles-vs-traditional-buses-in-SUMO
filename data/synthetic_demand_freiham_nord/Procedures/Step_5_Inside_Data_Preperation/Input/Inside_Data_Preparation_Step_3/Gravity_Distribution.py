import pandas as pd
import numpy as np

def calculate_gravity_model(activity_type, beta=1.0):
    # 1. Construct filenames dynamically
    input_file = f'Inside_(Residential_X_{activity_type}).xlsx'
    output_file = f'Inside_(Residential_X_{activity_type})_Updated.xlsx'
    
    print(f"--- Processing: {activity_type} ---")
    
    # 2. Load the Excel data
    try:
        df = pd.read_excel(input_file)
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found. Skipping.")
        return

    # Clean column names (strip whitespace)
    df.columns = df.columns.str.strip()
    
    # 3. Detect Structure based on Column Count
    num_cols = df.shape[1]
    
    # Column index 8 is always the Demand (9th column)
    # Note: Python uses 0-based indexing, so 9th column = index 8
    demand_col_idx = 8
    total_demand = df.iloc[:, demand_col_idx]
    
    # Setup configuration variables based on total columns
    if num_cols == 19:
        print("Detected 19 columns -> 2 Destinations mode")
        num_dests = 2
        area_start_idx = 9          # Areas at indices 9, 10
        block_x_idx = 11            # Block X at 11
        block_y_idx = 12            # Block Y at 12
        dest_coord_start_idx = 13   # Dest coords start at 13
        output_start_idx = 17       # Output columns start at 17
        
    elif num_cols == 23:
        print("Detected 23 columns -> 3 Destinations mode")
        num_dests = 3
        area_start_idx = 9          # Areas at indices 9, 10, 11
        block_x_idx = 12            # Block X at 12
        block_y_idx = 13            # Block Y at 13
        dest_coord_start_idx = 14   # Dest coords start at 14
        output_start_idx = 20       # Output columns start at 20
        
    else:
        print(f"Error: Unexpected column count ({num_cols}). Expected 19 or 23.")
        return

    # 4. Get Origin Coordinates
    block_x = df.iloc[:, block_x_idx]
    block_y = df.iloc[:, block_y_idx]

    # 5. Calculate Gravity Scores for each destination
    scores = []
    print(f"Calculating gravity scores (Beta={beta})...")
    
    for i in range(num_dests):
        # Select Area column
        dest_area = df.iloc[:, area_start_idx + i]
        
        # Select Coordinate columns (X and Y are paired)
        d_x_col = dest_coord_start_idx + (i * 2)
        d_y_col = dest_coord_start_idx + (i * 2) + 1
        
        dest_x = df.iloc[:, d_x_col]
        dest_y = df.iloc[:, d_y_col]
        
        # Euclidean Distance
        dist = np.sqrt((dest_x - block_x)**2 + (dest_y - block_y)**2)
        
        # Avoid division by zero
        dist = dist.replace(0, 0.1)
        
        # Gravity Formula: Mass / Distance^Beta
        score = dest_area / (dist ** beta)
        scores.append(score)

    # 6. Sum scores to get total attraction
    total_score = np.sum(np.column_stack(scores), axis=1)

    # 7. Calculate Shares and Update Output Columns
    for i in range(num_dests):
        share = scores[i] / total_score
        final_val = (total_demand * share).round(2)
        
        # Update the specific column in the dataframe
        target_col_idx = output_start_idx + i
        col_name = df.columns[target_col_idx]
        df[col_name] = final_val
        
    # 8. Save the file
    print(f"Saving to {output_file}...")
    df.to_excel(output_file, index=False)
    print("Done!\n")

# --- MAIN EXECUTION ---
# Add or remove activity names here as needed
activity_types = ['Occupation', 'Education', 'Shopping', 'Errands', 'Liesure']

for activity in activity_types:
    calculate_gravity_model(activity, beta=1.0)