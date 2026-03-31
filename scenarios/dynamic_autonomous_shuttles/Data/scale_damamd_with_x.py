import pandas as pd

def generate_busstop_routes(input_excel, output_xml, scale_factor=1):
    """
    Generates a SUMO routes file with a scaling factor.
    scale_factor = 1: Original demand.
    scale_factor = 2: Each person in Excel is duplicated.
    """
    try:
        df = pd.read_excel(input_excel)
    except FileNotFoundError:
        print(f"Error: The file '{input_excel}' was not found.")
        return

    # Counter for unique person IDs across the whole file
    global_person_count = 0

    with open(output_xml, 'w') as f:
        # Header
        f.write('<?xml version="1.0" ?>\n')
        f.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')

        for index, row in df.iterrows():
            try:
                # Extract Data
                depart_time = row['departure_time']
                activity_duration = row['activity_duration']
                origin = str(row['origin_selected_pickup']).strip()
                dest_drop = str(row['destination_selected_dropoff']).strip()
                dest_pick = str(row['destination_selected_pickup']).strip()
                origin_drop = str(row['origin_selected_dropoff']).strip()

                # --- Scaling Loop ---
                # This repeats the person block based on the scale_factor
                for _ in range(scale_factor):
                    # Generate a unique ID (t_0, t_1, t_2...)
                    unique_id = f"t_{global_person_count}"
                    
                    f.write(f'    <person id="{unique_id}" depart="{depart_time}">\n')
                    f.write(f'        <stop busStop="{origin}" duration="0"/>\n')
                    f.write(f'        <ride busStop="{dest_drop}" lines="taxi"/>\n')
                    f.write(f'        <stop busStop="{dest_drop}" duration="5"/>\n')
                    f.write(f'        <walk busStop="{dest_pick}"/>\n')
                    f.write(f'        <stop busStop="{dest_pick}" duration="{activity_duration}"/>\n')
                    f.write(f'        <ride busStop="{origin_drop}" lines="taxi"/>\n')
                    f.write(f'        <walk busStop="{origin}"/>\n')
                    f.write('    </person>\n')
                    
                    # Increment the counter so the next person gets a new ID
                    global_person_count += 1

            except KeyError as e:
                print(f"Error: Column {e} missing in row {index}.")
                continue

        # Footer
        f.write('</routes>')
    
    print(f"Successfully generated '{output_xml}' with scale factor {scale_factor}.")
    print(f"Total persons generated: {global_person_count}")

# Change this value to scale your demand (1, 2, 3, etc.)
scale_value = 5 

# --- Execution ---
input_file = 'od_final_stops.xlsx'
output_file = f'scalled_{scale_value}_person_plans.rou.xml'


generate_busstop_routes(input_file, output_file, scale_factor=scale_value)