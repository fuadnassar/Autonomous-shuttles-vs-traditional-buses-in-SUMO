import os
import sys
import math
import pandas as pd
import sumolib
from pathlib import Path

# --- CORE UTILITIES ---
def get_dist(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.path.append('/usr/local/share/sumo/tools')

class PTAnalyzer:
    def __init__(self, net_file, stops_file, buses_file):
        print(f"Loading files...")
        net_abs = os.path.abspath(net_file)
        net_uri = Path(net_abs).resolve().as_uri()
        self.net = sumolib.net.readNet(net_uri)
        self.bus_stops = list(sumolib.xml.parse(os.path.abspath(stops_file), 'busStop'))
        self.bus_trips = list(sumolib.xml.parse(os.path.abspath(buses_file), 'trip'))
        self.stop_coords = self._map_stop_coordinates()
        self.WALK_SPEED = 1.1  

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

    def find_best_route(self, origin_xy, dest_xy, person_depart, max_walk=600):
        near_origin, near_dest = [], []
        for s_id, s_xy in self.stop_coords.items():
            d_o, d_d = get_dist(origin_xy, s_xy), get_dist(dest_xy, s_xy)
            if d_o <= max_walk: near_origin.append({'id': s_id, 'dist': d_o})
            if d_d <= max_walk: near_dest.append({'id': s_id, 'dist': d_d})

        possible_options = []
        for trip in self.bus_trips:
            trip_schedule = {s.busStop: (float(s.until), float(s.duration)) for s in trip.stop}
            trip_stop_ids = [s.busStop for s in trip.stop]
            for o_stop in near_origin:
                if o_stop['id'] in trip_schedule:
                    bus_depart_stop = trip_schedule[o_stop['id']][0]
                    w1_dist = o_stop['dist']
                    w1_s = w1_dist / self.WALK_SPEED
                    person_reaches_stop = person_depart + w1_s
                    if person_reaches_stop > bus_depart_stop: continue 

                    for d_stop in near_dest:
                        if d_stop['id'] in trip_schedule:
                            idx_o, idx_d = trip_stop_ids.index(o_stop['id']), trip_stop_ids.index(d_stop['id'])
                            if idx_o < idx_d:
                                bus_until_dest, bus_dur_dest = trip_schedule[d_stop['id']]
                                bus_arrival_dest = bus_until_dest - bus_dur_dest
                                w2_dist = d_stop['dist']
                                w2_s = w2_dist / self.WALK_SPEED
                                total_time_s = w1_s + (bus_depart_stop - person_reaches_stop) + (bus_arrival_dest - bus_depart_stop) + w2_s
                                possible_options.append({
                                    'bus_id': trip.id, 'line': trip.type, 'board': o_stop['id'], 'exit': d_stop['id'],
                                    'w1_dist': round(w1_dist, 1), 'w1_s': int(w1_s), 'arrival_at_stop': int(person_reaches_stop),
                                    'bus_depart_stop': int(bus_depart_stop), 'bus_arrival_dest': int(bus_arrival_dest),
                                    'w2_dist': round(w2_dist, 1), 'w2_s': int(w2_s), 'rank_score': total_time_s + (w1_dist * 0.5)
                                })
        return sorted(possible_options, key=lambda x: x['rank_score'])

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent
    # Go up 2 levels (Step_1 -> Data -> buses_sumo) to find network files
    PROJECT_ROOT = SCRIPT_DIR.parent.parent 
    NET, STOPS, BUSES = str(PROJECT_ROOT/"network.net.xml"), str(PROJECT_ROOT/"stops.add.xml"), str(PROJECT_ROOT/"buses.rou.xml")
    
    # Input file is in the same folder as the script (Data/Step_1)
    INPUT_FILE = str(SCRIPT_DIR / "personal_planes_from_4_step_model.xlsx")

    analyzer = PTAnalyzer(NET, STOPS, BUSES)
    df = pd.read_excel(INPUT_FILE)
    
    outbound_rows, return_rows, od_rows = [], [], []

    for idx, row in df.iterrows():
        trip_id = f"t_{idx}"
        home_xy = (row['origin_x'], row['origin_y'])
        shop_xy = (row['destination_x'], row['destination_y'])
        shop_duration = row.get('shopper agent', row.get('shopping time', 0))
        
        # 1. GENERATE OUTBOUND (Home -> Shopping)
        out_best = analyzer.find_best_route(home_xy, shop_xy, person_depart=row['home_departure_time'])
        best_o = out_best[0] if out_best else None
        
        outbound_rows.append({
            'id': trip_id, 'departure_time': row['home_departure_time'],
            'bus_line_selected': best_o['line'] if best_o else 'No Route',
            'bus_id_selected': best_o['bus_id'] if best_o else 'No Route',
            'start_stop_selected': best_o['board'] if best_o else 'N/A',
            'start_walk_distance': best_o['w1_dist'] if best_o else 0,
            'start_walk_time': best_o['w1_s'] if best_o else 0,
            'person_arrival_start_stop': best_o['arrival_at_stop'] if best_o else 0,
            'bus_arrival_start_stop': best_o['bus_depart_stop'] if best_o else 0,
            'last_stop_selected': best_o['exit'] if best_o else 'N/A',
            'bus_arrival_last_stop': best_o['bus_arrival_dest'] if best_o else 0,
            'end_walk_distance': best_o['w2_dist'] if best_o else 0,
            'end_walk_time': best_o['w2_s'] if best_o else 0
        })

        # 2. GENERATE RETURN (Shopping -> Home)
        # Logic: Start at Shopping Dest, End at Home Origin
        # Departure = bus_arrival_last_stop + end_walk_time + shopping time
        if best_o:
            return_depart = best_o['bus_arrival_dest'] + best_o['w2_s'] + shop_duration
            ret_best = analyzer.find_best_route(shop_xy, home_xy, person_depart=return_depart)
            best_r = ret_best[0] if ret_best else None
            
            return_rows.append({
                'id': trip_id, 'departure_time': return_depart,
                'bus_line_selected': best_r['line'] if best_r else 'No Route',
                'bus_id_selected': best_r['bus_id'] if best_r else 'No Route',
                'start_stop_selected': best_r['board'] if best_r else 'N/A',
                'start_walk_distance': best_r['w1_dist'] if best_r else 0,
                'start_walk_time': best_r['w1_s'] if best_r else 0,
                'person_arrival_start_stop': best_r['arrival_at_stop'] if best_r else 0,
                'bus_arrival_start_stop': best_r['bus_depart_stop'] if best_r else 0,
                'last_stop_selected': best_r['exit'] if best_r else 'N/A',
                'bus_arrival_last_stop': best_r['bus_arrival_dest'] if best_r else 0,
                'end_walk_distance': best_r['w2_dist'] if best_r else 0,
                'end_walk_time': best_r['w2_s'] if best_r else 0
            })

        # 3. OD DATA
        od_rows.append({
            'id': trip_id, 'name_origin': row['name_block'],
            'origin_x': row['origin_x'], 'origin_y': row['origin_y'],
            'name_destination': row.get('name_destination', f"t_{idx}"),
            'destination_x': row['destination_x'], 'destination_y': row['destination_y'],
            'shopping time': shop_duration
        })

# Save files into the 'results' subfolder
    pd.DataFrame(outbound_rows).to_excel(SCRIPT_DIR / "results/Home_shopping_person_info.xlsx", index=False)
    pd.DataFrame(return_rows).to_excel(SCRIPT_DIR / "results/Shopping_home_person_info.xlsx", index=False)
    pd.DataFrame(od_rows).to_excel(SCRIPT_DIR / "results/od.xlsx", index=False)
    
    print(f"Success! Generated 3 files in {SCRIPT_DIR}")