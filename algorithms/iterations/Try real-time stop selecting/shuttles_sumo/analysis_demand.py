import xml.etree.ElementTree as ET
import math
from collections import defaultdict

def analyze_drt_demand(persons_file, avg_trip_time_sec=600, effective_capacity=15):
    """
    Analyzes SUMO demand to recommend DRT dispatcher settings.
    
    :param persons_file: Path to persons.rou.xml
    :param avg_trip_time_sec: Estimate of how long an average direct trip takes in seconds.
    :param effective_capacity: Realistic average occupancy limit before deviations become too severe.
                               (Even though your arts capacity is 40, effective is usually much lower).
    """
    try:
        tree = ET.parse(persons_file)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: Could not find {persons_file}")
        return

    demand_timeline = []
    
    # Extract all departure times from the persons file
    for person in root.findall('person'):
        depart_time = float(person.get('depart', 0))
        # Ensure they actually use the taxi/drt line
        for ride in person.findall('ride'):
            if ride.get('lines') == 'taxi':
                demand_timeline.append(depart_time)
                break
        
    if not demand_timeline:
        print("No DRT/taxi demand found in the file!")
        return

    demand_timeline.sort()
    total_requests = len(demand_timeline)
    
    # Group demand into 1-hour (3600s) bins to find the peak hour
    bins = defaultdict(int)
    for t in demand_timeline:
        bin_idx = int(t // 3600)
        bins[bin_idx] += 1
        
    peak_hour_demand = max(bins.values()) if bins else 0
    peak_hour_idx = max(bins, key=bins.get) if bins else 0

    # 1. Fleet Size Calculation (Little's Law variation)
    # Fleet = (Peak Demand per hour * Avg Trip Time in hours) / Effective Capacity
    avg_trip_time_hours = avg_trip_time_sec / 3600.0
    active_vehicles_needed = (peak_hour_demand * avg_trip_time_hours) / effective_capacity
    
    # Add a 25% buffer for repositioning, traffic delays, and deadheading
    recommended_fleet = math.ceil(active_vehicles_needed * 1.25)
    
    # 2. Delays Calculation
    # We evaluate requests per minute during the peak hour to determine density
    demand_rate_per_min = peak_hour_demand / 60.0
    
    # High density -> vehicles fill up fast, shorter delays needed
    if demand_rate_per_min > 5:
        max_pickup = 180   # 3 mins
        max_dropoff = 180
    # Medium density -> balanced approach (similar to your current 240s)
    elif demand_rate_per_min > 1:
        max_pickup = 300   # 5 mins
        max_dropoff = 300
    # Low density -> allow longer delays so algorithm can pool distant users
    else:
        max_pickup = 480   # 8 mins
        max_dropoff = 600  # 10 mins

    print(f"========== DRT DEMAND ANALYSIS ==========")
    print(f"Total Requests Processed: {total_requests}")
    print(f"Peak Hour Demand: {peak_hour_demand} requests (occurred during hour {peak_hour_idx})")
    print(f"Assumed Avg Trip Time: {avg_trip_time_sec}s | Effective Bus Capacity: {effective_capacity}")
    print("=========================================\n")
    
    print("🎯 RECOMMENDED CONFIGURATION:")
    print(f"► Number of Fleet:      {max(1, recommended_fleet)} buses")
    print(f"► max_pickup_delay:     {max_pickup} seconds")
    print(f"► max_dropoff_delay:    {max_dropoff} seconds")
    print("\n-----------------------------------------")
    print("How to apply this:")
    print(f"1. In arts.rou.xml, update <flow id=\"drt\" ... number=\"{max(1, recommended_fleet)}\">")
    print(f"2. In drt_manager.py, set max_pickup_delay={max_pickup} and max_dropoff_delay={max_dropoff}")

if __name__ == "__main__":
    # You can tweak 600 (10 mins) to your network's actual average trip time
    analyze_drt_demand("persons.rou.xml", avg_trip_time_sec=600, effective_capacity=15)