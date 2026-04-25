# DRT Manager

DRT Manager is a high-performance dispatching algorithm developed by Fuad Nassar during his master thesis at TUM to operate Dynamic Autonomous Stop-Based Transit (DAST) system.

It is designed to efficiently handle high-density demand, serving 5,000–15,000 daily trips using a limited fleet of midi-sized autonomous buses.





<table align="center">
  <tr>
    <td><img src="https://github.com/user-attachments/assets/b1bbe5c9-da0a-4ddd-aed6-ca5028e9145e" height="260"/></td>
    <td>&nbsp;</td>
    <td><img src="https://github.com/user-attachments/assets/b845b4f4-69c7-45e2-83ce-135879731387" height="260"/></td>
    <td>&nbsp;</td>
     <td><img src="https://github.com/user-attachments/assets/5ef2b672-d861-4d96-80a5-5343ccd62506" height="260"/></td>
    <td>&nbsp;</td>
     <td><img src="https://github.com/user-attachments/assets/0f790477-0189-4be6-bbb3-9f923fcc356e" height="260"/></td>
    <td>&nbsp;</td>
    <td><img src="https://github.com/user-attachments/assets/6f1827b2-c597-46e7-85d7-3663e1252a39" height="260"/></td>
  </tr>
</table>





# Algorithm Overview

DRT Manager is a deterministic, event-driven algorithm that maximizes computational efficiency by leveraging asynchronous event listeners, utilizing principles comparable to WebSocket protocols.

The system combines:

- Event-driven execution (listener-based)
- Cached system state for constant-time access
- Constraint-based dispatching
- Marginal cost optimization
- Dynamic route sequencing

This structure enables stable operation under high load with minimal fleet resources.

---
# Usage

Run the simulation:

```bash
python drt_manager.py --dropoff-delay 60 --pickup-delay 120 
```

Run with GUI:

```bash
python drt_manager.py --gui
```

---

# Arguments

The DRT Manager can be configured using the following command-line arguments. 

| Argument | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `--dropoff-delay` | `int` | `60` | Maximum acceptable delay (in seconds) for passenger drop-offs. |
| `--pickup-delay` | `int` | `120` | Maximum acceptable delay (in seconds) for passenger pickups. |
| `--gui` | `flag` | `False` | Launches the simulation using the SUMO-GUI instead of the command-line version. |
| `--help`, `-h` | `flag` | `-` | Displays the help message and lists all available command-line arguments. |

---
# Important Parts of the Code

## Event Listener (Real-Time Engine)

The algorithm uses a step-based listener similar to WebSocket-driven systems, allowing continuous updates of system state.

```python
class drt_manager_Listener(traci.StepListener):
    def step(self, t=0):
        # Executes every simulation step
        return True
```

Advantages:

- Immediate reaction to events  
- No polling overhead  
- Scalable under high demand  
- Continuous synchronization  

---

## Cached System State

Global caching is used to eliminate repeated computations and improve performance.

```python
AVAILABLE_STOPS_SPACE = {}
BUS_LENGTHS = {}
ROUTE_CACHE = {}
```

Example:

```python
def get_travel_time(start_edge, end_edge):
    if (start_edge, end_edge) not in ROUTE_CACHE:
        route = traci.simulation.findRoute(start_edge, end_edge)
        ROUTE_CACHE[(start_edge, end_edge)] = route.travelTime
    return ROUTE_CACHE[(start_edge, end_edge)]
```

---

## Constraint-Based Dispatching

All assignments are validated using strict service constraints.

```python
if delay > max_dropoff_delay:
    is_valid = False
```

Constraints include:

- Maximum pickup delay  
- Maximum drop-off delay  
- Vehicle capacity  

---

## Marginal Cost Optimization

Vehicle selection is based on minimizing system-wide cost increase.

```python
margin = new_total_time - base_total_time
```

Only valid and efficient assignments are accepted.

---

## Dynamic Route Optimization

Each vehicle maintains a continuously optimized route (manifest).

```python
manifest = optimize_route_sequence(bus, manifest, new_res)
```

Features:

- Pickup and drop-off sequencing  
- Capacity-aware routing  
- Travel-time-based decisions  

---

## Idle Vehicle Management

Idle vehicles are dynamically redistributed to avoid congestion.

```python
def request_idle_parking(bus_id, stop_id):
    if available_space > bus_length:
        return True
```

If a stop is full:

```python
next_stop = find_next_open_stop(bus_id)
```

---

# Using DRT Manager in Another City

## 1. Replace Network

Update SUMO configuration files:

- `sumo.sumocfg`
- Network (`.net.xml`)
- Stops (`.add.xml`)

---

## 2. Load Stops

```python
bus_stops = lib.get_bus_stops("your_stops.xml")
```

---

## 3. Configure Fleet

```python
buses = [v for v in traci.vehicle.getIDList() if traci.vehicle.getTypeID(v) == "arts"]
```

---

## 4. Inject Demand

```python
traci.person.add(person_id, edge, pos=pos)
traci.person.appendDrivingStage(person_id, destination_edge, "taxi")
```

Supported demand types:

- synthetic demand  
- external datasets  
- predefined schedules  

---

# Performance Characteristics

- Handles high-density demand scenarios  
- Operates with a limited fleet  
- Maintains bounded service delays  
- Minimizes computational overhead  

---

# Summary

DRT Manager is a scalable dispatching algorithm for dynamic transit systems.

It combines:

- event-driven architecture  
- efficient data structures  
- strict service constraints  

to achieve high operational performance with minimal resources.

---

# License

This project is licensed under a custom **Non-Commercial Academic License**. 

Researchers and students are free to use, modify, and test this code for academic purposes. **Commercial use, including using this software to build a company, product, or service, is strictly prohibited** without prior written permission. 

See the [LICENSE](LICENSE) file for full legal details. For commercial licensing inquiries, please contact the author directly.

---
