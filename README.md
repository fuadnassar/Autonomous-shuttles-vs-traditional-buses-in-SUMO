# Autonomous Shuttles vs Buses in SUMO

This repository presents a comparative simulation study between **conventional buses (current system)** and **autonomous shuttles / ARTS (future system)** using **SUMO (Simulation of Urban MObility)**.

## Project Structure

```
.
├── buses_sumo/           # Bus-based public transport scenario
├── shuttles_sumo/        # Autonomous shuttle (ARTS) scenario
└── synthetic_demand/     # Synthetic travel demand data
```

## Requirements

- SUMO (with GUI support)
- macOS / Linux
- `sumo-gui` available in PATH

Check installation:
```bash
sumo-gui --version
```

## How to Run the Simulations

### Autonomous Shuttles (ARTS)

```bash
cd shuttles_sumo
sumo-gui model.sumocfg
```

### Buses (Current System)

```bash
cd buses_sumo
sumo-gui model.sumocfg
```

## Key Performance Indicators (First Results)

| KPI                          | Bus (Current) | ARTS (Future) |
|------------------------------|---------------|---------------|
| Avg Walk Distance [m]        | 258.04        | 201.49        |
| Avg Walk Time [s]            | 233.56        | 183.18        |
| Avg Station Waiting Time [s] | 143.66        | 86.93         |
| Total Demand [Trips]         | 2830          | 2830          |
| Avg Travel Time [min]        | 6.81          | 3.08          |
| Total Distance [km]          | 2079.89       | 4272.64       |
| Avg In-Vehicle Time [s]      | 408.86        | 93.43         |
| Avg System Delay [s]         | 176.81        | 86.93         |

## Notes

- The project is currently undergoing further optimization. Future updates to this repository will include:powerful delivery algorithms to DRT to optimize travel distance.
- Both scenarios use the same synthetic demand for comparison.
- Results are obtained from SUMO simulation outputs and intruppted using python

**Fuad Nassar**  
Autonomous Shuttles vs Buses in SUMO
