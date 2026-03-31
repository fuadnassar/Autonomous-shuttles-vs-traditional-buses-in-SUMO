import traci
import math
import xml.etree.ElementTree as ET

ROUTE_CACHE = {}

# ---> NEW: Global Caches for Stop Spaces and Bus Sizes <---#
AVAILABLE_STOPS_SPACE = {}
BUS_LENGTHS = {}

def init_simulation_data(buses):
    """Caches all stop lengths and bus sizes exactly once when the simulation starts."""
    global AVAILABLE_STOPS_SPACE, BUS_LENGTHS
    
    # Cache Stop Lengths
    try:
        for stop_id in traci.busstop.getIDList():
            start = traci.busstop.getStartPos(stop_id)
            end = traci.busstop.getEndPos(stop_id)
            AVAILABLE_STOPS_SPACE[stop_id] = abs(end - start)
    except traci.exceptions.TraCIException:
        pass
        
    # Cache Bus Lengths (INCLUDING THE MIN GAP)
    for bus in buses:
        try:
            actual_length = traci.vehicle.getLength(bus)
            try:
                gap = traci.vehicle.getMinGap(bus)
            except:
                gap = 2.5 # SUMO default gap
            BUS_LENGTHS[bus] = actual_length + gap
        except traci.exceptions.TraCIException:
            BUS_LENGTHS[bus] = 22.5 # Fallback safety (20m bus + 2.5m gap)


def get_bus_length(bus_id):
    """Lazy-loads the bus length + minGap to handle dynamically spawned vehicles."""
    global BUS_LENGTHS
    if bus_id not in BUS_LENGTHS:
        try:
            # Ask SUMO for the exact length AND the gap
            actual_length = traci.vehicle.getLength(bus_id)
            try:
                gap = traci.vehicle.getMinGap(bus_id)
            except:
                gap = 2.5 # SUMO default gap
                
            BUS_LENGTHS[bus_id] = actual_length + gap
        except traci.exceptions.TraCIException:
            BUS_LENGTHS[bus_id] = 22.5 # Fallback just in case
            
    return BUS_LENGTHS[bus_id]


def request_idle_parking(bus_id, stop_id):
    if stop_id not in AVAILABLE_STOPS_SPACE:
        return False
        
    # ---> NEW: Use the helper <---
    bus_length = get_bus_length(bus_id)
    current_stop_length = AVAILABLE_STOPS_SPACE[stop_id]
    
    # print(f"{bus_id} want idle at {stop_id} the current available space {current_stop_length}:")
    result_value = current_stop_length - bus_length
    
    if result_value > bus_length:
        AVAILABLE_STOPS_SPACE[stop_id] = result_value
        # print(f"At time {traci.simulation.getTime()} {bus_id} allowed to park the update available space {result_value}:")
        return True
    print(f"\033[91m{bus_id} Not allowed to park at {stop_id} because the remaining space will not be enough to park another vehicle(space<bus_length) ({result_value} < {bus_length})\033[0m")
    return False

def release_idle_parking(bus_id, stop_id):
    """Restores the space when the bus leaves the idle state."""
    if stop_id in AVAILABLE_STOPS_SPACE:
        # ---> NEW: Use the helper <---
        bus_length = get_bus_length(bus_id)
        AVAILABLE_STOPS_SPACE[stop_id] += bus_length
        print(f"At time {traci.simulation.getTime()} {bus_id} left stop {stop_id} the update available space now is {AVAILABLE_STOPS_SPACE[stop_id]}:")

def find_next_open_stop(bus_id):
    """Finds the next nearest stop by DRIVING TIME (ensuring it is downstream)."""
    try:
        # Get exact driving edge
        current_edge = traci.vehicle.getRoadID(bus_id)
        if current_edge.startswith(":") or current_edge == "":
            route = traci.vehicle.getRoute(bus_id)
            idx = traci.vehicle.getRouteIndex(bus_id)
            current_edge = route[idx]
    except traci.exceptions.TraCIException:
        return None
        
    # Find out which stop we are currently at so we don't accidentally pick it again
    current_stop_id = None
    try:
        for s in traci.busstop.getIDList():
            if bus_id in traci.busstop.getVehicleIDs(s):
                current_stop_id = s
                break
    except:
        pass

    open_stops = []
    for stop_id in AVAILABLE_STOPS_SPACE.keys():
        if stop_id == current_stop_id:
            continue # Skip the stop that is already full!
            
        bus_length = get_bus_length(bus_id)
        
        # Check if it has space
        if (AVAILABLE_STOPS_SPACE[stop_id] - bus_length) > bus_length:
            try:
                lane_id = traci.busstop.getLaneID(stop_id)
                target_edge = lane_id.split('_')[0] 
                
                # ---> USE DRIVING TIME INSTEAD OF MATH.DIST <---
                cost = get_travel_time(current_edge, target_edge)
                
                # If there is a valid route, add it to our candidates
                if cost < float('inf'):
                    open_stops.append((cost, stop_id, target_edge))
            except:
                pass
                
    if open_stops:
        open_stops.sort() # Sort by lowest driving time!
        best_stop = open_stops[0][1]
        best_edge = open_stops[0][2] 
        
        # Note: We do NOT deduct the space here. 
        # The space will be deducted naturally when the bus arrives and triggers the listener!
        return best_stop, best_edge 
        
    return None 


def find_and_reserve_next_open_stop(bus_id):
    """Finds the next nearest stop that passes the True/False space check."""
    try:
        bus_pos = traci.vehicle.getPosition(bus_id)
    except traci.exceptions.TraCIException:
        return None
        
    open_stops = []
    for stop_id in AVAILABLE_STOPS_SPACE.keys():
        # ---> NEW: Use the helper <---
        bus_length = get_bus_length(bus_id)
        
        if (AVAILABLE_STOPS_SPACE[stop_id] - bus_length) > bus_length:
            try:
                lane_id = traci.busstop.getLaneID(stop_id)
                lane_shape = traci.lane.getShape(lane_id)
                dist = math.dist(bus_pos, lane_shape[0])
                edge_id = lane_id.split('_')[0] 
                open_stops.append((dist, stop_id, edge_id))
            except:
                pass
                
    if open_stops:
        open_stops.sort()
        best_stop = open_stops[0][1]
        best_edge = open_stops[0][2] 
        request_idle_parking(bus_id, best_stop)
        return best_stop, best_edge 
        
    return None
# ----------------------------------------------------------


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

def get_stops_from_edges(edge_sequence, bus_stops_dict):
    """
    Converts a sequence of road edges into a sequence of bus stops.
    It filters out any regular streets that don't have a stop on them.
    """
    stop_sequence = []
    
    for edge in edge_sequence:
        if edge in bus_stops_dict:
            # If this edge has a bus stop, add it to our list
            stop_sequence.append(bus_stops_dict[edge])
            
    return stop_sequence

def get_detailed_route_stops(edge_sequence, manifest, bus_stops_dict):
    """
    Converts a sequence of road edges into a sequence of bus stops,
    tagging them as Pickup, Dropoff, or Pass-through based on the manifest.
    """
    try:
        handled = traci.person.getTaxiReservations(12)
        waiting = traci.person.getTaxiReservations(3)
        res_map = {r.id: r for r in list(handled) + list(waiting)}
    except:
        res_map = {}

    pickup_stops = set()
    dropoff_stops = set()
    
    # Analyze the manifest to see what the bus intends to do
    seen_counts = {}
    total_counts = {r_id: manifest.count(r_id) for r_id in set(manifest)}
    
    for res_id in manifest:
        seen_counts[res_id] = seen_counts.get(res_id, 0) + 1
        if res_id not in res_map: continue
        res = res_map[res_id]
        
        if total_counts[res_id] == 2 and seen_counts[res_id] == 1:
            # First time seeing a double-entry -> Pickup
            stop_id = bus_stops_dict.get(res.fromEdge)
            if stop_id: pickup_stops.add(stop_id)
        else:
            # Second time, or single entry (already riding) -> Dropoff
            stop_id = bus_stops_dict.get(res.toEdge)
            if stop_id: dropoff_stops.add(stop_id)

    detailed_stops = []
    for edge in edge_sequence:
        if edge in bus_stops_dict:
            stop_id = bus_stops_dict[edge]
            # Tag the stop based on what the bus needs to do there
            if stop_id in pickup_stops and stop_id in dropoff_stops:
                detailed_stops.append(f"🔄 Pick&Drop[{stop_id}]")
            elif stop_id in pickup_stops:
                detailed_stops.append(f"🟢 Pick[{stop_id}]")
            elif stop_id in dropoff_stops:
                detailed_stops.append(f"🔴 Drop[{stop_id}]")
            else:
                detailed_stops.append(f"⏩ Pass[{stop_id}]")
                
    return detailed_stops


def optimize_route_sequence(bus_id, manifest, new_res=None, dropoff_weight=1):
    if not manifest:
        return []

    handled = traci.person.getTaxiReservations(12) 
    waiting = traci.person.getTaxiReservations(3)  
    all_res = list(handled) + list(waiting)
    res_map = {r.id: r for r in all_res}
    
    if new_res:
        res_map[new_res.id] = new_res

    needs_pickup = set()
    needs_dropoff = set()
    
    try:
        max_capacity = traci.vehicle.getPersonCapacity(bus_id)
    except traci.exceptions.TraCIException:
        max_capacity = 40 
        
    simulated_occupancy = 0
    
    unique_ids = set(manifest)
    for rid in sorted(unique_ids):
        if rid not in res_map:
            continue 
            
        state = res_map[rid].state
        if state == 8: 
            needs_dropoff.add(rid)
            simulated_occupancy += 1 
        else:
            needs_pickup.add(rid)
    
    # 1. Get the exact starting Edge and 1D Position of the bus
    current_edge = traci.vehicle.getRoadID(bus_id)
    try:
        current_pos = traci.vehicle.getLanePosition(bus_id)
    except traci.exceptions.TraCIException:
        current_pos = 0.0

    if current_edge.startswith(":") or current_edge == "": 
        try:
            route = traci.vehicle.getRoute(bus_id)
            idx = traci.vehicle.getRouteIndex(bus_id)
            current_edge = route[idx]
            current_pos = 0.0 # Just entered the edge
        except traci.exceptions.TraCIException:
            pass

    optimized_manifest = []
    
    while needs_pickup or needs_dropoff:
        best_action = None
        best_cost = float('inf')
        best_is_pickup = False
        target_edge_for_best = ""
        target_pos_for_best = 0.0
        
        # --- Check all possible PICKUPS ---
        if simulated_occupancy < max_capacity:
            for res_id in sorted(needs_pickup):
                if res_id in res_map:
                    target_edge = res_map[res_id].fromEdge
                    # Safely get the exact 1D depart position of the passenger on the edge
                    target_pos = getattr(res_map[res_id], 'departPos', 0.0)
                    
                    if current_edge == target_edge:
                        # They are on the same street!
                        if target_pos < current_pos:
                            # The bus has already driven past them! It must loop around the map.
                            cost = 999999 
                        else:
                            # Just drive straight ahead to reach them
                            cost = (target_pos - current_pos) / 10000.0 
                    else:
                        # They are on a different street. Use routing time + tie-breaker
                        cost = get_travel_time(current_edge, target_edge) + (target_pos / 10000.0)

                    if cost < best_cost:
                        best_cost = cost
                        best_action = res_id
                        best_is_pickup = True
                        target_edge_for_best = target_edge
                        target_pos_for_best = target_pos
                    
        # --- Check all possible DROP-OFFS ---
        for res_id in sorted(needs_dropoff):
            if res_id in res_map:
                target_edge = res_map[res_id].toEdge
                # Safely get the exact 1D arrival position of the passenger on the edge
                target_pos = getattr(res_map[res_id], 'arrivalPos', 0.0)
                
                if current_edge == target_edge:
                    if target_pos < current_pos:
                        cost = 999999 # Missed the stop, must loop around
                    else:
                        cost = (target_pos - current_pos) / 10000.0
                else:
                    cost = get_travel_time(current_edge, target_edge) + (target_pos / 10000.0)

                cost = cost * dropoff_weight

                if cost < best_cost:
                    best_cost = cost
                    best_action = res_id
                    best_is_pickup = False
                    target_edge_for_best = target_edge
                    target_pos_for_best = target_pos
                    
        if best_action is not None:
            optimized_manifest.append(best_action)
            
            # ---> Move virtual vehicle to new Edge AND new 1D position! <---
            current_edge = target_edge_for_best 
            current_pos = target_pos_for_best 
            
            if best_is_pickup:
                needs_pickup.remove(best_action)
                needs_dropoff.add(best_action) 
                simulated_occupancy += 1       
            else:
                needs_dropoff.remove(best_action)
                simulated_occupancy -= 1       
        else:
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

