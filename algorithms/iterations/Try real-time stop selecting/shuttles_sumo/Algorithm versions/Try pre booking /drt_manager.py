import traci
import pandas as pd
import drt_manager_lib as lib
import drt_manager_listener as listener

def run():
    # 1. Load Bus Stops and Create Reverse Mapping
    bus_stops = lib.get_bus_stops("as_stops.add.xml")
    stop_details = lib.get_stop_details("as_stops.add.xml")
    stop_to_edge = {stop_id: edge for edge, stop_id in bus_stops.items()}

    # 2. Load Excel Data and Group by Departure Time
    print("Loading trips from Excel...")
    df = pd.read_excel("./data/new_table.xlsx")
    trips_by_time = {}
    for _, row in df.iterrows():
        dep_time = int(row['departure_time'])
        if dep_time not in trips_by_time:
            trips_by_time[dep_time] = []
        trips_by_time[dep_time].append(row.to_dict())
    
    # Optional: Find the last departure time to know when we can safely stop the simulation
    max_depart_time = max(trips_by_time.keys()) if trips_by_time else 0

    traci.start([
        "sumo", 
        "-c", "sumo.sumocfg", 
        "--device.taxi.dispatch-algorithm", "traci"
        # ,"--delay","1000"
    ])
    
    max_dropoff_delay=60
    max_pickup_delay=120


    active_reservations = set()
    bus_manifests = {}
    queue_list = []
    user_to_res_map = {}
    res_to_user_map = {}

    # ---> NEW: ETA Tracking Variables <---
    promised_pickup_times = {}
    waiting_for_pickup = set()
    all_eta_delays = []  # Stores the (68 - 40) differences
    # ------------------------------------

    cleaner_listener = listener.ManifestCleanerListener(bus_manifests,user_to_res_map,res_to_user_map)
    traci.addStepListener(cleaner_listener)
    
    while traci.simulation.getTime() <= max_depart_time or traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        buses = [v for v in traci.vehicle.getIDList() if traci.vehicle.getTypeID(v) == "arts"]
        current_time = traci.simulation.getTime()
        

        # ---> NEW: DYNAMIC ON-THE-FLY INSERTION <---
        if current_time in trips_by_time:
            for trip in trips_by_time[current_time]:
                try:
                    p_id = trip["person_id"]
                    o_pickup = trip["origin_selected_pickup"]
                    d_dropoff = trip["destination_selected_dropoff"]
                    d_pickup = trip["destination_selected_pickup"]
                    o_dropoff = trip["origin_selected_dropoff"]
                    act_dur = trip["activity_duration"]
                    
                    # Call the function from the library and pass stop_to_edge!
                    lib.insert_person(
                        person_id=p_id,
                        depart_time=current_time,
                        origin_pickup=o_pickup,
                        dest_dropoff=d_dropoff,
                        dest_pickup=d_pickup,
                        origin_dropoff=o_dropoff,
                        activity_dur=act_dur,
                        stop_details=stop_details 
                    )
                    
                except traci.exceptions.TraCIException as e:
                    print(f"❌ Failed to insert {p_id}: {e}")
        # -------------------------------------------


        # ---> NEW: BOARDING DETECTOR (Calculates the Delay) <---
        for bus in buses:
            try:
                # Get the IDs of everyone physically sitting in this bus right now
                riding_ids = traci.vehicle.getPersonIDList(bus)
                for uid in riding_ids:
                    if uid in waiting_for_pickup:
                        # They just stepped onto the bus! Calculate the drift.
                        waiting_for_pickup.remove(uid)
                        promised_time = promised_pickup_times[uid]
                        
                        # Actual Time - Promised Time = Delay (Drift)
                        eta_delay = current_time - promised_time
                        all_eta_delays.append(eta_delay)
                        
                        # print(f"👋 Passenger {uid} picked up! (ETA Delay: {round(eta_delay, 1)} seconds)")
            except traci.exceptions.TraCIException:
                pass
        # -------------------------------------------------------

        waiting_reservations = traci.person.getTaxiReservations(3)


        for res in waiting_reservations[:2]:
            if res.id in active_reservations:
                continue
                    
            user_id = res.persons[0]
            sorted_buses = lib.get_marginal_cost_sorted_buses(
                res, buses, bus_manifests, 
                current_time=current_time, 
                promised_pickup_times=promised_pickup_times,
                res_to_user_map=res_to_user_map,
                max_dropoff_delay=max_dropoff_delay, 
                max_pickup_delay=max_pickup_delay,
                
            )


            assigned_successfully = False
            for bus in sorted_buses:
                current_manifest = bus_manifests.get(bus, [])
                total_assigned_people = len(set(current_manifest)) 
                
                try:
                    capacity = traci.vehicle.getPersonCapacity(bus) 
                except:
                    capacity = 40
                
                effective_limit = capacity

                if total_assigned_people >= (effective_limit):
                    continue
                
                try:
                    manifest = bus_manifests.get(bus, [])
                    manifest.append(res.id) # Pickup
                    manifest.append(res.id) # Drop-off
                    
                    manifest = lib.optimize_route_sequence(bus, manifest, new_res=res, dropoff_weight=1.0)
            
                    traci.vehicle.dispatchTaxi(bus, manifest)
                    
                    bus_manifests[bus] = manifest
                    active_reservations.add(res.id)
                    user_to_res_map[user_id] = res.id   
                    res_to_user_map[res.id] = user_id
                    
                    # ---> NEW: RECORD THE PROMISE <---
                    eta_seconds = lib.get_pickup_eta(bus, manifest, res)
                    eta_minutes = round(eta_seconds / 60, 1)
                    
                    # Calculate exactly what clock time they should be picked up
                    promised_pickup_times[user_id] = current_time + eta_seconds
                    waiting_for_pickup.add(user_id)
                    # ----------------------------------
                    
                    # print(f"✅ Assigned {user_id} (Res: {res.id}) to {bus}.")
                    # print(f"   --> 🕒 ETA to Pickup: {eta_seconds} seconds ({eta_minutes} mins).")
                    print(f"   --> 🗺️{bus} Current Plan: {manifest}")

                    assigned_successfully = True
                    break
                    
                except traci.exceptions.TraCIException as e:
                    print(f"Failed to assign {user_id} to {bus}: {e}")

            if not assigned_successfully:
                if user_id not in queue_list:
                    queue_list.append(user_id)
                    print(f"All buses are full! User {user_id} added to queue.")

    traci.close()
    
    # ---> NEW: PRINT FINAL AVERAGE ETA DRIFT <---
    if all_eta_delays:
        avg_drift = sum(all_eta_delays) / len(all_eta_delays)
        print("\n" + "="*45)
        print(f"📉 ALGORITHM ACCURACY: AVG ETA DELAY = {round(avg_drift, 2)} seconds")
        print("="*45 + "\n")

if __name__ == "__main__":
    run()