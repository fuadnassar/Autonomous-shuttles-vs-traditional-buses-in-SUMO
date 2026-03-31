import pandas as pd
import random
import os

def load_homes_data(file_path):
    """Loads and processes the homes location data."""
    try:
        # Try reading as Excel first
        homes_df = pd.read_excel(file_path)
    except Exception:
        # Fallback to CSV if needed
        base_name = file_path.split('.xlsx')[0]
        csv_path = f"{base_name}.xlsx - Sheet1.csv"
        try:
            homes_df = pd.read_csv(csv_path)
        except FileNotFoundError:
            # Last resort: try reading the original filename as csv
            homes_df = pd.read_csv(file_path)

    # Clean the coordinate column
    # Looks for a column containing 'x,y'
    coord_cols = [col for col in homes_df.columns if 'x,y' in col]
    if coord_cols:
        coord_col = coord_cols[0]
        homes_df[['x', 'y']] = homes_df[coord_col].str.split(',', expand=True).astype(float)
    
    # Clean block names to ensure matching works
    homes_df['name_block'] = homes_df['name_block'].astype(str).str.strip()
    
    # Group by block for fast lookup
    return {name: group.to_dict('records') for name, group in homes_df.groupby('name_block')}

def process_demand_file(file_path, houses_dict):
    """Reads a demand file and generates individual trip records with specific column names."""
    print(f"Processing {file_path}...")
    try:
        df = pd.read_excel(file_path)
    except Exception:
        # Fallback if the user has CSVs locally instead of Excel
        df = pd.read_csv(file_path.replace('.xlsx', '.xlsx - Sheet1.csv'))

    records = []
    
    # Check for required input columns
    # Note: 'Origin' maps to 'origin_name', 'Destination' to 'destination_name'
    required_columns = ['Origin', 'Destination', 'destination_x', 'destination_y', 
                        'euclidean_distance', 'agents', 'departure_time', 'activity duration']
    
    for col in required_columns:
        if col not in df.columns:
            print(f"Warning: Column '{col}' missing in {file_path}")
            return []

    for _, row in df.iterrows():
        # 1. Identify the Origin Block (maps to origin_name)
        origin_block = str(row['Origin']).strip()
        
        # 2. Find available houses in this block
        available_houses = houses_dict.get(origin_block, [])
        
        if not available_houses:
            # Skip if no house data exists for this block
            continue
            
        # 3. Generate records for the number of 'agents' specified
        agent_count = int(row['agents'])
        
        for _ in range(agent_count):
            # Select a random house from this block
            selected_house = random.choice(available_houses)
            
            # Create the trip record with the EXACT names you requested
            record = {
                'origin_name': origin_block,           # From Input 'Origin'
                'house_id': selected_house['house_id'], # From Homes File
                'house_x': selected_house['x'],         # From Homes File
                'house_y': selected_house['y'],         # From Homes File
                
                'destination_name': row['Destination'], # From Input 'Destination'
                'destination_x': row['destination_x'],
                'destination_y': row['destination_y'],
                'euclidean_distance': row['euclidean_distance'],
                
                'departure_time': row['departure_time'],
                'activity duration': row['activity duration']
            }
            records.append(record)
            
    return records

# --- Main Execution ---

# 1. Load Home Locations
homes_file = 'data_homes_locations.xlsx'
houses_by_block = load_homes_data(homes_file)
print(f"Loaded homes data. Found {len(houses_by_block)} blocks.")

# 2. Process the two Demand files
files_to_process = [
    'Final_Collected_Occup_Educa_Demand copy.xlsx',
    'Final_Collected_Shopp_Erra_Liesu_Demand copy.xlsx'
]

all_records = []
for file in files_to_process:
    try:
        file_records = process_demand_file(file, houses_by_block)
        all_records.extend(file_records)
        print(f" -> Generated {len(file_records)} trips from {file}")
    except FileNotFoundError:
        print(f"Error: Could not find file {file}")

# 3. Create Final DataFrame
final_df = pd.DataFrame(all_records)

if not final_df.empty:
    # Add person_id at the beginning
    final_df.insert(0, 'person_id', range(1, len(final_df) + 1))
    
    # Select and Reorder columns exactly as requested
    output_columns = [
        'person_id', 
        'origin_name', 
        'house_id', 
        'house_x', 
        'house_y', 
        'destination_name', 
        'destination_x', 
        'destination_y', 
        'euclidean_distance', 
        'departure_time', 
        'activity duration'
    ]
    
    # Ensure only these columns are in the output
    final_df = final_df[output_columns]
    
    # 4. Save to Excel
    output_path = 'results/personal_planes.xlsx'
    
    # Ensure results directory exists
    os.makedirs('results', exist_ok=True)
    
    final_df.to_excel(output_path, index=False)
    print(f"\nSuccess! Total plans generated: {len(final_df)}")
    print(f"Saved to {output_path}")
else:
    print("\nWarning: No plans generated. Check input files and block names.")