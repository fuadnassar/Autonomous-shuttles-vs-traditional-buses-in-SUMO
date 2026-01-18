import pandas as pd
import random

# 1. Load the home locations data
try:
    homes_df = pd.read_excel('data_homes_locations.xlsx')
except Exception:
    homes_df = pd.read_csv('data_homes_locations.xlsx - Sheet1.csv')

# Clean the coordinate column
coord_col = [col for col in homes_df.columns if 'x,y' in col][0]
homes_df[['x', 'y']] = homes_df[coord_col].str.split(',', expand=True).astype(float)

# Clean block names (strip spaces) to ensure matching works
homes_df['name_block'] = homes_df['name_block'].astype(str).str.strip()
houses_by_block = {name: group.to_dict('records') for name, group in homes_df.groupby('name_block')}

# 2. Load Attractions Data (New Step)
# We read the destination coordinates from this file instead of the trips file
attractions_df = pd.read_excel('Attractions_Sumo_Coordinates.xlsx')

# Create a dictionary for easy lookup: {'local': {'x': 210, 'y': -125}, ...}
# We normalize the name to lowercase just in case
attractions_map = {}
for _, row in attractions_df.iterrows():
    name_key = str(row['name']).lower().strip()
    attractions_map[name_key] = (row['x'], row['y'])

def process_trips(df, dest_name, dest_key, houses_dict, attr_map):
    records = []
    
    # Get the X, Y for this destination from our attractions map
    # dest_key should be 'local' or 'district' to match your file
    dest_x, dest_y = attr_map.get(dest_key, (0, 0))
    
    # Fix: Matches Excel time format "07:00:00" instead of "7:00"
    time_cols = [f"{h:02d}:00:00" for h in range(7, 22)]
    
    for _, row in df.iterrows():
        block_name = str(row['name']).strip()
        available_houses = houses_dict.get(block_name, [])
        
        if not available_houses:
            continue
            
        for col in time_cols:
            # Safety check if column exists
            if col not in df.columns:
                continue
                
            count = int(row[col])
            if count > 0:
                hour = int(col.split(':')[0])
                for _ in range(count):
                    selected_house = random.choice(available_houses)
                    random_sec = random.randint(0, 3599)
                    departure_time = (hour - 6) * 3600 + random_sec
                    
                    record = {
                        'name_block': block_name,
                        'house_id': selected_house['house_id'],
                        'origin_x': selected_house['x'],
                        'origin_y': selected_house['y'],
                        'home_departure_time': departure_time,
                        'name_destination': dest_name,
                        'destination_x': dest_x, # Uses coordinates from attractions file
                        'destination_y': dest_y, # Uses coordinates from attractions file
                        'shopping time': 1140
                    }
                    records.append(record)
    return records

# 3. Load trip data
# Correctly pointing to results_from_step_4
df_local = pd.read_excel('results_from_step_4/trips_local_center.xlsx')
df_district = pd.read_excel('results_from_step_4/trips_district_center.xlsx')

# Fix: Ensure columns are strings so we can find "07:00:00"
df_local.columns = df_local.columns.astype(str)
df_district.columns = df_district.columns.astype(str)

# 4. Process both datasets
# We pass 'local' and 'district' as keys to find coordinates in the attractions_map
all_records = process_trips(df_local, "Local Center", "local", houses_by_block, attractions_map) + \
              process_trips(df_district, "District Center", "district", houses_by_block, attractions_map)

# 5. Create Final DataFrame and add person_id
final_df = pd.DataFrame(all_records)
if not final_df.empty:
    final_df.insert(0, 'person_id', range(1, len(final_df) + 1))
    print(f"Success! Generated {len(final_df)} plans.")
else:
    print("Warning: No plans generated. Check if block names match between files.")

# 6. Save to Excel
final_df.to_excel('results/personal_planes.xlsx', index=False)