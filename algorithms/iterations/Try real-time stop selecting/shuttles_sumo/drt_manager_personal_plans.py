import traci
import math
import drt_manager_lib as lib

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
    """Caches stop geometry and queues passengers at their base departure time."""
    global STOPS_DATA
    STOPS_DATA = []
    
    # ---> THE RESTORED STOPS_DATA CACHING LOGIC <---
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
    # ------------------------------------------------
        
    demand_dict = {}
    master_database = {} 
    
    try:
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip()
        
        for _, row in df.iterrows():
            base_row_dict = row.to_dict()
            base_p_id = base_row_dict['person_id']
            
            # We use the raw Excel time. No walking time calculated yet!
            departure_time = int(base_row_dict['departure_time'])
            
            if departure_time not in demand_dict:
                demand_dict[departure_time] = []
            
            for i in range(scale):
                row_dict = base_row_dict.copy()
                p_id = f"{base_p_id}_{i+1}" if scale > 1 else base_p_id
                
                row_dict['person_id'] = p_id
                row_dict['trip_type'] = 'outbound'
                row_dict['state'] = 'at_home' 
                
                master_database[p_id] = row_dict 
                demand_dict[departure_time].append(row_dict)
                
        print(f"✅ Loaded {len(master_database)} trips. Stops will be assigned in real-time!")
        return demand_dict, master_database 
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return {}, {}
    
    
def compute_stops_for_person(ox, oy, dx, dy):
    """Executes your adaptive search logic."""
    trip_angle = math.degrees(math.atan2(dy - oy, dx - ox))
    if trip_angle < 0: trip_angle += 360
    
    best_p_id, best_d_id = None, None
    
    # Expand search radius if no stops are found nearby
    for radius in [200, 300, 500]:
        o_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], ox, oy) <= radius]
        d_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], dx, dy) <= radius]
        
        o_filtered = [s for s in o_candidates if get_angle_diff(s['angle'], trip_angle) <= 100]
        d_filtered = [s for s in d_candidates if get_angle_diff(s['angle'], trip_angle) <= 100]
        
        if not o_filtered and o_candidates: o_filtered = o_candidates
        if not d_filtered and d_candidates: d_filtered = d_candidates

        if not o_filtered or not d_filtered: continue 

        # ---> THE UPDATE: Find the best pair at the exact same time <---
        best_score = -float('inf')
        
        for s_o in o_filtered:
            for s_d in d_filtered:
                walk_o = calculate_dist(s_o['x'], s_o['y'], ox, oy)
                walk_d = calculate_dist(s_d['x'], s_d['y'], dx, dy)
                ride_dist = calculate_dist(s_o['x'], s_o['y'], s_d['x'], s_d['y'])
                
                # Apply the walking penalty
                score = ride_dist - (3.0 * (walk_o + walk_d))
                
                # If this is the best pair so far, save BOTH IDs
                if score > best_score:
                    best_score = score
                    best_p_id = s_o['id']
                    best_d_id = s_d['id']
        
        # If we successfully found a valid pair in this radius, stop searching!
        if best_p_id and best_d_id:
            break
            
    if not best_p_id or not best_d_id:
        return None, None, None, None
        
    # Get the return trip stops
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

def check_and_inject_persons(current_time, pending_persons, master_database, buses, bus_stops_dict):
    current_sec = int(current_time)
    
    if current_sec not in pending_persons:
        return
        
    persons_to_process = pending_persons.pop(current_sec)
    
    for person in list(persons_to_process):
        state = person.get('state', 'at_home')
        person_id = person['person_id']
        
        # ==========================================
        # PHASE 1: They are at home. Pick stops and start walking!
        # ==========================================
        if state == 'at_home':
            ox, oy = person['house_x'], person['house_y']
            dx, dy = person['destination_x'], person['destination_y']
            
            # ---> RUN REAL-TIME STOP SELECTION <---
            p_id, d_id, ret_p, ret_d = dynamic_stop_selection(ox, oy, dx, dy, buses, bus_stops_dict)
            
            if not p_id:
                print(f"⚠️ No valid stops found for {person_id}. Trip cancelled.")
                continue
                
            # Save the chosen stops
            person['origin_selected_pickup'] = p_id
            person['destination_selected_dropoff'] = d_id
            person['destination_selected_pickup'] = ret_p
            person['origin_selected_dropoff'] = ret_d
            
            # Calculate Walk Times
            start_walk_dist, start_walk_time = get_walk_metrics(ox, oy, p_id)
            end_walk_dist, end_walk_time = get_walk_metrics(dx, dy, d_id)
            
            person['start_walk_distance'] = start_walk_dist
            person['end_walk_distance'] = end_walk_dist
            person['end_walk_time'] = end_walk_time
            
            # Update the master database so the return trip knows where to go later!
            master_database[person_id].update(person)
            
            # ---> SCHEDULE THE ACTUAL SPAWN <---
            # They will appear at the bus stop when their walk finishes
            spawn_time = int(current_sec + start_walk_time)
            person['state'] = 'walking_to_stop'
            
            if spawn_time not in pending_persons:
                pending_persons[spawn_time] = []
            pending_persons[spawn_time].append(person)
            
            # print(f"🏠 {person_id} chose stops. Walking to {p_id}. Will arrive at {spawn_time}s.")
            
        # ==========================================
        # PHASE 2: Walk finished. Spawn them at the stop!
        # ==========================================
        elif state == 'walking_to_stop':
            trip_type = person.get('trip_type', 'outbound')
            
            try:
                if trip_type == 'outbound':
                    p_id_actual = f"{person_id}_out"
                    start_stop = person['origin_selected_pickup']
                    end_stop = person['destination_selected_dropoff']
                else:
                    p_id_actual = f"{person_id}_ret"
                    start_stop = person['destination_selected_pickup']
                    end_stop = person['origin_selected_dropoff']
                    
                # Safely get positions
                start_lane = traci.busstop.getLaneID(start_stop)
                start_edge = start_lane.rsplit('_', 1)[0]
                start_pos = min(traci.busstop.getEndPos(start_stop) - 1.0, traci.lane.getLength(start_lane) - 4.0)
                
                end_lane = traci.busstop.getLaneID(end_stop)
                end_edge = end_lane.rsplit('_', 1)[0]

                # Direct Injection into SUMO
                traci.person.add(p_id_actual, start_edge, pos=start_pos)
                traci.person.appendDrivingStage(p_id_actual, end_edge, "taxi", stopID=end_stop)
                
                print(f"🧍 Spawned {p_id_actual} at {start_stop}! Reservation created.")
                
            except traci.exceptions.TraCIException as e:
                print(f"⚠️ Failed to inject {person_id}: {e}")


def dynamic_stop_selection(ox, oy, dx, dy, buses, bus_stops_dict):
    """Tries to piggyback on live buses first. Falls back to spatial logic if none match."""
    # STEP 1: Try the advanced Piggyback logic
    p_id, d_id = find_piggyback_stops(ox, oy, dx, dy, buses, bus_stops_dict)
    
    if p_id and d_id:
        # Generate the return trip stops by finding the opposite direction lanes
        dest_pick = get_closest_stop_to_stop(d_id)
        op_drop = get_closest_stop_to_stop(p_id)
        return p_id, d_id, dest_pick, op_drop
        
    # STEP 2: Piggyback failed (no buses going that way). Fallback to standard spatial logic!
    return compute_stops_for_person(ox, oy, dx, dy)

# (Make sure the find_piggyback_stops function from my previous message is also pasted here!)

def find_piggyback_stops(ox, oy, dx, dy, buses, bus_stops_dict, max_walk_radius=500, max_drop_radius=100):
    """
    Checks if any active bus is already planning to drive from near the Origin 
    to near the Destination, and if the user can walk there in time.
    """
    # 1. Get all stops near the Origin (Walkable Catchment)
    o_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], ox, oy) <= max_walk_radius]
    
    # 2. Get all stops near the Destination (Strict 100m Drop-off Catchment)
    d_candidates = [s for s in STOPS_DATA if calculate_dist(s['x'], s['y'], dx, dy) <= max_drop_radius]
    
    if not o_candidates or not d_candidates:
        return None, None # Fallback to standard method

    o_ids = {s['id'] for s in o_candidates}
    d_ids = {s['id'] for s in d_candidates}
    
    best_bus = None
    best_p_id = None
    best_d_id = None
    best_score = float('inf') # Lower is better (Time)

    # 3. Scan all live buses
    for bus in buses:
        try:
            # Ask SUMO for the actual sequence of streets this bus is going to drive
            current_route = traci.vehicle.getRoute(bus)
            route_idx = traci.vehicle.getRouteIndex(bus)
            future_edges = current_route[route_idx:] 
            
            # Convert those streets into bus stops
            future_stops = lib.get_stops_from_edges(future_edges, bus_stops_dict)
            
            # 4. Look for a matching Origin Stop first
            for i, planned_stop in enumerate(future_stops):
                if planned_stop in o_ids:
                    
                    # 5. We found a pickup! Check if the person can walk there before the bus arrives.
                    # (Approximation: edge count * avg time per edge. For exact time, use lib.simulate_manifest)
                    bus_eta_approx = i * 15.0 # Rough guess: 15 seconds per street
                    
                    stop_geom = next(s for s in STOPS_DATA if s['id'] == planned_stop)
                    walk_dist = calculate_dist(ox, oy, stop_geom['x'], stop_geom['y'])
                    walk_time = walk_dist / 1.32
                    
                    if walk_time <= bus_eta_approx:
                        
                        # 6. Person can catch it! Now check if this bus goes near the destination AFTER the pickup.
                        remaining_stops = future_stops[i+1:]
                        for potential_drop in remaining_stops:
                            if potential_drop in d_ids:
                                
                                # PERFECT MATCH FOUND! Score it by total walk distance
                                drop_geom = next(s for s in STOPS_DATA if s['id'] == potential_drop)
                                end_walk_dist = calculate_dist(dx, dy, drop_geom['x'], drop_geom['y'])
                                total_walk = walk_dist + end_walk_dist
                                
                                if total_walk < best_score:
                                    best_score = total_walk
                                    best_p_id = planned_stop
                                    best_d_id = potential_drop
                                    best_bus = bus
                                    
        except traci.exceptions.TraCIException:
            continue

    if best_p_id and best_d_id:
        print(f"🎯 Piggyback Success! Found perfect pre-existing route on best_bus:{best_bus} best_p_id:{best_p_id}best_d_id:{best_d_id}")
        return best_p_id, best_d_id
        
    return None, None