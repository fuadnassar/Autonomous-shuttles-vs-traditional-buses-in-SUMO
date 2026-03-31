import xml.etree.ElementTree as ET

# Analysis results: (start_time, interval)
patterns = {
    "Bus_156_Freiham": {"start": 0.0, "interval": 600.0, "from": "E18", "to": "E67", "via": "E25 E36 E37 E30 E32 E39 E43 E44 E53 E64 E62 E63 E19 E20 E65 E70 E71", "stops": [("bs_0", 21), ("bs_1", 105), ("bs_2", 155), ("bs_3", 202), ("bs_4", 261), ("bs_5", 311), ("bs_6", 358), ("bs_7", 406), ("bs_8", 462), ("bs_9", 513)]},
    "Bus_157_Aubing": {"start": 0.0, "interval": 600.0, "from": "-E71", "to": "-E8", "via": "-E70 -E65 -E16 -E15 -E0 E10 E11 E6 -E52 -E50 E44 -E42 -E41 -E24 -E23 -E22 -E25 -E18", "stops": [("bs_39", 35), ("bs_38", 90), ("bs_36", 138), ("bs_32", 198), ("bs_34", 246), ("bs_31", 292), ("bs_4", 343), ("bs_28", 393), ("bs_24", 445), ("bs_42", 504)]},
    "Bus_157_Freiham": {"start": 180.0, "interval": 600.0, "from": "E8", "to": "E71", "via": "E18 E25 E22 E23 E24 E41 E42 -E49 E50 E52 -E6 -E11 -E10 E0 E15 E16 E65 E70", "stops": [("bs_15", 21), ("bs_17", 81), ("bs_21", 134), ("bs_23", 183), ("bs_14", 238), ("bs_13", 286), ("bs_12", 332), ("bs_11", 393), ("bs_7", 442), ("bs_8", 498)]},
    "Bus_156_Aubing": {"start": 300.0, "interval": 600.0, "from": "-E67", "to": "-E18", "via": "-E71 -E70 -E65 -E20 -E19 -E63 -E62 -E64 -E53 -E49 -E43 -E39 -E32 -E30 -E37 -E36 -E25", "stops": [("bs_40", 44), ("bs_39", 95), ("bs_38", 150), ("bs_35", 197), ("bs_33", 242), ("bs_29", 294), ("bs_44", 357), ("bs_25", 404), ("bs_26", 454), ("bs_41", 537)]},
    "Bus_143_Aubing": {"start": 360.0, "interval": 600.0, "from": "-E46", "to": "-E7", "via": "-E28 -E27 E29 -E37 -E36 -E25 -E18 -E8", "stops": [("bs_22", 21), ("bs_27", 103), ("bs_26", 160), ("bs_43", 259)]},
    "Bus_57_Aubing": {"start": 360.0, "interval": 420.0, "from": "-E17", "to": "-E2", "via": "-E63 -E62 -E64 -E53 -E42 -E41 -E24 -E23 -E22 -E25 -E18 -E8 -E7", "stops": [("bs_37", 31), ("bs_35", 82), ("bs_33", 127), ("bs_30", 178), ("bs_28", 225), ("bs_24", 277), ("bs_45", 356)]},
    "Bus_143_Freiham": {"start": 540.0, "interval": 600.0, "from": "E7", "to": "E46", "via": "E8 E18 E25 E36 E37 -E29 E27 E28", "stops": [("bs_1", 99), ("bs_19", 154), ("bs_20", 234)]},
    "Bus_57_Freiham": {"start": 540.0, "interval": 420.0, "from": "E2", "to": "E17", "via": "E7 E8 E18 E25 E22 E23 E24 E41 E42 E53 E64 E62 E63", "stops": [("bs_18", 21), ("bs_17", 93), ("bs_21", 145), ("bs_23", 193), ("bs_5", 244), ("bs_6", 290), ("bs_10", 338)]}
}

def generate():
    end_time = 61200
    with open("generate_bus_trips.rou.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        # Insert vTypes here as requested in previous turn...
        
        trip_id = 0
        all_trips = []
        
        for name, p in patterns.items():
            current_time = p["start"]
            while current_time <= end_time:
                all_trips.append((current_time, name, p))
                current_time += p["interval"]
        
        # Sort by departure time for XML consistency
        all_trips.sort(key=lambda x: x[0])
        
        for depart, name, p in all_trips:
            f.write(f'    <trip id="b_{trip_id}" type="{name}" depart="{depart:.2f}" from="{p["from"]}" to="{p["to"]}" via="{p["via"]}">\n')
            for b_stop, offset in p["stops"]:
                f.write(f'        <stop busStop="{b_stop}" duration="20.00" until="{(depart + offset):.2f}"/>\n')
            f.write('    </trip>\n')
            trip_id += 1
            
        f.write('</routes>')

if __name__ == "__main__":
    generate()