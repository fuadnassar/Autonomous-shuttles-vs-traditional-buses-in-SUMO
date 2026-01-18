import xml.etree.ElementTree as ET
import os

def analyze_sumo_results(tripinfo_path, stats_path):
    if not os.path.exists(tripinfo_path):
        print(f"Error: {tripinfo_path} not found.")
        return

    tree = ET.parse(tripinfo_path)
    root = tree.getroot()

    waiting_times = []
    in_vehicle_times = []
    ride_distances = []
    ride_count = 0

    # 1. Analyze Person Trips (Rides)
    for person in root.findall('personinfo'):
        # Each person has multiple <ride> tags
        for ride in person.findall('ride'):
            veh_id = ride.get('vehicle', '')
            # Filter for your DRT fleet
            if "drt" in veh_id:
                ride_count += 1
                waiting_times.append(float(ride.get('waitingTime')))
                in_vehicle_times.append(float(ride.get('duration')))
                ride_distances.append(float(ride.get('routeLength')))

    # 2. Get Statistics from statistics.xml
    avg_system_delay = "N/A"
    if os.path.exists(stats_path):
        stats_tree = ET.parse(stats_path)
        stats_root = stats_tree.getroot()
        # For DRT, rideStatistics is the most reliable block
        ride_stats = stats_root.find('rideStatistics')
        if ride_stats is not None:
            avg_system_delay = ride_stats.get('waitingTime')


    # Inside your loop where you process rides:
    total_travel_times = []
    for ride in person.findall('ride'):
        wait = float(ride.get('waitingTime'))
        dur = float(ride.get('duration'))
        total_travel_times.append(wait + dur)

    avg_travel_time_s = sum(total_travel_times) / len(total_travel_times) if total_travel_times else 0


    # 3. Format and Print Results
    print("\n" + "="*45)
    print("       SUMO DRT SIMULATION RESULTS")
    print("="*45)
    print(f"Total Successful Rides      : {ride_count}")
    print(f"Avg Station Waiting Time [s]: {sum(waiting_times)/len(waiting_times):.2f}" if waiting_times else "0.00")
    print(f"Avg In-Vehicle Time [s]     : {sum(in_vehicle_times)/len(in_vehicle_times):.2f}" if in_vehicle_times else "0.00")
    print(f"Avg Total Travel Time [min] : {avg_travel_time_s / 60:.2f}")
    print(f"Total Passenger Dist [km]   : {sum(ride_distances)/1000:.2f}")
    print(f"Global Avg System Delay [s] : {avg_system_delay}")
    print("="*45 + "\n")

# Make sure these paths point to your actual files
analyze_sumo_results('./tripinfo.xml', './statistics.xml')