import pandas as pd
import numpy as np
import os
import random
import math

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_FOLDER = "results_from_step_1"
OUTPUT_FILE = "Final_Collected_Shopp_Erra_Liesu_Demand.xlsx"  # Changed to .xlsx

# The columns representing time slots in your Excel files
TIME_SLOTS = [
    '5-6', '6-7', '7-8', '8-9', '9-10', '10-11', '11-12', '12-13', 
    '13-14', '14-15', '15-16', '16-17', '17-18', '18-19', '19-20', '20-21', '21-22'
]

# ==========================================
# MAIN LOGIC
# ==========================================

def process_files():
    # List to hold all generated rows from all files
    all_generated_trips = []

    # 1. Check if input folder exists
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Folder '{INPUT_FOLDER}' not found.")
        return

    # 2. Get list of Excel files
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.xlsx') or f.endswith('.xls')]
    
    if not files:
        print(f"No Excel files found in {INPUT_FOLDER}")
        return

    print(f"Found {len(files)} files. Processing...")

    # 3. Iterate through each file
    for filename in files:
        file_path = os.path.join(INPUT_FOLDER, filename)
        print(f"Reading: {filename}...")
        
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            print(f"Skipping {filename}: {e}")
            continue

        # 4. Iterate through each row in the current file
        for index, row in df.iterrows():
            
            # Extract static data for this row
            origin_val = row.get('Origin', '')
            dest_val   = row.get('Destination', '')
            
            # Ensure coordinates are floats for calculation
            try:
                orig_x = float(row.get('origin_x', 0))
                orig_y = float(row.get('origin_y', 0))
                dest_x = float(row.get('destination_x', 0))
                dest_y = float(row.get('destination_y', 0))
            except (ValueError, TypeError):
                # Handle cases where coordinates might be missing/None
                orig_x, orig_y, dest_x, dest_y = 0.0, 0.0, 0.0, 0.0

            duration = row.get('activity duration', 0)

            # Calculate Euclidean Distance: sqrt((x2-x1)^2 + (y2-y1)^2)
            distance = math.sqrt((dest_x - orig_x)**2 + (dest_y - orig_y)**2)

            # 5. Iterate through time slots
            for time_idx, time_col in enumerate(TIME_SLOTS):
                
                # Check if this time column exists in the file
                if time_col in df.columns:
                    agent_count = row[time_col]
                    
                    # Ensure it's a valid number
                    if pd.isna(agent_count) or agent_count <= 0:
                        continue
                        
                    agent_count = int(agent_count)

                    # 6. Generate a row for EACH agent
                    for _ in range(agent_count):
                        # Calculate time range for this slot
                        start_seconds = time_idx * 3600
                        end_seconds = (time_idx + 1) * 3600
                        
                        # Random departure time within the slot
                        random_departure = random.randint(start_seconds, end_seconds)
                        
                        # Create the new trip entry
                        trip_data = {
                            'Origin': origin_val,
                            'Destination': dest_val,
                            'origin_x': orig_x,
                            'origin_y': orig_y,
                            'destination_x': dest_x,
                            'destination_y': dest_y,
                            'euclidean_distance': round(distance, 2),
                            'agents': 1,
                            'departure_time': random_departure,
                            'activity duration': duration,
                            'Source_File': filename
                        }
                        
                        all_generated_trips.append(trip_data)

    # 7. Convert list to DataFrame
    if not all_generated_trips:
        print("No trips generated. Please check your input files.")
        return

    print("Consolidating data...")
    final_df = pd.DataFrame(all_generated_trips)

    # 8. Save to Excel (.xlsx)
    print(f"Saving to {OUTPUT_FILE} (this might take a moment)...")
    final_df.to_excel(OUTPUT_FILE, index=False)
    
    print(f"========================================")
    print(f"Process Complete!")
    print(f"Total trips generated: {len(final_df)}")
    print(f"File saved as: {OUTPUT_FILE}")
    print(f"========================================")

if __name__ == "__main__":
    process_files()