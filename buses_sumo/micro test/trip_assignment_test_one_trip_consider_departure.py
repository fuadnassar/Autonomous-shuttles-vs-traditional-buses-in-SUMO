import os
import sys
import math
import sumolib

# Initialize SUMO tools
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.path.append('/usr/local/share/sumo/tools')

def get_dist(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

class PTAnalyzer:
    def __init__(self, net_file, stops_file, buses_file):
        print(f"Loading files...")
        net_abs = os.path.abspath(net_file)
        self.net = sumolib.net.readNet(net_abs)
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

    def find_best_route(self, origin_xy, dest_xy, person_depart=3660, max_walk=600):
        near_origin = []
        near_dest = []

        for s_id, s_xy in self.stop_coords.items():
            d_to_origin = get_dist(origin_xy, s_xy)
            d_to_dest = get_dist(dest_xy, s_xy)
            if d_to_origin <= max_walk:
                near_origin.append({'id': s_id, 'dist': d_to_origin})
            if d_to_dest <= max_walk:
                near_dest.append({'id': s_id, 'dist': d_to_dest})

        possible_options = []
        for trip in self.bus_trips:
            # Map stop ID to its 'until' time for this specific trip
            trip_schedule = {s.busStop: float(s.until) for s in trip.stop}
            trip_stop_ids = [s.busStop for s in trip.stop]
            
            for o_stop in near_origin:
                if o_stop['id'] in trip_schedule:
                    # EXACT DEPARTURE from your XML 'until'
                    bus_depart_from_stop = trip_schedule[o_stop['id']]
                    
                    walk1_dist = o_stop['dist']
                    walk1_time_s = walk1_dist / self.WALK_SPEED
                    person_reaches_stop = person_depart + walk1_time_s
                    
                    # 3) CHECK: Can the person catch this bus?
                    if person_reaches_stop > bus_depart_from_stop:
                        continue 

                    for d_stop in near_dest:
                        if d_stop['id'] in trip_schedule:
                            idx_o = trip_stop_ids.index(o_stop['id'])
                            idx_d = trip_stop_ids.index(d_stop['id'])
                            
                            if idx_o < idx_d:
                                # Ride time is simply Arrival_at_Dest - Departure_from_Origin
                                bus_arrival_at_dest = trip_schedule[d_stop['id']]
                                ride_time = bus_arrival_at_dest - bus_depart_from_stop
                                
                                walk2_dist = d_stop['dist']
                                walk2_time_s = walk2_dist / self.WALK_SPEED
                                wait_s = bus_depart_from_stop - person_reaches_stop
                                
                                total_time_s = walk1_time_s + wait_s + ride_time + walk2_time_s
                                
                                possible_options.append({
                                    'bus_id': trip.id,
                                    'line': trip.type,
                                    'board': o_stop['id'],
                                    'exit': d_stop['id'],
                                    'orig_x': origin_xy[0],
                                    'orig_y': origin_xy[1],
                                    'w1_dist': round(walk1_dist, 1),
                                    'w1_s': int(walk1_time_s),
                                    'arrival_at_stop': int(person_reaches_stop),
                                    'bus_depart_stop': int(bus_depart_from_stop),
                                    'wait_s': int(wait_s),
                                    'ride_s': int(ride_time),
                                    'w2_dist': round(walk2_dist, 1),
                                    'w2_s': int(walk2_time_s),
                                    'total_min': round(total_time_s / 60, 2),
                                    'rank_score': total_time_s + (walk1_dist * 0.5)
                                })

        return sorted(possible_options, key=lambda x: x['rank_score'])

if __name__ == "__main__":
    NET, STOPS, BUSES = "network.net.xml", "stops.add.xml", "buses.rou.xml"
    analyzer = PTAnalyzer(NET, STOPS, BUSES)

    # Example test with your updated depart times
    USER_START_TIME = 3660 
    origin = (-320.0, 115.0)
    dest = (210.0, -125.0)
    
    results = analyzer.find_best_route(origin, dest, person_depart=USER_START_TIME)

    print(f"\nTABLE 1: BUS ROUTE RANKING (Using XML 'until' times)")
    print("="*140)
    h1 = f"{'Rank':<4} | {'Bus ID':<7} | {'Line':<18} | {'Board':<7} | {'Reach Stop':<10} | {'Bus Leave':<10} | {'Wait(s)':<8} | {'Ride(s)':<8} | {'Total'}"
    print(h1)
    print("-" * 140)
    for i, res in enumerate(results[:10], 1):
        print(f"{i:<4} | {res['bus_id']:<7} | {res['line']:<18} | {res['board']:<7} | "
              f"{res['arrival_at_stop']:<10} | {res['bus_depart_stop']:<10} | {res['wait_s']:<8} | "
              f"{res['ride_s']:<8} | {res['total_min']} min")

    print(f"\nTABLE 2: PERSON TRIP LOGISTICS")
    print("="*190)
    h2 = (f"{'Orig X':<8} | {'Orig Y':<8} | {'To Stop':<10} | {'Walk Time':<10} | {'Walk Dist':<10} | "
          f"{'Arrival':<8} | {'Earliest Bus':<13} | {'Dest Stop':<10} | {'Last Leg':<12} | {'Walk Time':<10} | {'Walk Dist'}")
    print(h2)
    print("-" * 190)
    for res in results[:10]:
        print(f"{res['orig_x']:<8} | {res['orig_y']:<8} | {res['board']:<10} | {res['w1_s']:<10} | {res['w1_dist']:<10} | "
              f"{res['arrival_at_stop']:<8} | {res['bus_depart_stop']:<13} | {res['exit']:<10} | {'To Dest':<12} | "
              f"{res['w2_s']:<10} | {res['w2_dist']}")
    print("="*190)