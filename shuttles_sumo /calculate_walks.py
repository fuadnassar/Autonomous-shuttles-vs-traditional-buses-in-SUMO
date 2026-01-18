import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os

def calculate_walking_metrics(xml_file, net_file, od_file, walk_speed=1.1):
    # Check if files exist before starting
    for f in [xml_file, net_file, od_file]:
        if not os.path.exists(f):
            print(f"Error: File not found -> {f}")
            return

    print("Loading data and parsing files...")
    # 1. Load OD Coordinates
    od_df = pd.read_excel(od_file)
    od_df.columns = od_df.columns.str.strip()
    
    # 2. Parse Network to get Edge Midpoints
    tree_net = ET.parse(net_file)
    root_net = tree_net.getroot()
    edge_coords = {}
    for edge in root_net.findall('edge'):
        eid = edge.get('id')
        lane = edge.find('lane')
        if lane is not None and lane.get('shape'):
            shape = lane.get('shape').split(' ')
            # Use midpoint of the shape for coordinate mapping
            mid = shape[len(shape)//2].split(',')
            edge_coords[eid] = (float(mid[0]), float(mid[1]))

    # 3. Parse persons.rou.xml
    tree_xml = ET.parse(xml_file)
    root_xml = tree_xml.getroot()
    
    total_walk_dist = 0
    total_people_processed = 0

    print("Calculating distances...")
    for person in root_xml.findall('person'):
        pid = person.get('id')
        rides = person.findall('ride')
        
        # We need at least 2 rides (Round Trip) to calculate 4 walk segments
        if len(rides) < 2:
            continue

        # Get coordinates from OD file for this person
        row = od_df[od_df['id'] == pid]
        if row.empty:
            continue
        
        orig_xy = (row.iloc[0]['origin_x'], row.iloc[0]['origin_y'])
        dest_xy = (row.iloc[0]['destination_x'], row.iloc[0]['destination_y'])

        # Stage 1: Home -> First Pickup Edge (Origin -> Start Edge)
        e1 = rides[0].get('from')
        # Stage 2: First Drop-off Edge -> Shop (End Edge -> Destination)
        e2 = rides[0].get('to')
  

        person_dist = 0
        valid_segments = 0

        for start_coord, edge_id in [(orig_xy, e1), (dest_xy, e2)]:
            if edge_id in edge_coords:
                dist = np.sqrt((start_coord[0] - edge_coords[edge_id][0])**2 + 
                               (start_coord[1] - edge_coords[edge_id][1])**2)
                person_dist += dist
                valid_segments += 1
        
        if valid_segments > 0:
            total_walk_dist += person_dist
            total_people_processed += 1

    # 4. Final Calculations
    if total_people_processed == 0:
        print("No valid person trips found to analyze.")
        return

    # Average distance a person walks in their ENTIRE day (all 4 segments)
    avg_total_dist_per_person = total_walk_dist / total_people_processed
    avg_total_time_per_person = avg_total_dist_per_person / walk_speed

    # Average per single walk segment (distance to/from one taxi)
    avg_dist_per_segment = total_walk_dist / (total_people_processed * 4)
    avg_time_per_segment = avg_dist_per_segment / walk_speed

    print("\n" + "="*40)
    print("       WALKING ANALYSIS RESULTS")
    print("="*40)
    print(f"Total Persons Analyzed    : {total_people_processed}")
    print("-" * 40)
    print(f"Avg Total Walk Dist [m]   : {avg_total_dist_per_person:.2f}")
    print(f"Avg Total Walk Time [s]   : {avg_total_time_per_person:.2f}")
    print("-" * 40)
    print(f"Avg per Segment Dist [m]  : {avg_dist_per_segment:.2f}")
    print(f"Avg per Segment Time [s]  : {avg_time_per_segment:.2f}")
    print("="*40 + "\n")

# RUN COMMAND: Ensure you are in the Arts_in_sumo folder
calculate_walking_metrics(
    xml_file='persons.rou.xml', 
    net_file='network.net.xml', 
    od_file='Data/od.xlsx'
)