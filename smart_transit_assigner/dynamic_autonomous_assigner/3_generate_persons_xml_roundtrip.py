import pandas as pd

def generate_busstop_routes(input_excel, output_xml):
    # 1. Load the Excel file
    try:
        df = pd.read_excel(input_excel)
    except FileNotFoundError:
        print(f"Error: The file '{input_excel}' was not found.")
        return

    # 2. Pandas Logic: Calculate and Sort
    try:
        # Calculate the new times
        df['first_station_arrival_time'] = (df['departure_time'] + df['start_walk_time']).astype(int)
        df['calc_activity_duration'] = (df['activity_duration'] + (2 * df['end_walk_time'])).astype(int)
        
        # Sort the DataFrame by the first_station_arrival_time (lowest to highest)
        df = df.sort_values(by='first_station_arrival_time', ascending=True).reset_index(drop=True)
        
    except KeyError as e:
        print(f"Error: Missing column needed for calculations: {e}. Please check your Excel headers.")
        return

    # 3. Write to XML
    with open(output_xml, 'w') as f:
        # Header
        f.write('<?xml version="1.0" ?>\n')
        f.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')

        # Iterate through the newly sorted dataframe
        for index, row in df.iterrows():
            try:
                # --- NEW ID LOGIC ---
                # Get the original ID (e.g., "t_0")
                original_id = str(row['person_id'])
                
                # Split by '_' and take the last part to get just the number
                # "t_0" becomes ["t", "0"], and [-1] grabs the "0"
                id_number = original_id.split('_')[-1] 
                
                # Create the new ID format
                new_person_id = f"a_s_{id_number}"
                
                # Extract our pre-calculated, sorted integers
                depart_time = row['first_station_arrival_time']
                activity_duration = row['calc_activity_duration']

                # Get the Stop IDs
                origin = str(row['origin_selected_pickup']).strip()
                dest_drop = str(row['destination_selected_dropoff']).strip()
                dest_pick = str(row['destination_selected_pickup']).strip()
                origin_drop = str(row['origin_selected_dropoff']).strip()

                # Write Person Block with the extracted ID number and sorted depart time
                f.write(f'    <person id="{new_person_id}" depart="{depart_time}">\n')

                # Step 1: Spawn at Origin Stop
                f.write(f'        <stop busStop="{origin}" duration="0"/>\n')

                # Step 2: Ride to Destination Dropoff
                f.write(f'        <ride busStop="{dest_drop}" lines="taxi"/>\n')

                # Step 3: Wait 5 seconds before crossing street
                f.write(f'        <stop busStop="{dest_drop}" duration="5"/>\n')

                # Step 4: Walk to Destination Pickup
                f.write(f'        <walk busStop="{dest_pick}"/>\n')

                # Step 5: Activity at Destination Pickup
                f.write(f'        <stop busStop="{dest_pick}" duration="{activity_duration}"/>\n')

                # Step 6: Ride back to Home area
                f.write(f'        <ride busStop="{origin_drop}" lines="taxi"/>\n')

                # Step 7: Walk back to original start
                f.write(f'        <walk busStop="{origin}"/>\n')

                f.write('    </person>\n')

            except KeyError as e:
                print(f"Error: Column {e} missing in row {index}.")
                continue

        # Footer
        f.write('</routes>\n')
    
    print(f"Successfully generated '{output_xml}' with sorted times and updated 'a_s_' IDs.")

# --- Execution ---
input_file = 'new_table.xlsx'
output_file = 'persons.rou.xml'

generate_busstop_routes(input_file, output_file)