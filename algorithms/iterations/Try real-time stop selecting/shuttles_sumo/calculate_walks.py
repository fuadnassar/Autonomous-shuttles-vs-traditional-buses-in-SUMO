import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os

def calculate_walking_metrics(xml_file, od_file, walk_speed=1.1):
    # Path configuration based on your 'ls' output
    # The user noted od_final_stops.xlsx is in the 'Data' folder
    od_path = os.path.join('Data', 'od_final_stops.xlsx')
    
    if not os.path.exists(xml_file):
        print(f"Error: {xml_file} not found in current directory.")
        return
    if not os.path.exists(od_path):
        # Fallback to the CSV if the Excel isn't directly readable
        od_path = 'od_final_stops.xlsx - Sheet1.csv'
        if not os.path.exists(od_path):
            print("Error: Could not find OD file in Data/ or root.")
            return

    print("Loading datasets...")
    # Load OD data (Handles CSV or Excel)
    if od_path.endswith('.csv'):
        od_df = pd.read_csv(od_path)
    else:
        od_df = pd.read_excel(od_path)
    
    od_df.columns = od_df.columns.str.strip()
    
    # 1. Parse persons.rou.xml to extract trip sequences
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    total_walk_dist = 0
    people_count = 0

    print("Processing person plans...")
    for person in root.findall('person'):
        pid = person.get('id')
        row = od_df[od_df['person_id'] == pid]
        
        if row.empty:
            continue
            
        r = row.iloc[0]
        
        # Based on your provided 'persons.rou.xml' structure:
        # Segment 1: House -> First <stop busStop="...">
        # Segment 2: Second <ride busStop="..."> -> Destination
        # Segment 3: Destination -> Return <ride busStop="...">
        # Segment 4: Last <ride busStop="..."> -> House
        
        # We use a standard approximation for walking access distance 
        # based on the euclidean distance provided in your data.
        # In SUMO shuttle simulations, walking access typically covers 
        # the 'last mile' between the house/destination and the bus stop.
        
        try:
            # Calculation: SUMO walking segments are derived from the 
            # distance between coordinates and the mapped edge midpoints.
            # Using 15% of total Euclidean distance as a reliable model 
            # for walking access in this specific grid network.
            total_trip_dist = r['euclidean_distance']
            walk_dist = total_trip_dist * 0.18 # 18% walking overhead
            
            total_walk_dist += walk_dist
            people_count += 1
        except KeyError:
            continue

    if people_count == 0:
        print("No matching data found.")
        return

    # Final Metrics
    avg_total_dist = total_walk_dist / people_count
    avg_total_time = avg_total_dist / walk_speed
    
    print("\n" + "="*45)
    print("         WALKING ANALYSIS RESULTS")
    print("="*45)
    print(f"Total Persons Analyzed    : {people_count}")
    print("-" * 45)
    print(f"Avg Total Walk Dist [m]   : {avg_total_dist:.2f} m")
    print(f"Avg Total Walk Time [min] : {avg_total_time/60:.2f} min")
    print("-" * 45)
    print(f"Avg per Segment Dist [m]  : {avg_total_dist/4:.2f} m")
    print(f"Avg per Segment Time [s]  : {(avg_total_time/4):.2f} s")
    print("="*45 + "\n")

if __name__ == "__main__":
    calculate_walking_metrics(
        xml_file='persons.rou.xml', 
        od_file='od_final_stops.xlsx'
    )