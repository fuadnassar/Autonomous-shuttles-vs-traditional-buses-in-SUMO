import traci

class ManifestCleanerListener(traci.StepListener):
    def __init__(self, bus_manifests, user_to_res_map, res_to_user_map):
        self.bus_manifests = bus_manifests
        self.user_to_res_map = user_to_res_map
        self.res_to_user_map = res_to_user_map
    

    def step(self, t=0):
        buses = [v for v in traci.vehicle.getIDList() if traci.vehicle.getTypeID(v) == "arts"]
        current_time=traci.simulation.getTime()
        # print(f"--------------( {current_time} )-------------")
        # if(traci.simulation.getTime==10190 or traci.simulation.getTime==2600):
            # print(f"--------------( {self.user_to_res_map} )-------------")
  
        

        for bus in buses:
            current_plan = self.bus_manifests.get(bus, [])
            
            if not current_plan:
                continue

            # Check who is physically sitting in the bus right now
            passenger_ids = traci.vehicle.getPersonIDList(bus)
            onboard_res_ids = {self.user_to_res_map.get(uid) for uid in passenger_ids}
            
            # print(f"passenger_ids: {passenger_ids}")
            # print(f"onboard_res_ids: {onboard_res_ids}")
            # print(f"current_plan: {current_plan}")

            cleaned_plan = []
            alive_ids = set()
            dead_ids = set()
            
            # --- NEW: Pre-calculate counts to differentiate Pickups and Drop-offs ---
            total_counts = {r_id: current_plan.count(r_id) for r_id in set(current_plan)}
            seen_counts = {}

            for res_id in current_plan:
                # Count how many times we have looked at this ID in the loop so far
                seen_counts[res_id] = seen_counts.get(res_id, 0) + 1
                
                # 1. If they are physically inside the bus:
                if res_id in onboard_res_ids:
                    # If they are in the plan TWICE, and this is the FIRST time seeing it...
                    # This is the Pickup action! Skip it to delete it from the new list.
                    if total_counts[res_id] == 2 and seen_counts[res_id] == 1:
                        continue 
                        
                    # Otherwise, keep it! (This preserves the Drop-off action perfectly)
                    cleaned_plan.append(res_id)
                    continue
                    
                # 2. If they are NOT inside the bus (Waiting or Finished)
                is_alive = False
                
                # Check our fast cache first
                if res_id in alive_ids:
                    is_alive = True
                elif res_id in dead_ids:
                    is_alive = False
                else:
                    # If not in cache, ask SUMO their exact stage
                    person_id = self.res_to_user_map.get(res_id)
                    try:
                        stage = traci.person.getStage(person_id)
                        
                        # Stage Type 3 means "Waiting for a ride"
                        if stage.type == 3: 
                            alive_ids.add(res_id)
                            is_alive = True
                        else:
                            # If they are walking or finished, the trip is over
                            dead_ids.add(res_id) 
                            
                    except traci.exceptions.TraCIException:
                        # If they vanished from the simulation entirely
                        dead_ids.add(res_id) 
                
                # If they are alive and waiting on the sidewalk, keep them in the plan!
                if is_alive:
                    cleaned_plan.append(res_id)
            
            # Update the main dictionary invisibly!
            self.bus_manifests[bus] = cleaned_plan
            # print(f"cleaned_plan: {cleaned_plan}")

        return True