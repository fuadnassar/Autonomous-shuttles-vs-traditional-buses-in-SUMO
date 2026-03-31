import traci
import drt_manager_lib as lib

class drt_manager_Listener(traci.StepListener):
    def __init__(self, bus_manifests, user_to_res_map, res_to_user_map, master_database, pending_persons):
        self.bus_manifests = bus_manifests
        self.user_to_res_map = user_to_res_map
        self.res_to_user_map = res_to_user_map
        
        # ---> NEW: Store references to the databases <---
        self.master_database = master_database
        self.pending_persons = pending_persons
        
        # Maps bus_id -> stop_id to remember where they parked and release space later
        self.idle_parked_buses = {}
    
    def step(self, t=0):
        current_time = traci.simulation.getTime()

        # =================================================================
        # NEW: Catch arriving Outbound people and schedule Return!
        # =================================================================
        arrived_people = traci.simulation.getArrivedPersonIDList()
        for p_id in arrived_people:
            if p_id.endswith("_out"):
                original_id = p_id.replace("_out", "") 
                p_data = self.master_database.get(original_id)
                
                if p_data:
                    act_dur = p_data.get('activity_duration', 0)
                    end_walk = p_data.get('end_walk_time', 0)
                    
                    # Exact return time calculation
                    return_time = int(current_time + act_dur + (2 * end_walk))
                    
                    return_trip_data = p_data.copy()
                    return_trip_data['trip_type'] = 'return'
                    
                    if return_time not in self.pending_persons:
                        self.pending_persons[return_time] = []
                    self.pending_persons[return_time].append(return_trip_data)
                    
                    # print(f"🕒 {original_id} arrived at {current_time}s! Scheduled return trip at {return_time}s.")
        # =================================================================

        buses = [v for v in traci.vehicle.getIDList() if traci.vehicle.getTypeID(v) == "arts"]
        active_persons = set(traci.person.getIDList())

        for bus in buses:
            current_plan = self.bus_manifests.get(bus, [])
            
            # ==========================================
            # IDLE PARKING LOGIC
            # ==========================================
            if not current_plan:
                if bus not in self.idle_parked_buses or self.idle_parked_buses[bus] == "ROAD_PARKING":
                    # Bus just became empty! Find out which stop it is currently at
                    current_stop = None
                    try:
                        all_stops = traci.busstop.getIDList()
                        for s in all_stops:
                            if bus in traci.busstop.getVehicleIDs(s):
                                current_stop = s
                                break
                    except traci.exceptions.TraCIException:
                        pass
                        
                    if current_stop:
                        # Send idle request to our list cache
                        can_park = lib.request_idle_parking(bus, current_stop)
                        
                        if can_park:
                            self.idle_parked_buses[bus] = current_stop
                            
                        else:
                            # ---> NEW: Unpack the tuple from our new driving-time function <---
                            next_stop_info = lib.find_next_open_stop(bus)
                            if next_stop_info:
                                next_stop, next_edge = next_stop_info
                                print(f"next_stop:{next_stop}, next_edge:{next_edge}")

                                # 1. Mark as driving so the system waits for it to arrive
                                self.idle_parked_buses[bus] = "ROAD_PARKING" 
                                
                                try:
                                    # 2. Wake it up to force it out of the full stop!
                                    traci.vehicle.resume(bus)
                                    
                                    # 3. Route it to the target downstream edge
                                    traci.vehicle.changeTarget(bus, next_edge)
                                    
                                    # 4. Command the off-road park when it gets there
                                    traci.vehicle.setBusStop(bus, next_stop, duration=3600, flags=1)
                                    print(f"⚠️ Stop {current_stop} full! {bus} driving downstream to {next_stop}...")
                                except traci.exceptions.TraCIException:
                                    pass
                    else:
                        # The bus is empty but NOT at any bus stop (e.g., spawned at E5).
                        self.idle_parked_buses[bus] = "ROAD_PARKING"

                continue # Skip manifest cleanup since it's empty
            else:
                # If it HAS a plan but was previously parked, release the space!
                if bus in self.idle_parked_buses:
                    parked_location = self.idle_parked_buses[bus]
                    
                    if parked_location != "ROAD_PARKING":
                        lib.release_idle_parking(bus, parked_location)
                        
                    del self.idle_parked_buses[bus]

            # ==========================================
            # MANIFEST CLEANUP LOGIC (Original)
            # ==========================================
            passenger_ids = traci.vehicle.getPersonIDList(bus)
            onboard_res_ids = {self.user_to_res_map.get(uid) for uid in passenger_ids}
            # print(f"passenger_ids:{passenger_ids}")
            # print(f"onboard_res_ids:{onboard_res_ids}")
            cleaned_plan = []
            alive_ids = set()
            dead_ids = set()
            
            total_counts = {r_id: current_plan.count(r_id) for r_id in set(current_plan)}
            seen_counts = {}
            # print(f"{bus} current_plan:{current_plan}")

            for res_id in current_plan:
                seen_counts[res_id] = seen_counts.get(res_id, 0) + 1
                
                if res_id in onboard_res_ids:
                    if total_counts[res_id] == 2 and seen_counts[res_id] == 1:
                        continue 
                    cleaned_plan.append(res_id)
                    continue
                    
                is_alive = False
                
                if res_id in alive_ids:
                    is_alive = True
                elif res_id in dead_ids:
                    is_alive = False
                else:
                    person_id = self.res_to_user_map.get(res_id)
                    
                    # ---> FIX: Check if they vanished BEFORE asking SUMO! <---
                    if person_id not in active_persons:
                        dead_ids.add(res_id)
                    else:
                        try:
                            stage = traci.person.getStage(person_id)
                            if stage.type == 3: 
                                alive_ids.add(res_id)
                                is_alive = True
                            else:
                                dead_ids.add(res_id) 
                        except traci.exceptions.TraCIException:
                            dead_ids.add(res_id) 
                
                if is_alive:
                    cleaned_plan.append(res_id)
            
            self.bus_manifests[bus] = cleaned_plan

        return True