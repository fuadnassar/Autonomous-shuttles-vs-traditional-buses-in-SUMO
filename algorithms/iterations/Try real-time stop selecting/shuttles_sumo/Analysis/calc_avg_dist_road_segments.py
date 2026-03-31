import sumolib
import os

def calculate_clean_average_distance(net_file):
    print(f"Loading network: {net_file}...")
    net = sumolib.net.readNet(net_file)
    
    lengths = []
    seen_base_ids = set()

    for edge in net.getEdges():
        edge_id = edge.getID()
        length = edge.getLength()
        
        # 1. Strip direction markers to find the "base" road ID
        # Many SUMO networks use '-ID' or 'ID#0' for directions/segments
        base_id = edge_id.replace('-', '')
        
        # 2. Filter: Only include if length >= 100 and we haven't counted this road yet
        if length >= 100 and base_id not in seen_base_ids:
            lengths.append(length)
            seen_base_ids.add(base_id)

    if not lengths:
        print("No unique edges found with length >= 100m.")
        return 0, 0

    avg_distance = sum(lengths) / len(lengths)
    return avg_distance, len(lengths)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    net_path = os.path.join(script_dir, "..", "network.net.xml")
    
    if not os.path.exists(net_path):
        print(f"Error: Could not find file at {net_path}")
    else:
        avg_dist, count = calculate_clean_average_distance(net_path)
        
        print("-" * 30)
        print(f"Average Road Distance (Unique Edges >= 100m): {avg_dist:.2f} meters")
        print(f"Total Unique Road Segments: {count}")