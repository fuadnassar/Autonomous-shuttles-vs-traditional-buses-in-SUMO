import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os

def get_angle(x1, y1, x2, y2):
    """Calculates the bearing angle in radians."""
    return np.arctan2(y2 - y1, x2 - x1)

def find_best_directional_edge(ox, oy, dx, dy, edges_df):
    """Finds the best edge near (ox, oy) that points toward (dx, dy)."""
    trip_angle = get_angle(ox, oy, dx, dy)
    distances = np.sqrt((edges_df['x'] - ox)**2 + (edges_df['y'] - oy)**2)
    
    # Take 10 closest edges
    candidates_idx = distances.nsmallest(10).index
    candidates = edges_df.loc[candidates_idx].copy()
    
    # Find the one with the smallest angle difference
    candidates['angle_diff'] = np.abs(np.remainder(candidates['angle'] - trip_angle + np.pi, 2 * np.pi) - np.pi)
    
    return candidates.sort_values('angle_diff').iloc[0]['edge_id']

def process_personal_plans(net_file, input_excel, output_file):
    if not os.path.exists(net_file):
        print(f"Error: Network file not found at {net_file}")
        return
    if not os.path.exists(input_excel):
        print(f"Error: Input file {input_excel} not found.")
        return

    # --- Step 1: Parse the SUMO Network ---
    print("Parsing SUMO network edges...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    edges_data = []
    
    for edge in root.findall('edge'):
        eid = edge.get('id')
        if not eid or eid.startswith(':'): continue
        
        lane = edge.find('lane')
        if lane is not None and lane.get('shape'):
            coords = [tuple(map(float, p.split(','))) for p in lane.get('shape').split(' ')]
            edge_angle = get_angle(coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
            mid = coords[len(coords) // 2]
            edges_data.append({'edge_id': eid, 'x': mid[0], 'y': mid[1], 'angle': edge_angle})
                
    edges_df = pd.DataFrame(edges_data)

    # --- Step 2: Load the Excel File ---
    print(f"Loading {input_excel}...")
    df = pd.read_excel(input_excel) 
    df.columns = df.columns.str.strip() # Remove any hidden spaces

    # --- Step 3: Directional Edge Assignment ---
    print("Mapping coordinates to best directional edges...")
    
    results_to_dest = []
    results_back_home = []

    for index, row in df.iterrows():
        try:
            # UPDATED HEADERS to match your file exactly:
            hx, hy = row['house_x'], row['house_y']
            dx, dy = row['destination_x'], row['destination_y']
            
            # Leg 1: House -> Destination
            edge_to = find_best_directional_edge(hx, hy, dx, dy, edges_df)
            results_to_dest.append(edge_to)
            
            # Leg 2: Destination -> House
            edge_back = find_best_directional_edge(dx, dy, hx, hy, edges_df)
            results_back_home.append(edge_back)
        except KeyError as e:
            print(f"Error at row {index}: Column {e} not found. Check your Excel headers!")
            return

    # --- Step 4: Save Output ---
    df['edge_id_to_destination'] = results_to_dest
    df['edge_id_back_home'] = results_back_home
    
    df.to_excel(output_file, index=False)
    print(f"Success! Final mapping saved to: {output_file}")

# --- SETTINGS ---
process_personal_plans(
    net_file='../network.net.xml', 
    input_excel='personal_planes.xlsx', 
    output_file='Final_Person_Network_Mapping.xlsx'
)