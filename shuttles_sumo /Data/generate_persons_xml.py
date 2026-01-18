import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os
from xml.dom import minidom

def generate_sumo_person_file(net_file, info_file, od_file, output_xml):
    # 1. Load the data
    print("Loading data files...")
    if not os.path.exists(info_file):
        print(f"Error: {info_file} not found!")
        return

    info_df = pd.read_excel(info_file)
    od_df = pd.read_excel(od_file)
    
    # Clean column names
    info_df.columns = info_df.columns.str.strip()
    od_df.columns = od_df.columns.str.strip()

    # Use the column you identified: 'edge_selected_y'
    target_col = 'edge_selected_y'
    
    if target_col not in info_df.columns:
        print(f"Error: {target_col} column missing in {info_file}")
        print(f"Available columns: {list(info_df.columns)}")
        return

    # Merge to get id, departure_time, edge_selected_y, and destination coordinates
    data = info_df.merge(od_df[['id', 'destination_x', 'destination_y']], on='id', how='left')

    # 2. Parse network to find destination edges
    print("Parsing network for destination mapping...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    edges_data = []
    for edge in root.findall('edge'):
        eid = edge.get('id')
        if not eid or eid.startswith(':'): continue
        lane = edge.find('lane')
        if lane is not None:
            shape = lane.get('shape')
            if shape:
                coords = [tuple(map(float, p.split(','))) for p in shape.split(' ')]
                midpoint = coords[len(coords) // 2]
                edges_data.append({'id': eid, 'x': midpoint[0], 'y': midpoint[1]})
    
    edges_df = pd.DataFrame(edges_data)

    # 3. Build XML
    routes = ET.Element("routes")
    routes.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    routes.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/routes_file.xsd")

    dest_cache = {}

    print("Generating XML entries...")
    for _, row in data.iterrows():
        # Find destination edge
        dest_coords = (row['destination_x'], row['destination_y'])
        if dest_coords not in dest_cache:
            dist = np.sqrt((edges_df['x'] - row['destination_x'])**2 + (edges_df['y'] - row['destination_y'])**2)
            dest_cache[dest_coords] = edges_df.loc[dist.idxmin(), 'id']
        
        dest_edge = dest_cache[dest_coords]

        # Create Person element
        person = ET.SubElement(routes, "person", {
            "id": str(row['id']),
            "depart": str(round(row['departure_time'], 2)),
            "departPos": "0.0"
        })
        
        # Create Ride element using the edge_selected_y column
        ET.SubElement(person, "ride", {
            "from": str(row[target_col]),
            "to": str(dest_edge),
            "lines": "taxi"
        })

    # 4. Save with pretty formatting
    print("Writing XML file...")
    xml_str = ET.tostring(routes, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")
    
    with open(output_xml, "w", encoding='utf-8') as f:
        f.write(pretty_xml)
        
    print(f"Success! Created {output_xml}")

# Execute
generate_sumo_person_file(
    net_file='../network.net.xml',
    info_file='Home_shopping_person_info_updated.xlsx',
    od_file='od.xlsx',
    output_xml='persons.rou.xml'
)