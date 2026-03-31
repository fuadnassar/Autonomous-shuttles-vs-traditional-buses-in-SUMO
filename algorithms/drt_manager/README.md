# DRT Manager

## Overview
DRT Manager is a high-performance Demand Responsive Transport (DRT) algorithm developed by Fuad Nassar as part of a Master’s thesis at the Technical University of Munich (TUM). 

Rather than a standard routing framework, this project is fundamentally an algorithmic solution designed to operate a constrained fleet of autonomous midi-buses under extreme high-demand conditions. It focuses on real-time vehicle assignment, route optimization, and strict service-level control, enabling efficient operation in dense urban scenarios without computational bottlenecks.

## Algorithm Characteristics
* **Dynamic Assignment:** Evaluates and assigns passenger requests to vehicles using a strict marginal-cost approach.
* **Constraint-Based Enforcement:** Rejects routing assignments that violate maximum allowable pickup or drop-off delays.
* **Incremental Route Optimization:** Dynamically inserts pickup and drop-off points, reordering stops to minimize travel time while maintaining capacity feasibility.
* **Event-Driven Execution:** Bypasses standard loop-based simulation polling by utilizing a TraCI step listener to react to simulation events asynchronously.
* **Efficient State Management:** Utilizes hash-based data structures to achieve O(1) time complexity for state lookups during heavy load.

## Core Logic
The algorithm operates within a discrete simulation loop using SUMO (Simulation of Urban MObility) and TraCI:

* **Request Processing:** Passenger demand is not live; it is injected from a predefined synthetic dataset and processed incrementally at each simulation step.
* **Vehicle Assignment:** Each active request is evaluated against the available fleet. The algorithm calculates the marginal cost (added delay) of inserting the passenger into a vehicle's manifest.
* **Constraint Validation:** The algorithm strictly enforces two parameters before assignment: 
  1. Maximum delay threshold for passengers already onboard.
  2. Maximum drift from the initially promised ETA for passengers waiting at a stop.
* **Route Optimization:** If constraints are satisfied, the vehicle's route is updated incrementally.

## Usage

### Execution
```bash
# Basic run with default parameters
python drt_manager.py

# Run with custom parameters and GUI
python drt_manager.py --dropoff-delay 60 --pickup-delay 120 --rt-limit 2 --scale 1 -gui
ArgumentsArgumentDescriptionDefault--dropoff-delayMaximum allowed detour delay for onboard passengers (seconds).60--pickup-delayMaximum allowed drift from promised pickup ETA (seconds).120--rt-limitMaximum number of real-time requests processed per simulation step.2--scaleDemand scaling factor for stress testing.1-guiLaunches the simulation using the SUMO graphical interface.DisabledPorting the Algorithm to Another CityThe DRT Manager algorithm is network-agnostic and can be adapted to simulate demand-responsive transit in any city. To port the project, update the following input data:Network Configuration: Replace the existing SUMO network (.net.xml) and simulation configuration (sumo.sumocfg) with your target city's network.Stops Definition: Update the as_stops.add.xml file to map bus stops to the exact lane IDs of the new network.Demand Data: Replace data/personal_planes.xlsx. The algorithm requires origin coordinates (X,Y), destination coordinates (X,Y), and departure times. The system will automatically map these coordinates to the nearest valid stops.Fleet Configuration: Adjust vehicle definitions (fleet size, capacity, vehicle type) within the SUMO configuration files to match your simulation parameters.Project StructurePlaintextproject/
├── drt_manager.py                 # Core simulation loop and TraCI execution
├── drt_manager_lib.py             # Optimization, routing, and cost calculation logic
├── drt_manager_listener.py        # Event-driven step listener and fleet state manager
├── drt_manager_personal_plans.py  # Demand processing and topology mapping
├── data/
│   └── personal_planes.xlsx       # Predefined synthetic demand dataset
├── sumo.sumocfg                   # SUMO simulation configuration
└── as_stops.add.xml               # Bus stop definitions and lane mappings
LicenseThis project is licensed under the MIT License.