import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os

def get_angle(x1, y1, x2, y2):
    return np.arctan2(y2 - y1, x2 - x1)

def find_best_directional_edge(ox, oy, dx, dy, edges_df):
    """Finds the best edge near (ox, oy) that points toward (dx, dy)"""
    trip_angle = get_angle(ox, oy, dx, dy)
    distances = np.sqrt((edges_df['x'] - ox)**2 + (edges_df['y'] - oy)**2)
    
    # Take 5 closest edges
    candidates_idx = distances.nsmallest(5).index
    candidates = edges_df.loc[candidates_idx].copy()
    
    # Find the one with the smallest angle difference
    candidates['angle_diff'] = np.abs(np.arctan2(np.sin(candidates['angle'] - trip_angle), 
                                               np.cos(candidates['angle'] - trip_angle)))
    
    return candidates.sort_values('angle_diff').iloc[0]['edge_id']

def assign_roundtrip_edges(net_file, od_file, info_file, output_file):
    if not all(os.path.exists(f) for f in [net_file, od_file, info_file]):
        print("Error: Files missing.")
        return

    print("Parsing network...")
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
    od_df = pd.read_excel(od_file)
    info_df = pd.read_excel(info_file)

    print("Calculating directional edges for round trips...")
    results = []
    for _, row in od_df.iterrows():
        hx, hy = row['origin_x'], row['origin_y']
        sx, sy = row['destination_x'], row['destination_y']
        
        # Best edge at home for the trip TO the shop
        home_to_shop = find_best_directional_edge(hx, hy, sx, sy, edges_df)
        
        # Best edge at shop for the trip BACK home
        shop_to_home = find_best_directional_edge(sx, sy, hx, hy, edges_df)
        
        results.append({
            'id': row['id'], 
            'edge_home_to_shop': home_to_shop, 
            'edge_shop_to_home': shop_to_home
        })

    mapping_df = pd.DataFrame(results)
    updated_info = info_df.merge(mapping_df, on='id', how='left')
    updated_info.to_excel(output_file, index=False)
    print(f"Success! Optimized round-trip edges saved to: {output_file}")

assign_roundtrip_edges('../network.net.xml', 'od.xlsx', 'Home_shopping_person_info.xlsx', 'Home_shopping_person_info_updated.xlsx')