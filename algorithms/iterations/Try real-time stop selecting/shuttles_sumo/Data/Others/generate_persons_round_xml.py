import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os
from xml.dom import minidom

def get_angle(x1, y1, x2, y2):
    """Calculates the angle of the vector (x1,y1) -> (x2,y2)"""
    return np.arctan2(y2 - y1, x2 - x1)

def find_best_edge(ox, oy, dx, dy, edges_df):
    """Finds the edge closest to (ox, oy) that points toward (dx, dy)"""
    trip_angle = get_angle(ox, oy, dx, dy)
    distances = np.sqrt((edges_df['x'] - ox)**2 + (edges_df['y'] - oy)**2)
    
    # Filter to 5 physically closest edges
    candidates_idx = distances.nsmallest(5).index
    candidates = edges_df.loc[candidates_idx].copy()
    
    # Choose the one that aligns best with the destination direction
    candidates['angle_diff'] = np.abs(np.arctan2(np.sin(candidates['angle'] - trip_angle), 
                                               np.cos(candidates['angle'] - trip_angle)))
    return candidates.sort_values('angle_diff').iloc[0]['id']

def generate_round_trips(net_file, info_file, od_file, output_xml):
    print("Loading files and parsing network...")
    # Loading your data
    info_df = pd.read_excel(info_file)
    od_df = pd.read_excel(od_file)
    
    # 1. Parse Network to get edge positions and angles
    tree = ET.parse(net_file)
    root = tree.getroot()
    edges_data = []
    for edge in root.findall('edge'):
        eid = edge.get('id')
        if not eid or eid.startswith(':'): continue
        lane = edge.find('lane')
        if lane is not None:
            shape = lane.get('shape').split(' ')
            p1 = [float(c) for c in shape[0].split(',')]
            p2 = [float(c) for c in shape[-1].split(',')]
            mid = [float(c) for c in shape[len(shape)//2].split(',')]
            edges_data.append({
                'id': eid, 'x': mid[0], 'y': mid[1], 
                'angle': get_angle(p1[0], p1[1], p2[0], p2[1])
            })
    edges_df = pd.DataFrame(edges_data)

    # 2. Create the XML Structure
    routes = ET.Element("routes")
    routes.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    routes.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/routes_file.xsd")
    
    print("Processing trips...")
    for _, row in od_df.iterrows():
        hx, hy = row['origin_x'], row['origin_y'] # Home
        sx, sy = row['destination_x'], row['destination_y'] # Shop
        
        # FIND THE BEST EDGES
        # Since roads are two-way, the "Home" edge for exit is the best for entry.
        # The "Shop" edge for entry is the best for exit.
        edge_home = find_best_edge(hx, hy, sx, sy, edges_df)
        edge_shop = find_best_edge(sx, sy, hx, hy, edges_df)

        # Get departure time from your info file
        dep_time = info_df.loc[info_df['id'] == row['id'], 'departure_time'].values[0]

        person = ET.SubElement(routes, "person", {
            "id": str(row['id']),
            "depart": str(round(float(dep_time), 2))
        })
        
        # --- TRIP 1: HOME TO SHOPPING ---
        ET.SubElement(person, "ride", {
            "from": edge_home, 
            "to": edge_shop, 
            "lines": "taxi"
        })
        
        # --- STOP: SHOPPING DURATION ---
        ET.SubElement(person, "stop", {
            "lane": f"{edge_shop}_0", 
            "duration": str(row['shopping time'])
        })
        
        # --- TRIP 2: SHOPPING BACK HOME ---
        ET.SubElement(person, "ride", {
            "from": edge_shop, 
            "to": edge_home, 
            "lines": "taxi"
        })

    # 3. Save Final XML
    xml_str = ET.tostring(routes, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")
    with open(output_xml, "w", encoding='utf-8') as f:
        f.write(pretty_xml)
        
    print(f"Done! Created {output_xml} with 1,548 Round Trips.")

# Run the process
generate_round_trips(
    '../network.net.xml', 
    'Home_shopping_person_info_updated.xlsx', 
    'od.xlsx', 
    'persons.rou.xml'
)