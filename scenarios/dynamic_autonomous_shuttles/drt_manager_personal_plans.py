import traci
import math
import pandas as pd

STOPS_DATA = []

def calculate_dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def get_angle_diff(angle1, angle2):
    diff = abs(angle1 - angle2) % 360
    return 360 - diff if diff > 180 else diff

def get_closest_stop_to_stop(target_stop_id):
    """Finds the stop physically closest to the target_stop_id (excluding itself)."""
    target = next((s for s in STOPS_DATA if s['id'] == target_stop_id), None)
    if not target: return None
    
    closest_stop_id = None
    min_dist = float('inf')
    for s in STOPS_DATA:
        if s['id'] == target_stop_id: continue
        dist = calculate_dist(target['x'], target['y'], s['x'], s['y'])
        if dist < min_dist:
            min_dist = dist
            closest_stop_id = s['id']
    return closest_stop_id

def init_demand(excel_path, scale=1):
    """Caches stop geometry, dynamically assigns stops, calculates walk times, and builds demand dict."""
    global STOPS_DATA
    STOPS_DATA = []
    
    # 1. Ask SUMO directly for exact stop geometry
    for stop_id in traci.busstop.getIDList():
        lane_id = traci.busstop.getLaneID(stop_id)
        edge_id = lane_id.rsplit('_', 1)[0]
        lane_index = int(lane_id.rsplit('_', 1)[1])
        start_pos = traci.busstop.getStartPos(stop_id)
        end_pos = traci.busstop.getEndPos(stop_id)
        mid_pos = (start_pos + end_pos) / 2
        
        x, y = traci.simulation.convert2D(edge_id, mid_pos, laneIndex=lane_index)
        x1, y1 = traci.simulation.convert2D(edge_id, max(0, mid_pos - 1.0), laneIndex=lane_index)
        x2, y2 = traci.simulation.convert2D(edge_id, mid_pos + 1.0, laneIndex=lane_index)
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if angle < 0: angle += 360
        
        STOPS_DATA.append({'id': stop_id, 'x': x, 'y': y, 'angle': angle})
        
    demand_dict = {}
    master_database = {} 
    
    # 2. Read the raw Excel file and scale demand
    try:
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip()
        
        for _, row in df.iterrows():
            base_row_dict = row.to_dict()
            base_p_id = base_row_dict['person_id']
            ox, oy = base_row_dict['house_x'], base_row_dict['house_y']
            dx, dy = base_row_dict['destination_x'], base_row_dict['destination_y']
            
            # --- DYNAMICALLY FIND STOPS ---
            origin_stop, dest_drop, dest_pick, origin_drop = compute_stops_for_person(ox, oy, dx, dy)
            
            if not origin_stop:
                print(f"⚠️ Could not find valid stops for {base_p_id}. Skipping.")
                continue
                
            # --- CALCULATE WALK METRICS ---
            # 1. Home to Origin Pickup
            start_walk_dist, start_walk_time = get_walk_metrics(ox, oy, origin_stop)
            # 2. Destination Pickup to Final Destination (for the return trip)
            end_walk_dist, end_walk_time = get_walk_metrics(dx, dy, dest_pick)
            
            # --- PREPARE TIME DICTIONARY ---
            # Departure = Excel Time + First Walk Time
            outbound_time = int(base_row_dict['departure_time'] + start_walk_time)
            
            if outbound_time not in demand_dict:
                demand_dict[outbound_time] = []
            
            # ---> NEW: SCALE DEMAND BY DUPLICATING TRIPS <---
            for i in range(scale):
                row_dict = base_row_dict.copy()
                
                # Make the person_id unique if scaling (e.g., "person1_1", "person1_2")
                p_id = f"{base_p_id}_{i+1}" if scale > 1 else base_p_id
                row_dict['person_id'] = p_id
                
                # --- STORE DATA FOR DIRECT INJECTION ---
                row_dict['origin_selected_pickup'] = origin_stop
                row_dict['destination_selected_dropoff'] = dest_drop
                row_dict['destination_selected_pickup'] = dest_pick
                row_dict['origin_selected_dropoff'] = origin_drop
                
                row_dict['start_walk_distance'] = start_walk_dist
                row_dict['end_walk_distance'] = end_walk_dist
                row_dict['end_walk_time'] = end_walk_time
                row_dict['trip_type'] = 'outbound'
                
                # Save to master database for Return Trip lookup later
                master_database[p_id] = row_dict 
                
                # Add to demand dictionary
                demand_dict[outbound_time].append(row_dict)
                
        print(f"✅ Loaded and processed {len(master_database)} trips dynamically (Original: {len(df)}, Scaled by: {scale}).")
        return demand_dict, master_database 
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return {}, {}
    
    
def compute_stops_for_person(ox, oy, dx, dy):
    """Executes your adaptive search logic."""
    trip_angle = math.degrees(math.atan2(dy - oy, dx - ox))
    if trip_angle < 0: trip_angle += 360
    
    best_p_id, best_d_id = None, None
    
    for radius in [200, 300, 500]:
        o_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], ox, oy) <= radius]
        d_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], dx, dy) <= radius]
        
        o_filtered = [s for s in o_candidates if get_angle_diff(s['angle'], trip_angle) <= 100]
        d_filtered = [s for s in d_candidates if get_angle_diff(s['angle'], trip_angle) <= 100]
        
        if not o_filtered and o_candidates: o_filtered = o_candidates
        if not d_filtered and d_candidates: d_filtered = d_candidates

        if not o_filtered or not d_filtered: continue 

        max_pickup_score = -float('inf')
        temp_best_pickup = None
        
        for s_o in o_filtered:
            for s_d in d_filtered:
                walk_o = calculate_dist(s_o['x'], s_o['y'], ox, oy)
                walk_d = calculate_dist(s_d['x'], s_d['y'], dx, dy)
                ride_dist = calculate_dist(s_o['x'], s_o['y'], s_d['x'], s_d['y'])
                score = ride_dist - (3.0 * (walk_o + walk_d))
                
                if score > max_pickup_score:
                    max_pickup_score = score
                    temp_best_pickup = s_o
        
        temp_best_dropoff = None
        if temp_best_pickup:
            min_dist_from_pickup = float('inf')
            for s_d in d_filtered:
                d_dist_to_dest = calculate_dist(s_d['x'], s_d['y'], dx, dy)
                if d_dist_to_dest < min_dist_from_pickup:
                    min_dist_from_pickup = d_dist_to_dest
                    temp_best_dropoff = s_d
        
        if temp_best_pickup and temp_best_dropoff:
            best_p_id = temp_best_pickup['id']
            best_d_id = temp_best_dropoff['id']
            break
            
    if not best_p_id or not best_d_id:
        return None, None, None, None
        
    op_drop = get_closest_stop_to_stop(best_p_id) 
    dest_pick = get_closest_stop_to_stop(best_d_id)
    
    return best_p_id, best_d_id, dest_pick, op_drop

def get_walk_metrics(person_x, person_y, stop_id, walking_speed=1.32):
    """
    Calculates the Euclidean distance and walking time to/from a specific stop.
    Returns: (distance_in_meters, time_in_seconds)
    """
    if not stop_id:
        return 0.0, 0.0
        
    # Find the stop in our TraCI-cached geometry list
    stop_data = next((s for s in STOPS_DATA if s['id'] == stop_id), None)
    if not stop_data:
        return 0.0, 0.0
        
    # Calculate Euclidean Distance
    dist = math.sqrt((person_x - stop_data['x'])**2 + (person_y - stop_data['y'])**2)
    
    # Calculate Time (Distance / Speed)
    time = dist / walking_speed
    
    return dist, time

def check_and_inject_persons(current_time, pending_persons):
    """O(1) lookup to instantly find and inject anyone departing at this exact second."""
    current_sec = int(current_time)
    
    if current_sec not in pending_persons:
        return
        
    persons_to_depart = pending_persons.pop(current_sec)
    
    for person in persons_to_depart:
        person_id = person['person_id']
        trip_type = person.get('trip_type', 'outbound')
        
        try:
            if trip_type == 'outbound':
                # --- OUTBOUND: Origin -> Destination Dropoff ---
                p_id_actual = f"{person_id}_out"
                start_stop = person['origin_selected_pickup']
                end_stop = person['destination_selected_dropoff']
            else:
                # --- RETURN: Destination Pickup -> Origin Dropoff ---
                p_id_actual = f"{person_id}_ret"
                start_stop = person['destination_selected_pickup']
                end_stop = person['origin_selected_dropoff']
                
            # Safely get positions
            start_lane = traci.busstop.getLaneID(start_stop)
            start_edge = start_lane.rsplit('_', 1)[0]
            start_pos = min(traci.busstop.getEndPos(start_stop) - 1.0, traci.lane.getLength(start_lane) - 4.0)
            
            end_lane = traci.busstop.getLaneID(end_stop)
            end_edge = end_lane.rsplit('_', 1)[0]

            # ---> DIRECT INJECTION: Just Spawn and Ride! <---
            traci.person.add(p_id_actual, start_edge, pos=start_pos)
            traci.person.appendDrivingStage(p_id_actual, end_edge, "taxi", stopID=end_stop)
            
            print("-----------------------------------------")
            print(f"🧍 Spawned {p_id_actual}! Direct Ride: {start_stop} -> {end_stop}")
            print("-----------------------------------------")
            
        except traci.exceptions.TraCIException as e:
            print(f"⚠️ Failed to inject {person_id}: {e}")