import xml.etree.ElementTree as ET

def clean_sumo_network(input_file, output_file):
    print(f"Reading {input_file}...")
    tree = ET.parse(input_file)
    root = tree.getroot()
    
    changed_count = 0
    
    # Loop through every single lane in the network
    for lane in root.iter('lane'):
        current_speed_str = lane.get('speed')
        
        if current_speed_str:
            current_speed = float(current_speed_str)
            
            # If the speed is greater than 20 m/s (72 km/h), it's likely an uncorrected km/h value
            if current_speed > 20.0:
                # Convert km/h to m/s
                corrected_speed = current_speed / 3.6
                
                # Update the XML attribute, formatted to 2 decimal places
                lane.set('speed', f"{corrected_speed:.2f}")
                changed_count += 1
                
    # Save the corrected network
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    print(f"Successfully fixed {changed_count} incorrect speeds!")
    print(f"Saved cleaned network to: {output_file}")

if __name__ == "__main__":
    # Ensure your file is named network.net.xml
    clean_sumo_network("network.net.xml", "network_fixed.net.xml")