import pandas as pd
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

def generate_sumo_persons_separated():
    # 1. Setup Paths
    SCRIPT_DIR = Path(__file__).resolve().parent
    HOME_SHOP_FILE = SCRIPT_DIR / "results_from_step_1/Home_shopping_person_info.xlsx"
    SHOP_HOME_FILE = SCRIPT_DIR / "results_from_step_1/Shopping_home_person_info.xlsx"
    OUTPUT_FILE = SCRIPT_DIR / "results/persons.rou.xml"

    # 2. Load the data
    print("Loading Excel files...")
    df_out = pd.read_excel(HOME_SHOP_FILE)
    df_ret = pd.read_excel(SHOP_HOME_FILE)

    # 3. Create XML Structure
    routes = ET.Element('routes')
    routes.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    routes.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

    # 4. Process each trip
    count = 1
    for idx, row_out in df_out.iterrows():
        pid = str(row_out['id'])
        
        # --- PERSON OUTBOUND (Home -> Shop) ---
        if row_out['bus_id_selected'] != 'No Route':
            p_out = ET.SubElement(routes, 'person', {
                'id': f"p_{pid}_out",
                'depart': str(row_out['departure_time'])
            })
            # Start at the boarding stop
            ET.SubElement(p_out, 'stop', {'busStop': str(row_out['start_stop_selected']), 'duration': '0.10'})
            # Ride to the destination stop
            ET.SubElement(p_out, 'ride', {'busStop': str(row_out['last_stop_selected']), 'lines': str(row_out['bus_id_selected'])})
            count += 1

        # --- PERSON RETURN (Shop -> Home) ---
        row_ret_match = df_ret[df_ret['id'] == pid]
        if not row_ret_match.empty:
            row_ret = row_ret_match.iloc[0]
            if row_ret['bus_id_selected'] != 'No Route':
                p_ret = ET.SubElement(routes, 'person', {
                    'id': f"p_{pid}_ret",
                    'depart': str(row_ret['departure_time'])
                })
                # Start at the shopping bus stop
                ET.SubElement(p_ret, 'stop', {'busStop': str(row_ret['start_stop_selected']), 'duration': '0.10'})
                # Ride back to the home bus stop
                ET.SubElement(p_ret, 'ride', {'busStop': str(row_ret['last_stop_selected']), 'lines': str(row_ret['bus_id_selected'])})
                count += 1

    # 5. Save
    xml_string = ET.tostring(routes, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="    ")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Success! Generated {count} person-trips in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_sumo_persons_separated()