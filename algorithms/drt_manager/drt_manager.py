import argparse
import traci
import drt_manager_lib as lib
import drt_manager_listener as listener
import drt_manager_personal_plans as persons
def run(max_dropoff_delay, max_pickup_delay, realtime_requests_limit, demand_scale, use_gui):
    bus_stops = lib.get_bus_stops("as_stops.add.xml")
    
    # Check the flag to determine which binary to use
    sumo_binary = "sumo-gui" if use_gui else "sumo"
    
    traci.start([
        sumo_binary, 
        "-c", "sumo.sumocfg", 
        "--device.taxi.dispatch-algorithm", "traci"
        # ,"--delay","1000"
    ])
    

    active_reservations = set()
    bus_manifests = {}
    queue_list = []
    user_to_res_map = {}
    res_to_user_map = {}

    promised_pickup_times = {}
    waiting_for_pickup = set()
    all_eta_delays = []  
    
 # ---> NEW: Ensure data is cached only once <---
    data_initialized = False
    # pending_persons, master_database = persons.init_demand("./data/personal_planes.xlsx", scale=demand_scale)

    cleaner_listener = listener.drt_manager_Listener(
        bus_manifests,
        user_to_res_map,
        res_to_user_map, 
        # master_database,pending_persons
        )
    traci.addStepListener(cleaner_listener)
    
   

    # # # ==========================================================
    # # # ---> FIX: Inject people scheduled for Time 0 BEFORE the first step! <---
    # initial_time = traci.simulation.getTime() # This gets time 0.0
    # persons.check_and_inject_persons(initial_time, pending_persons)
    # # # ==========================================================


    previous_bus_routes = {}



    # while len(pending_persons) > 0 or len(traci.person.getIDList()) > 0:
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        buses = [v for v in traci.vehicle.getIDList() if traci.vehicle.getTypeID(v) == "arts"]
        
        # # ==========================================================
        # # ---> CHECK FOR ROUTE/PLAN CHANGES <---
        # for bus in buses:
        #     try:
        #         # Get the full sequence of edges
        #         current_route = traci.vehicle.getRoute(bus)
                
        #         # If the route is new or changed
        #         if previous_bus_routes.get(bus) != current_route:
        #             current_time = traci.simulation.getTime()
                    
        #             # ---> GRAB THE MANIFEST TO KNOW WHO IS GETTING ON/OFF <---
        #             manifest = bus_manifests.get(bus, [])
                    
        #             # -> NEW: Convert the edges into detailed bus stops <-
        #             planned_stops = lib.get_detailed_route_stops(current_route, manifest, bus_stops)
                    
        #             print("-----------------------------------------")
        #             print(f"\n🚍 [Time: {current_time}] Plan Changed for {bus}!")
        #             print(f"   -> Stop Sequence: {planned_stops}\n")
                    
        #             # Update tracker
        #             previous_bus_routes[bus] = current_route
        #     except traci.exceptions.TraCIException:
        #         pass 
        # # ==========================================================

        # # # ---> NEW: Fire the lib setup immediately when buses appear <---
        # if not data_initialized and len(buses) > 0:
        #     lib.init_simulation_data(buses)
        #     data_initialized = True
            
            
        current_time = traci.simulation.getTime()
        

        # try:
        #     persons.check_and_inject_persons(current_time, pending_persons)
        # except traci.exceptions.TraCIException as ex:
        #     print(f"TraCI Issue: {ex}")

        for bus in buses:
            try:
                riding_ids = traci.vehicle.getPersonIDList(bus)
                for uid in riding_ids:
                    if uid in waiting_for_pickup:
                        waiting_for_pickup.remove(uid)
                        promised_time = promised_pickup_times[uid]
                        eta_delay = current_time - promised_time
                        all_eta_delays.append(eta_delay)
            except traci.exceptions.TraCIException:
                pass

        waiting_reservations = traci.person.getTaxiReservations(3)
        
        for res in waiting_reservations[:realtime_requests_limit]:
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
                    manifest.append(res.id) 
                    manifest.append(res.id) 
                    
                    manifest = lib.optimize_route_sequence(bus, manifest, new_res=res, dropoff_weight=1.0)
            
                    traci.vehicle.dispatchTaxi(bus, manifest)
                    
                    bus_manifests[bus] = manifest
                    active_reservations.add(res.id)
                    user_to_res_map[user_id] = res.id   
                    res_to_user_map[res.id] = user_id
                    
                    eta_seconds = lib.get_pickup_eta(bus, manifest, res)
                    eta_minutes = round(eta_seconds / 60, 1)
                    
                    promised_pickup_times[user_id] = current_time + eta_seconds
                    waiting_for_pickup.add(user_id)
                    
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
    
    if all_eta_delays:
        avg_drift = sum(all_eta_delays) / len(all_eta_delays)
        print("\n" + "="*45)
        print(f"📉 ALGORITHM ACCURACY: AVG ETA DELAY = {round(avg_drift, 2)} seconds")
        print("="*45 + "\n")

    # # ==========================================
    # # FINAL KPIs
    # # ==========================================
    # if master_database:
    #     total_start_walks = sum(data.get('start_walk_distance', 0) for data in master_database.values())
    #     total_end_walks = sum(data.get('end_walk_distance', 0) for data in master_database.values())
    #     total_walk_distance = total_start_walks + total_end_walks
        
    #     # Multiply by 2 because everyone does a start walk and an end walk (2 legs per person)
    #     avg_walk = total_walk_distance / (len(master_database) * 2) 
        
    #     print("\n" + "="*45)
    #     print(f"🚶 PEDESTRIAN KPI: AVG WALK DISTANCE = {round(avg_walk, 2)} meters per leg")
    #     print("="*45 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the DRT Manager Simulation.")
    
    # Add your existing parameters
    parser.add_argument("-d", "--dropoff-delay", type=float, default=60, 
                        help="Maximum dropoff delay in seconds (default: 60)")
                        
    parser.add_argument("-p", "--pickup-delay", type=float, default=120, 
                        help="Maximum pickup delay in seconds (default: 120)")
                        
    parser.add_argument("-l", "--rt-limit", type=int, default=2, 
                        help="Max reservations to process per step; None process all (default: 2)")
    
    parser.add_argument("-s", "--scale", type=int, default=1, 
                        help="Scale demand by multiplying trips (default: 1)")

    parser.add_argument("-gui", action="store_true", 
                        help="Run the simulation with the SUMO GUI (default is headless SUMO)")

    # Parse the arguments from the terminal
    args = parser.parse_args()

    # Pass all terminal arguments into your run function, including the GUI flag
    run(max_dropoff_delay=args.dropoff_delay, 
        max_pickup_delay=args.pickup_delay, 
        realtime_requests_limit=args.rt_limit,
        demand_scale=args.scale,
        use_gui=args.gui)