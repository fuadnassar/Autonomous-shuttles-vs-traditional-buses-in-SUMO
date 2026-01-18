import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import os
from xml.dom import minidom

def generate_sumo_roundtrip_file(net_file, info_file, od_file, output_xml):
    print("Loading data...")
    info_df = pd.read_excel(info_file)
    od_df = pd.read_excel(od_file)
    
    # Merge to get all info: home edge, shop edge, shopping time, and coords
    data = info_df.merge(od_df[['id', 'destination_x', 'destination_y', 'shopping time']], on='id', how='left')

    # Parse network for arrival edges (closest edge to destination for dropoff)
    print("Parsing network for drop-off mapping...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    edges_data = []
    for edge in root.findall('edge'):
        eid = edge.get('id')
        if not eid or eid.startswith(':'): continue
        lane = edge.find('lane')
        if lane is not None and lane.get('shape'):
            coords = [tuple(map(float, p.split(','))) for p in lane.get('shape').split(' ')]
            edges_data.append({'id': eid, 'x': coords[len(coords)//2][0], 'y': coords[len(coords)//2][1]})
    edges_df = pd.DataFrame(edges_data)

    routes = ET.Element("routes")
    dest_cache = {}

    print("Generating XML Round Trips...")
    for _, row in data.iterrows():
        # Identify arrival edge at shopping center
        dest_coords = (row['destination_x'], row['destination_y'])
        if dest_coords not in dest_cache:
            dist = np.sqrt((edges_df['x'] - row['destination_x'])**2 + (edges_df['y'] - row['destination_y'])**2)
            dest_cache[dest_coords] = edges_df.loc[dist.idxmin(), 'id']
        
        shop_arrival_edge = dest_cache[dest_coords]
        
        person = ET.SubElement(routes, "person", {
            "id": str(row['id']),
            "depart": str(round(row['departure_time'], 2)),
            "departPos": "0.0"
        })
        
        # 1. RIDE TO SHOPPING
        ET.SubElement(person, "ride", {
            "from": str(row['edge_home_to_shop']),
            "to": shop_arrival_edge,
            "lines": "taxi"
        })

        # 2. SHOPPING ACTIVITY (The Stop)
        # Person waits at the shop arrival edge for the 'shopping time' duration
        ET.SubElement(person, "stop", {
            "lane": f"{shop_arrival_edge}_0",
            "duration": str(row['shopping time'])
        })

        # 3. RIDE BACK HOME
        # Pickup at the directional 'shop_to_home' edge, dropoff at the 'home_to_shop' edge
        ET.SubElement(person, "ride", {
            "from": str(row['edge_shop_to_home']),
            "to": str(row['edge_home_to_shop']),
            "lines": "taxi"
        })

    print("Writing XML...")
    xml_str = ET.tostring(routes, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")
    with open(output_xml, "w", encoding='utf-8') as f:
        f.write(pretty_xml)
    print(f"Success! Created {output_xml} with full round trips.")

generate_sumo_roundtrip_file('../network.net.xml', 'Home_shopping_person_info_updated.xlsx', 'od.xlsx', 'persons.rou.xml')