import traci
import math
import xml.etree.ElementTree as ET

ROUTE_CACHE = {}

def get_sorted_buses(user_id, buses):
    """
    Calculates the distance to every bus and returns a list of all buses,
    sorted from absolute closest to furthest.
    """
    if not buses:
        return []
        
    user_pos = traci.person.getPosition(user_id)
    bus_distances = []
    
    for bus in buses:
        bus_pos = traci.vehicle.getPosition(bus)
        distance = math.dist(user_pos, bus_pos) 
        bus_distances.append((distance, bus))
        
    # Sort the list by distance (shortest to longest)
    bus_distances.sort()
    
    # Return just the bus IDs in order
    return [bus for dist, bus in bus_distances]


def get_travel_time(start_edge, end_edge):
    # If they are on the same street, the distance is 0!
    if start_edge == end_edge:
        return 0
        
    pair = (start_edge, end_edge)
    
    # If we have NEVER calculated this route before, ask SUMO
    if pair not in ROUTE_CACHE:
        try:
            route = traci.simulation.findRoute(start_edge, end_edge)
            ROUTE_CACHE[pair] = route.travelTime if len(route.edges) > 0 else float('inf')
        except traci.exceptions.TraCIException:
            ROUTE_CACHE[pair] = float('inf')
            
    # Return the saved answer instantly
    return ROUTE_CACHE[pair]


def get_bus_stops(stop_xml_file):
    """Reads the XML and creates a simple dictionary mapping {Edge: BusStop_ID}"""
    tree = ET.parse(stop_xml_file)
    stops = {}
    for stop in tree.getroot().findall('busStop'):
        lane = stop.get('lane')
        if lane:
            edge = lane.rsplit('_', 1)[0]
            stops[edge] = stop.get('id')
    return stops


def optimize_route_sequence(bus_id, manifest, new_res=None, dropoff_weight=1):
    """
    Analyzes a taxi manifest and re-orders it using a Greedy Nearest-Neighbor approach.
    Includes a Virtual Occupancy Tracker to prevent scheduling more pickups 
    than the vehicle's physical capacity allows.
    
    :param bus_id: The ID of the vehicle.
    :param manifest: The list of reservation IDs assigned to the vehicle.
    :param dropoff_weight: Float between 0.0 and 1.0 to artificially reduce drop-off distances.
        -> Range: (0.0 to 1.0]. Default is 0.2.
        -> 0.1 (Heavy Drop-off Priority): The bus will almost always drop people off before 
           picking up new ones. Passengers get home very fast, but the bus drives more miles.
        -> 0.9 (Light Drop-off Priority): The bus behaves almost like standard Nearest-Neighbor. 
           It will gladly detour to pick up nearby people, even if passengers are waiting inside. 
           Highly efficient for the fleet, but passengers may be trapped inside for a long time.
        -> 1.0 (Neutral): Distance is the only factor.
    """
    if not manifest:
        return []

    # 1. Fetch details using safe bitmasks
    handled = traci.person.getTaxiReservations(12) # People on the buses
    waiting = traci.person.getTaxiReservations(3)  # People in the queue
    
    all_res = list(handled) + list(waiting)
    res_map = {r.id: r for r in all_res}
    
    
    if new_res:
        res_map[new_res.id] = new_res


    needs_pickup = set()
    needs_dropoff = set()
    
    # Get the actual physical capacity of the vehicle from SUMO
    try:
        max_capacity = traci.vehicle.getPersonCapacity(bus_id)
    except traci.exceptions.TraCIException:
        max_capacity = 40 # Fallback just in case
        
    simulated_occupancy = 0
    
    # 2. Check actual SUMO state and count current riders
    unique_ids = set(manifest)
    for rid in sorted(unique_ids):
        if rid not in res_map:
            continue # If they are missing, their trip is already completely finished!
            
        state = res_map[rid].state
        
        if state == 8: 
            # State 8 means they are ALREADY RIDING in the bus!
            needs_dropoff.add(rid)
            simulated_occupancy += 1 # Add them to our virtual counter
        else:
            # States 1, 2, or 4 mean they are still waiting on the sidewalk.
            needs_pickup.add(rid)
    
    # 3. Get the bus's exact starting location
    current_edge = traci.vehicle.getRoadID(bus_id)
    if current_edge.startswith(":") or current_edge == "": # Failsafe if the bus is inside an intersection
        try:
            route = traci.vehicle.getRoute(bus_id)
            idx = traci.vehicle.getRouteIndex(bus_id)
            current_edge = route[idx]
        except traci.exceptions.TraCIException:
            pass

    optimized_manifest = []
    
    
    # 4. Greedy Loop: Always choose the closest valid action
    while needs_pickup or needs_dropoff:
        best_action = None
        best_cost = float('inf')
        best_is_pickup = False
        target_edge_for_best = ""
        
        # --- Check all possible PICKUPS ---
        # ONLY check pickups if our simulated future bus has empty seats!
        if simulated_occupancy < max_capacity:
            for res_id in sorted(needs_pickup):
                if res_id in res_map:
                    target_edge = res_map[res_id].fromEdge
                    
                    # if current_edge == target_edge:
                    #     cost = 0
                    # else:
                    #     route = traci.simulation.findRoute(current_edge, target_edge)
                    #     cost = route.travelTime if len(route.edges) > 0 else float('inf')
                    cost = get_travel_time(current_edge, target_edge)

                    if cost < best_cost:
                        best_cost = cost
                        best_action = res_id
                        best_is_pickup = True
                        target_edge_for_best = target_edge
                    
        # --- Check all possible DROP-OFFS ---
        # Drop-offs are ALWAYS allowed because they free up space.
        for res_id in sorted(needs_dropoff):
            if res_id in res_map:
                target_edge = res_map[res_id].toEdge
                
                # if current_edge == target_edge:
                #     cost = 0
                # else:
                #     route = traci.simulation.findRoute(current_edge, target_edge)
                #     cost = route.travelTime if len(route.edges) > 0 else float('inf')

                cost = get_travel_time(current_edge, target_edge)


                # Multiply cost by 0.2 to artificially make drop-offs look closer.
                # This prevents passengers from being trapped in the bus for a long time!
                cost = cost * dropoff_weight

                if cost < best_cost:
                    best_cost = cost
                    best_action = res_id
                    best_is_pickup = False
                    target_edge_for_best = target_edge
                    
        # 5. Apply the best action found to the new list
        if best_action is not None:
            optimized_manifest.append(best_action)
            current_edge = target_edge_for_best # Move our virtual location to this stop
            
            if best_is_pickup:
                needs_pickup.remove(best_action)
                needs_dropoff.add(best_action) # Now they need a drop-off
                simulated_occupancy += 1       # A passenger got on, take up a seat!
            else:
                needs_dropoff.remove(best_action)
                simulated_occupancy -= 1       # A passenger got off, free up a seat!
        else:
            # Failsafe: if routing completely fails, append whatever is left
            for p in needs_pickup:
                optimized_manifest.extend([p, p])
            for d in needs_dropoff:
                optimized_manifest.append(d)
            break
            
    return optimized_manifest



def simulate_manifest(bus_id, manifest, res_map):
    """
    Simulates the route and tracks EXACTLY when each person gets picked up AND dropped off.
    Reads vehicle physics (boarding times) dynamically from SUMO.
    Returns: (total_driving_time, dictionary_of_dropoff_times, dictionary_of_pickup_times)
    """
    if not manifest:
        return 0, {}, {}
        
    current_edge = traci.vehicle.getRoadID(bus_id)
    if current_edge.startswith(":") or current_edge == "":
        try:
            route = traci.vehicle.getRoute(bus_id)
            idx = traci.vehicle.getRouteIndex(bus_id)
            current_edge = route[idx]
        except traci.exceptions.TraCIException:
            pass
    
    # ---> READ DYNAMIC PHYSICS FROM YOUR XML <---
    try:
        # Ask SUMO for the vehicle's specific parameters
        p_dur = traci.vehicle.getParameter(bus_id, "device.taxi.pickUpDuration")
        pickup_duration = float(p_dur) if p_dur else 0.0
    except traci.exceptions.TraCIException:
        pickup_duration = 0.0 # Default if missing
        
    try:
        d_dur = traci.vehicle.getParameter(bus_id, "device.taxi.dropOffDuration")
        dropoff_duration = float(d_dur) if d_dur else 0.0
    except traci.exceptions.TraCIException:
        dropoff_duration = 0.0 # Default if missing
    # --------------------------------------------

    total_time = 0
    dropoff_times = {}
    pickup_times = {}
    seen_counts = {}
    
    for res_id in manifest:
        if res_id not in res_map:
            continue
            
        seen_counts[res_id] = seen_counts.get(res_id, 0) + 1
        res = res_map[res_id]
        
        is_pickup = False
        if res.state == 8:
            is_pickup = False
        else:
            if seen_counts[res_id] == 1:
                is_pickup = True
            else:
                is_pickup = False
                
        target_edge = res.fromEdge if is_pickup else res.toEdge
        leg_time = get_travel_time(current_edge, target_edge)
        total_time += leg_time
        
        # ---> APPLY THE EXACT DYNAMIC DURATION <---
        if is_pickup:
            total_time += pickup_duration
        else:
            total_time += dropoff_duration
        # ------------------------------------------
        
        # ---> RECORD THE EXACT PICKUP OR DROP-OFF TIME! <---
        if is_pickup:
            if res_id not in pickup_times:
                pickup_times[res_id] = total_time
        else:
            dropoff_times[res_id] = total_time
            
        current_edge = target_edge
        
    return total_time, dropoff_times, pickup_times

def get_marginal_cost_sorted_buses(new_res, buses, bus_manifests, current_time, promised_pickup_times, res_to_user_map, max_dropoff_delay=240, max_pickup_delay=120):
    """
    The strict Marginal Cost Sorter.
    Rejects buses if the detour causes too much delay for Drop-offs OR Pickups,
    locking in ETAs using the original promised pickup time.
    """
    if not buses:
        return []
        
    try:
        handled_res = traci.person.getTaxiReservations(12) 
        res_map = {r.id: r for r in handled_res}
    except traci.exceptions.TraCIException:
        res_map = {}
        
    res_map[new_res.id] = new_res 
    
    bus_margins = []
    
    for bus in buses:
        # ---> GRAB THE MANIFEST (This is what was missing!) <---
        current_manifest = bus_manifests.get(bus, [])
        
        # 1. Base Simulation: When is everyone currently scheduled to get picked up and dropped off?
        base_total_time, base_dropoffs, base_pickups = simulate_manifest(bus, current_manifest, res_map)
        
        # 2. Simulate inserting the new passenger
        test_manifest = current_manifest.copy()
        test_manifest.extend([new_res.id, new_res.id])
        optimized_test = optimize_route_sequence(bus, test_manifest, new_res=new_res, dropoff_weight=1.0)
        
        # 3. New Simulation: What happens to the schedules if we add this person?
        new_total_time, new_dropoffs, new_pickups = simulate_manifest(bus, optimized_test, res_map)
        
        is_valid = True
        
        # ---> RULE 1: DROP-OFF CONSTRAINT (Protect riders inside the bus) <---
        for r_id, base_time in base_dropoffs.items():
            if r_id in new_dropoffs:
                delay = new_dropoffs[r_id] - base_time
                if delay > max_dropoff_delay:
                    is_valid = False
                    break 
                    
        # ---> RULE 2: ANCHORED PICKUP CONSTRAINT (Protect people waiting on the curb) <---
        if is_valid: 
            for r_id, new_duration in new_pickups.items():
                
                # Translate reservation ID to User ID using your dictionary map
                person_id = res_to_user_map.get(r_id) 
                
                # If we have an original promise for this person, check against THAT!
                if person_id and person_id in promised_pickup_times:
                    # Calculate the EXACT predicted clock time of arrival
                    predicted_arrival_time = current_time + new_duration
                    original_promise = promised_pickup_times[person_id]
                    
                    # Calculate total drift from the very first promise
                    total_drift = predicted_arrival_time - original_promise
                    
                    if total_drift > max_pickup_delay:
                        is_valid = False
                        break
                else:
                    # If no promise exists (they are brand new), use the standard base_time check
                    if r_id in base_pickups:
                        delay = new_duration - base_pickups[r_id]
                        if delay > max_pickup_delay:
                            is_valid = False
                            break
                        
        # If it broke EITHER rule, throw this bus in the trash!
        if not is_valid:
            continue
            
        # 5. If it passed both strict SLA checks, calculate the system margin
        margin = new_total_time - base_total_time
        bus_margins.append((margin, bus))
        
    bus_margins.sort()
    return [bus for margin, bus in bus_margins]



def get_pickup_eta(bus_id, manifest, target_res):
    """
    Helper function to calculate the exact ETA in seconds for a specific passenger's pickup.
    """
    try:
        handled = traci.person.getTaxiReservations(12)
        waiting = traci.person.getTaxiReservations(3)
        res_map = {r.id: r for r in list(handled) + list(waiting)}
    except:
        res_map = {}
        
    res_map[target_res.id] = target_res
    
    _, _, pickup_times = simulate_manifest(bus_id, manifest, res_map)
    return pickup_times.get(target_res.id, -1)

def get_stop_details(stop_xml_file):
    """Parses the XML and finds the exact physical center of every bus stop."""
    tree = ET.parse(stop_xml_file)
    stops = {}
    for stop in tree.getroot().findall('busStop'):
        stop_id = stop.get('id')
        lane = stop.get('lane')
        if lane:
            edge = lane.rsplit('_', 1)[0]
            # Grab where the bus stop starts
            start_pos = float(stop.get('startPos', 0))
            
            # Calculate the exact middle position so they stand perfectly inside it
            end_pos_str = stop.get('endPos')
            if end_pos_str:
                end_pos = float(end_pos_str)
                pos = (start_pos + end_pos) / 2.0
            else:
                pos = start_pos + 10.0  # Assumes standard 20m bus stop length
            
            stops[stop_id] = {'edge': edge, 'pos': pos}
    return stops

def insert_person(person_id, depart_time, origin_pickup, dest_dropoff, dest_pickup, origin_dropoff, activity_dur, stop_details):
    try:
        # Get the exact street AND position for the starting bus stop
        start_edge = stop_details[origin_pickup]['edge']
        start_pos = stop_details[origin_pickup]['pos']
        
        # Add the person EXACTLY inside the bus stop box
        traci.person.add(person_id, edgeID=start_edge, pos=start_pos, depart=depart_time)
        
        # 1. Wait for ride
        traci.person.appendWaitingStage(person_id, duration=0, description="waiting", stopID=origin_pickup)
        
        # 2. Ride to first destination
        traci.person.appendDrivingStage(person_id, toEdge=stop_details[dest_dropoff]['edge'], lines="taxi", stopID=dest_dropoff)
        
        # 3. Quick dropoff wait
        traci.person.appendWaitingStage(person_id, duration=5, description="activity", stopID=dest_dropoff)
        
        # 4. Walk to activity bus stop (Update arrivalPos so they walk into the middle of the box!)
        traci.person.appendWalkingStage(person_id, edges=[stop_details[dest_pickup]['edge']], arrivalPos=stop_details[dest_pickup]['pos'], stopID=dest_pickup)
        
        # 5. Do activity
        traci.person.appendWaitingStage(person_id, duration=activity_dur, description="activity", stopID=dest_pickup)
        
        # 6. Ride home
        traci.person.appendDrivingStage(person_id, toEdge=stop_details[origin_dropoff]['edge'], lines="taxi", stopID=origin_dropoff)
        
        # 7. Walk home (Update arrivalPos here too)
        traci.person.appendWalkingStage(person_id, edges=[stop_details[origin_pickup]['edge']], arrivalPos=stop_details[origin_pickup]['pos'], stopID=origin_pickup)
        
        print(f"✅ Inserted {person_id} perfectly inside {origin_pickup}!")
        
    except traci.exceptions.TraCIException as e:
        print(f"❌ Failed to insert person {person_id}: {e}")


