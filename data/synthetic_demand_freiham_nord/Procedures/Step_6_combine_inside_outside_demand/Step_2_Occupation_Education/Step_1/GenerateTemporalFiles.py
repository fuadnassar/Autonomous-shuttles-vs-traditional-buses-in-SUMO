import pandas as pd
import re
import os
import math
import numpy as np

# ==========================================
# 1. DISTRIBUTION LISTS
# ==========================================

time_slots = [
    '5-6', '6-7', '7-8', '8-9', '9-10', '10-11', '11-12', '12-13', 
    '13-14', '14-15', '15-16', '16-17', '17-18', '18-19', '19-20', '20-21', '21-22'
]

dist_shopping = [
    0.0103, 0.0207, 0.0103, 0.0828, 0.0828, 0.1149, 0.1149, 0.1149,
    0.0598, 0.0598, 0.0598, 0.0667, 0.0667, 0.0667, 0.0207, 0.0207, 0.0207
]

dist_errands = [
    0.0037, 0.0074, 0.0037, 0.0519, 0.0519, 0.0938, 0.0938, 0.0938,
    0.0617, 0.0617, 0.0617, 0.1012, 0.1012, 0.1012, 0.0296, 0.0296, 0.0296
]

# Occupation: 8 slots defined, rest 0
dist_occupation = [
    0.1194, 0.2388, 0.1194, 0.1542, 0.1542, 0.0696, 0.0696, 0.0696,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
]

# Education: 6 slots defined, rest 0
dist_education = [
    0.1538, 0.3076, 0.1538, 0.1538, 0.1538, 0.0598, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
]

# ==========================================
# 2. COORDINATE DATA LISTS
# ==========================================

# Fixed Origin Coordinates
origin_x_data = [
    -150, 0, 125, -210, -50, 85, -310, -120, 30, -330, -150, -20, -315, -160, -95, 
    -35, -50, 85, 255, 230, 335, 175, 290, 370, 180, 320, 380, 235, 300, 430, 330, 
    450, 10, 160, 40, 200, 435
]

origin_y_data = [
    620, 600, 580, 480, 485, 475, 250, 295, 290, 115, 190, 125, -43, 50, -45, 
    -175, -290, -255, 380, 270, 285, 130, 155, 130, 0, 50, -40, -200, -380, 
    -335, -525, -500, -480, -440, -600, -565, -660
]

# Special 'ubhan' Destination Coordinates
ubhan_x_data = [
    65, 65, 65, -180, 65, 65, -180, 65, 65, -180, -180, 65, -180, -180, -180, 
    65, -180, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 
    -180, 65, -180, 65, 65
]

ubhan_y_data = [
    -83, -83, -83, -140, -83, -83, -140, -83, -83, -140, -140, -83, -140, -140, -140, 
    -83, -140, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, -83, 
    -140, -83, -140, -83, -83
]

# ==========================================
# 3. LOGIC FUNCTIONS
# ==========================================

def distribute_integers(total_val, probabilities):
    total = int(round(total_val))
    if total == 0:
        return [0] * len(probabilities)
    
    prob_sum = sum(probabilities)
    if prob_sum == 0:
        return [0] * len(probabilities)
    normalized_probs = [p / prob_sum for p in probabilities]
    
    ideal_shares = [total * p for p in normalized_probs]
    integers = [math.floor(x) for x in ideal_shares]
    remainders = [x - math.floor(x) for x in ideal_shares]
    
    current_sum = sum(integers)
    shortfall = total - current_sum
    sorted_indices = np.argsort(remainders)[::-1]
    
    for i in range(shortfall):
        idx = sorted_indices[i]
        integers[idx] += 1
    return integers

def get_distribution_list(col_name):
    name_lower = str(col_name).lower()
    
    # 1. Check for Occupation
    if 'occupation' in name_lower:
        return dist_occupation
    # 2. Check for Education
    elif 'education' in name_lower:
        return dist_education
    # 3. Check existing
    elif 'shop' in name_lower:
        return dist_shopping
    elif 'errand' in name_lower:
        return dist_errands
        
    return dist_occupation

def calculate_duration(col_name):
    name_lower = str(col_name).lower()
    duration = 0
    
    if 'occupation' in name_lower:
        duration += 24300
    if 'education' in name_lower:
        duration += 16200
        
    if 'outside' in name_lower:
        duration += 3120
        
    return duration

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()

def get_destination_info(col_name, num_rows):
    """
    Returns tuple: (destination_name_string, dest_x_list, dest_y_list)
    """
    name_lower = str(col_name).lower()
    
    # Initialize defaults
    dest_name = ""
    x_list = [None] * num_rows
    y_list = [None] * num_rows
    
    # 1. SPECIFIC EDUCATION LOCATIONS
    if 'education_inside_d' in name_lower:
        dest_name = "D-Education"
        x_list = [-240] * num_rows
        y_list = [-235] * num_rows
        
    elif 'education_inside_u' in name_lower:
        dest_name = "U-Education"
        x_list = [-35] * num_rows
        y_list = [735] * num_rows

    elif 'education_inside_z' in name_lower:
        dest_name = "Z-Education"
        x_list = [145] * num_rows
        y_list = [-757] * num_rows

    # 2. Check 'inside' + Center keywords
    elif 'inside' in name_lower and 'district' in name_lower:
        dest_name = "District Center"
        x_list = [400] * num_rows
        y_list = [-700] * num_rows
        
    elif 'inside' in name_lower and 'local' in name_lower:
        dest_name = "Local Center"
        x_list = [210] * num_rows
        y_list = [-125] * num_rows
        
    # 3. Check S-Bahn / U-Bahn keywords
    elif 'aubing' in name_lower:
        dest_name = "Aubing S-Bhan"
        x_list = [390] * num_rows
        y_list = [895] * num_rows
        
    elif 'freiahm_sbhan' in name_lower:
        dest_name = "Freiham S-Bhan"
        x_list = [545] * num_rows
        y_list = [-810] * num_rows
        
    elif 'ubhan' in name_lower:
        dest_name = "U-Bhan"
        # Pad or slice special U-Bahn list
        current_x = ubhan_x_data
        current_y = ubhan_y_data
        if len(current_x) < num_rows:
            current_x = current_x + [None] * (num_rows - len(current_x))
            current_y = current_y + [None] * (num_rows - len(current_y))
        x_list = current_x[:num_rows]
        y_list = current_y[:num_rows]
        
    return dest_name, x_list, y_list

# ==========================================
# 4. MAIN SCRIPT
# ==========================================

def generate_column_files(input_file):
    output_folder = "results_integer"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")

    try:
        df = pd.read_excel(input_file)
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        return

    first_col_name = df.columns[0]
    
    for col_name in df.columns[1:]:
        percentages = get_distribution_list(col_name)
        if percentages is None: 
            continue

        # 1. Create Dataframe Subset
        new_df = df[[first_col_name, col_name]].copy()
        
        # 2. Rename First Column to 'Origin'
        new_df.rename(columns={first_col_name: 'Origin'}, inplace=True)
        
        # 3. Rename Value Column to 'agents'
        new_df.rename(columns={col_name: 'agents'}, inplace=True)
        
        row_count = len(new_df)
        
        # 4. Determine Destination Data
        dest_name, dest_x_list, dest_y_list = get_destination_info(col_name, row_count)
        
        # 5. Insert 'Destination' Column (after Origin)
        new_df.insert(1, 'Destination', dest_name)
        
        # 6. Add Coordinate Columns
        if row_count > len(origin_x_data):
            curr_orig_x = origin_x_data + [0] * (row_count - len(origin_x_data))
            curr_orig_y = origin_y_data + [0] * (row_count - len(origin_y_data))
        else:
            curr_orig_x = origin_x_data[:row_count]
            curr_orig_y = origin_y_data[:row_count]
            
        new_df['origin_x'] = curr_orig_x
        new_df['origin_y'] = curr_orig_y
        new_df['destination_x'] = dest_x_list
        new_df['destination_y'] = dest_y_list

        # 7. Reorder Columns
        cols = ['Origin', 'Destination', 'origin_x', 'origin_y', 'destination_x', 'destination_y', 'agents']
        new_df = new_df[cols]

        # 8. Distribute integers across time slots
        distributed_data = []
        for index, row in new_df.iterrows():
            total_value = row['agents']
            if pd.isna(total_value): total_value = 0
            
            row_distribution = distribute_integers(total_value, percentages)
            distributed_data.append(row_distribution)
        
        # 9. Create DataFrame for time slots
        dist_df = pd.DataFrame(distributed_data, columns=time_slots)
        
        # 10. Final Concatenation
        final_df = pd.concat([new_df.reset_index(drop=True), dist_df], axis=1)
        
        # 11. Add Duration
        duration_val = calculate_duration(col_name)
        final_df['activity duration'] = duration_val
        
        # 12. Save
        safe_name = sanitize_filename(col_name)
        output_filename = os.path.join(output_folder, f"{safe_name}.xlsx")
        final_df.to_excel(output_filename, index=False)
        print(f"Generated: {output_filename} (Dest: {dest_name})")

if __name__ == "__main__":
    file_name = "All_Demand_Occupation_Education.xlsx"
    generate_column_files(file_name)