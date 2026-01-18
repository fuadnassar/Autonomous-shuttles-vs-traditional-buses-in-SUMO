import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

# --- Path Configuration ---
DATA_DIR = Path("../Data/Step_1/results")
OUTPUT_DIR = Path(".") # Assuming running from 'output' folder

FILE_HOME_SHOP = DATA_DIR / "Home_shopping_person_info.xlsx"
FILE_SHOP_HOME = DATA_DIR / "Shopping_home_person_info.xlsx"
TRIPINFO_FILE = OUTPUT_DIR / "tripinfo.xml"

def get_demand_kpis():
    """Extracts accessibility KPIs from the Person Info Excel files."""
    try:
        # Load the demand data from your Excel files
        df1 = pd.read_excel(FILE_HOME_SHOP)
        df2 = pd.read_excel(FILE_SHOP_HOME)
        df_combined = pd.concat([df1, df2])
        
        # Calculating Waiting Time based on your image columns: 
        # (Bus Arrival at Start Stop) - (Person Arrival at Start Stop)
        wait_times = df_combined['bus_arrival_start_stop'] - df_combined['person_arrival_start_stop']
        
        metrics = {
            "Avg Walk Distance [m]": (df_combined['start_walk_distance'] + df_combined['end_walk_distance']).mean(),
            "Avg Walk Time [s]": (df_combined['start_walk_time'] + df_combined['end_walk_time']).mean(),
            "Avg Station Waiting Time [s]": wait_times.mean(),
            "Total Demand [Trips]": len(df_combined)
        }
        return metrics
    except Exception as e:
        print(f"Error reading Excel files: {e}")
        return None

def get_sumo_output_kpis():
    """Extracts operational KPIs from SUMO tripinfo.xml."""
    if not TRIPINFO_FILE.exists():
        print(f"Warning: {TRIPINFO_FILE} not found.")
        return {}
    
    tree = ET.parse(TRIPINFO_FILE)
    root = tree.getroot()
    
    # Extracting raw data from XML attributes
    durations = [float(t.get("duration")) for t in root.findall("tripinfo")]
    lengths = [float(t.get("routeLength")) for t in root.findall("tripinfo")]
    delays = [float(t.get("timeLoss")) for t in root.findall("tripinfo")]
    
    # Calculations
    total_trips = len(durations)
    if total_trips == 0:
        return {}

    avg_travel_time_min = (sum(durations) / total_trips) / 60  # seconds to minutes
    total_dist_km = sum(lengths) / 1000                        # meters to kilometers
    
    return {
        "Avg Travel Time [min]": avg_travel_time_min,
        "Total Distance [km]": total_dist_km,
        "Avg In-Vehicle Time [s]": sum(durations) / total_trips,
        "Avg System Delay [s]": sum(delays) / total_trips
    }

# --- Execution ---
demand_stats = get_demand_kpis()
simulation_stats = get_sumo_output_kpis()

# Combine into a clean table
kpi_list = []

# Add Demand Metrics
if demand_stats:
    for k, v in demand_stats.items():
        kpi_list.append({"Category": "User Accessibility", "KPI": k, "Bus (Current)": round(v, 2), "ARTS (Future)": 0})

# Add Simulation Metrics (including your new KPIs)
for k, v in simulation_stats.items():
    kpi_list.append({"Category": "System Performance", "KPI": k, "Bus (Current)": round(v, 2), "ARTS (Future)": 0})

# Create final DataFrame
df_midterm = pd.DataFrame(kpi_list)

# Save to CSV for easy import to Excel
df_midterm.to_csv("midterm_consolidated_kpis.csv", index=False)

print("\n=== CONSOLIDATED MIDTERM ANALYSIS (FREIHAM-NORD) ===")
print(df_midterm.to_string(index=False))
print("\n[Output] Results saved to: midterm_consolidated_kpis.csv")