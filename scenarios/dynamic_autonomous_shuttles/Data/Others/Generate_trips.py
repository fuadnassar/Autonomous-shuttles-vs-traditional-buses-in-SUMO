import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os

def get_angle(x1, y1, x2, y2):
    """Calculates the angle of the vector (x1,y1) -> (x2,y2)"""
    return np.arctan2(y2 - y1, x2 - x1)

def assign_directional_edge(net_file, od_file, info_file, output_file):
    if not all(os.path.exists(f) for f in [net_file, od_file, info_file]):
        print("Error: One or more input files are missing.")
        return

    # 1. Parse network and calculate edge directions
    print("Parsing network and calculating edge directions...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    edges_data = []
    
    for edge in root.findall('edge'):
        edge_id = edge.get('id')
        if not edge_id or edge_id.startswith(':'): continue
            
        lane = edge.find('lane')
        if lane is not None:
            shape = lane.get('shape')
            if shape:
                coords = [tuple(map(float, p.split(','))) for p in shape.split(' ')]
                p1, p2 = coords[0], coords[-1] # Start and End of the road
                midpoint = coords[len(coords) // 2]
                
                # Calculate the angle of the road itself
                edge_angle = get_angle(p1[0], p1[1], p2[0], p2[1])
                
                edges_data.append({
                    'edge_id': edge_id, 
                    'x': midpoint[0], 'y': midpoint[1], 
                    'angle': edge_angle
                })
                
    edges_df = pd.DataFrame(edges_data)

    # 2. Load Data
    od_df = pd.read_excel(od_file)
    info_df = pd.read_excel(info_file)

    # 3. Direction-Aware Assignment
    print("Assigning edges based on distance AND destination direction...")
    results = []
    for _, row in od_df.iterrows():
        ox, oy = row['origin_x'], row['origin_y']
        dx, dy = row['destination_x'], row['destination_y']
        
        # Angle of the trip (Origin -> Destination)
        trip_angle = get_angle(ox, oy, dx, dy)
        
        # Calculate distances to all edges
        distances = np.sqrt((edges_df['x'] - ox)**2 + (edges_df['y'] - oy)**2)
        
        # Get 5 closest edges as candidates
        candidates_idx = distances.nsmallest(5).index
        candidates = edges_df.loc[candidates_idx].copy()
        
        # Calculate difference between trip angle and edge angle
        # We want the edge whose direction is closest to the trip direction
        candidates['angle_diff'] = np.abs(np.arctan2(np.sin(candidates['angle'] - trip_angle), 
                                                   np.cos(candidates['angle'] - trip_angle)))
        
        # Pick the candidate with the best direction among the closest ones
        best_edge_id = candidates.sort_values('angle_diff').iloc[0]['edge_id']
        
        results.append({'id': row['id'], 'edge_selected': best_edge_id})

    # 4. Save
    mapping_df = pd.DataFrame(results)
    updated_info = info_df.merge(mapping_df, on='id', how='left')
    updated_info.to_excel(output_file, index=False)
    print(f"Success! Optimized file saved to: {output_file}")


# Run from Data folder
assign_directional_edge(
    net_file='../network.net.xml', 
    od_file='od.xlsx', 
    info_file='Home_shopping_person_info.xlsx', 
    output_file='Home_shopping_person_info_updated.xlsx'
)