import pandas as pd
import xml.etree.ElementTree as ET
import math
import os

# --- GEOMETRY HELPER FUNCTIONS ---

def get_lane_geometry(shape_str, pos):
    """
    Returns (x, y) and the Angle (degrees) of the lane at a specific position.
    """
    if not shape_str:
        return None, None, None
        
    points = [tuple(map(float, p.split(','))) for p in shape_str.split()]
    accumulated_dist = 0
    
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i+1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.sqrt(dx**2 + dy**2)
        
        if accumulated_dist + dist >= pos:
            remaining = pos - accumulated_dist
            ratio = remaining / dist if dist > 0 else 0
            x = p1[0] + ratio * dx
            y = p1[1] + ratio * dy
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0: angle += 360
            return x, y, angle
        accumulated_dist += dist
        
    last_p = points[-1]
    prev_p = points[-2] if len(points) > 1 else points[-1]
    dx = last_p[0] - prev_p[0]
    dy = last_p[1] - prev_p[1]
    angle = math.degrees(math.atan2(dy, dx))
    if angle < 0: angle += 360
    return last_p[0], last_p[1], angle

def calculate_dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def get_angle_diff(angle1, angle2):
    diff = abs(angle1 - angle2) % 360
    return 360 - diff if diff > 180 else diff

def get_closest_stop_to_stop(target_stop_id, all_stops):
    """Finds the stop physically closest to the target_stop_id (excluding itself)."""
    if not target_stop_id:
        return None
    
    # Find coordinates of the target stop
    target = next((s for s in all_stops if s['id'] == target_stop_id), None)
    if not target:
        return None
        
    closest_stop_id = None
    min_dist = float('inf')
    
    for s in all_stops:
        # Skip the exact same stop ID to find the "opposite" one
        if s['id'] == target_stop_id:
            continue
            
        dist = calculate_dist(target['x'], target['y'], s['x'], s['y'])
        
        # We look for the absolute closest stop (likely across the street)
        if dist < min_dist:
            min_dist = dist
            closest_stop_id = s['id']
            
    return closest_stop_id

# --- MAIN ANALYSIS ---

def analyze_stops_adaptive(od_file, net_xml, stops_xml, output_xlsx):
    # 1. Parse Network
    print(f"Loading Network: {net_xml}")
    if not os.path.exists(net_xml):
        print("Error: Network file not found.")
        return

    tree_net = ET.parse(net_xml)
    root_net = tree_net.getroot()
    lane_shapes = {lane.get('id'): lane.get('shape') for lane in root_net.findall(".//lane")}

    # 2. Parse Stops
    print(f"Loading Stops: {stops_xml}")
    if not os.path.exists(stops_xml):
        print("Error: Stops file not found.")
        return
        
    tree_stops = ET.parse(stops_xml)
    root_stops = tree_stops.getroot()
    stops_data = []

    for stop in root_stops.findall(".//busStop"):
        lane_id = stop.get('lane')
        mid_pos = (float(stop.get('startPos')) + float(stop.get('endPos'))) / 2
        shape = lane_shapes.get(lane_id)
        if shape:
            x, y, angle = get_lane_geometry(shape, mid_pos)
            if x is not None:
                stops_data.append({'id': stop.get('id'), 'x': x, 'y': y, 'angle': angle})

    # 3. Process OD Trips
    print(f"Processing Trips from: {od_file}")
    try:
        # Read Excel and strip whitespace from headers
        df = pd.read_excel(od_file)
        df.columns = df.columns.str.strip()
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    RADII_TO_TRY = [200, 300, 600] 
    ANGLE_TOLERANCE = 100
    WALK_PENALTY = 3.0
    WALKING_SPEED = 1.32 # Assumed walking speed in m/s (approx 5km/h)
    
    # Lists for Results
    origin_pickups = []
    dest_dropoffs = []
    origin_dropoffs = [] 
    dest_pickups = []    
    
    # New lists for walking times and distances
    start_walk_times = []
    end_walk_times = []
    start_walk_distances = []
    end_walk_distances = []

    print("Running Adaptive Optimization & Calculating Walk Times/Distances...")

    for idx, row in df.iterrows():
        ox, oy = row['house_x'], row['house_y']
        dx, dy = row['destination_x'], row['destination_y']
        
        trip_angle = math.degrees(math.atan2(dy - oy, dx - ox))
        if trip_angle < 0: trip_angle += 360
        
        best_p_id = None
        best_d_id = None
        temp_best_pickup = None

        # Try small radius first, then expand if no stops found
        for radius in RADII_TO_TRY:
            o_candidates = [s for s in stops_data if calculate_dist(s['x'], s['y'], ox, oy) <= radius]
            d_candidates = [s for s in stops_data if calculate_dist(s['x'], s['y'], dx, dy) <= radius]
            
            # Filter by angle
            o_filtered = [s for s in o_candidates if get_angle_diff(s['angle'], trip_angle) <= ANGLE_TOLERANCE]
            d_filtered = [s for s in d_candidates if get_angle_diff(s['angle'], trip_angle) <= ANGLE_TOLERANCE]
            
            # Fallback
            if not o_filtered and o_candidates: o_filtered = o_candidates
            if not d_filtered and d_candidates: d_filtered = d_candidates

            if not o_filtered or not d_filtered:
                continue 

            # SEARCH STEP 1: Best Pickup Stop
            max_pickup_score = -float('inf')
            
            for s_o in o_filtered:
                for s_d in d_filtered:
                    walk_o = calculate_dist(s_o['x'], s_o['y'], ox, oy)
                    walk_d = calculate_dist(s_d['x'], s_d['y'], dx, dy)
                    ride_dist = calculate_dist(s_o['x'], s_o['y'], s_d['x'], s_d['y'])
                    
                    score = ride_dist - (WALK_PENALTY * (walk_o + walk_d))
                    
                    if score > max_pickup_score:
                        max_pickup_score = score
                        temp_best_pickup = s_o
            
            # SEARCH STEP 2: Best Dropoff Stop
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

        # Append standard results
        origin_pickups.append(best_p_id)
        dest_dropoffs.append(best_d_id)
        
        op_drop = get_closest_stop_to_stop(best_p_id, stops_data) 
        dest_pick = get_closest_stop_to_stop(best_d_id, stops_data) 
        
        origin_dropoffs.append(op_drop)
        dest_pickups.append(dest_pick)

        # --- NEW: Calculate Walk Times & Distances ---
        start_time = None
        end_time = None
        dist_start_val = None
        dist_end_val = None

        # 1. Start Walk (House to Origin Pickup)
        if temp_best_pickup:
            dist_start_val = calculate_dist(ox, oy, temp_best_pickup['x'], temp_best_pickup['y'])
            start_time = dist_start_val / WALKING_SPEED # Time in seconds
            if idx == 0: print(f"DEBUG P1 Start Walk: House({ox:.1f}, {oy:.1f}) -> Stop({temp_best_pickup['x']:.1f}, {temp_best_pickup['y']:.1f}) | Dist: {dist_start_val:.2f}m | Speed: {WALKING_SPEED}m/s | Time: {start_time:.2f}s")
            
        # 2. End Walk (Destination Pickup to Destination coordinates)
        if dest_pick:
            # Look up the actual coordinates of the selected destination pickup stop
            dp_stop = next((s for s in stops_data if s['id'] == dest_pick), None)
            if dp_stop:
                dist_end_val = calculate_dist(dp_stop['x'], dp_stop['y'], dx, dy)
                end_time = dist_end_val / WALKING_SPEED # Time in seconds

        start_walk_times.append(start_time)
        end_walk_times.append(end_time)
        start_walk_distances.append(dist_start_val)
        end_walk_distances.append(dist_end_val)

    # 4. Save Output
    df['origin_selected_pickup'] = origin_pickups
    df['destination_selected_dropoff'] = dest_dropoffs
    df['destination_selected_pickup'] = dest_pickups
    df['origin_selected_dropoff'] = origin_dropoffs
    
    # Add new columns
    df['start_walk_distance'] = start_walk_distances
    df['end_walk_distance'] = end_walk_distances
    df['start_walk_time'] = start_walk_times
    df['end_walk_time'] = end_walk_times
    
    df.to_excel(output_xlsx, index=False)
    print(f"Success! Results saved to: {output_xlsx}")

# --- RUN SCRIPT ---
analyze_stops_adaptive(
    od_file='personal_planes.xlsx', 
    net_xml='../network.net.xml', 
    stops_xml='../as_stops.add.xml', 
    output_xlsx='new_table.xlsx' # Updated target output file
)