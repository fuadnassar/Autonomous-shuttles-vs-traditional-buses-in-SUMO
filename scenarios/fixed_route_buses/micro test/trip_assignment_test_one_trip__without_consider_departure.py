import os
import sys
import math
import sumolib

# Initialize SUMO tools
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    # Common Mac path if environment variable isn't set
    sys.path.append('/opt/homebrew/share/sumo/tools')
    sys.path.append('/usr/local/share/sumo/tools')

def get_dist(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

class PTAnalyzer:
    def __init__(self, net_file, stops_file, buses_file):
        print(f"Loading: {net_file}...")
        # Use absolute paths to prevent ValueError: unknown url type
        net_abs = os.path.abspath(net_file)
        
        self.net = sumolib.net.readNet(net_abs)
        self.bus_stops = list(sumolib.xml.parse(os.path.abspath(stops_file), 'busStop'))
        self.bus_trips = list(sumolib.xml.parse(os.path.abspath(buses_file), 'trip'))
        self.stop_coords = self._map_stop_coordinates()

    def _map_stop_coordinates(self):
        coords = {}
        for stop in self.bus_stops:
            lane_id = stop.lane
            edge_id = lane_id.rsplit('_', 1)[0]
            lane_idx = int(lane_id.rsplit('_', 1)[1])
            
            edge = self.net.getEdge(edge_id)
            lane = edge.getLanes()[lane_idx]
            
            mid_pos = (float(stop.startPos) + float(stop.endPos)) / 2
            coords[stop.id] = sumolib.geomhelper.positionAtShapeOffset(lane.getShape(), mid_pos)
        return coords

    def find_best_route(self, origin_xy, dest_xy, max_walk=600):
        near_origin = []
        near_dest = []

        for s_id, s_xy in self.stop_coords.items():
            d_to_origin = get_dist(origin_xy, s_xy)
            d_to_dest = get_dist(dest_xy, s_xy)

            if d_to_origin <= max_walk:
                near_origin.append({'id': s_id, 'dist': d_to_origin})
            if d_to_dest <= max_walk:
                near_dest.append({'id': s_id, 'dist': d_to_dest})

        if not near_origin:
            return "No bus stops found within walking radius of Origin."
        if not near_dest:
            return "No bus stops found within walking radius of Destination."

        possible_options = []
        for trip in self.bus_trips:
            trip_sequence = [s.busStop for s in trip.stop]
            
            for o_stop in near_origin:
                if o_stop['id'] in trip_sequence:
                    idx_o = trip_sequence.index(o_stop['id'])
                    for d_stop in near_dest:
                        if d_stop['id'] in trip_sequence:
                            idx_d = trip_sequence.index(d_stop['id'])
                            
                            if idx_o < idx_d:
                                total_walk = o_stop['dist'] + d_stop['dist']
                                num_stops = idx_d - idx_o
                                # Score: Low is better. Weighting walking heavily.
                                score = (total_walk * 1.5) + (num_stops * 30) 
                                
                                possible_options.append({
                                    'bus_id': trip.id,
                                    'bus_type': trip.type,
                                    'board_at': o_stop['id'],
                                    'exit_at': d_stop['id'],
                                    'walk_dist': round(total_walk, 2),
                                    'stops_count': num_stops,
                                    'score': score
                                })

        return sorted(possible_options, key=lambda x: x['score'])

# --- Execution ---
if __name__ == "__main__":
    # UPDATED FILENAMES based on your 'ls' output
    NET = "network.net.xml"
    STOPS = "stops.add.xml"
    BUSES = "buses.rou.xml"

    if not os.path.exists(NET):
        print(f"Error: {NET} not found in {os.getcwd()}")
        sys.exit()

    analyzer = PTAnalyzer(NET, STOPS, BUSES)

    # Example Coordinates - Adjust to your map
    origin = (-320.0, 115.0)
    dest = (210.0, -125.0)
    
    results = analyzer.find_best_route(origin_point, dest_point, max_walk=600)

    print("\n" + "="*70)
    if isinstance(results, str):
        print(results)
    else:
        print(f"Found {len(results)} possible connections:")
        print(f"{'Bus ID':<8} | {'Line Type':<18} | {'Board':<8} | {'Exit':<8} | {'Total Walk'}")
        print("-" * 70)
        for res in results[:5]: 
            print(f"{res['bus_id']:<8} | {res['bus_type']:<18} | {res['board_at']:<8} | {res['exit_at']:<8} | {res['walk_dist']}m")
    print("="*70)