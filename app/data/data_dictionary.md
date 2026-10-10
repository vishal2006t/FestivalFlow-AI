# FestivalFlow AI — Synthetic & Operational Transit Data Dictionary

This data dictionary documents the schema, data types, units of measurement, sources, and generation methodologies for passenger demand and transit fleet datasets used in FestivalFlow AI.

| Field Name | Type | Unit / Format | Source Type | Category | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `timestamp` | ISO8601 String | `YYYY-MM-DDTHH:MM:SS` | Synthetic / Live | Observed / Generated | Timestamp corresponding to the beginning of the 15-minute operational measurement window. |
| `date` | String | `YYYY-MM-DD` | Synthetic / Live | Observed | Calendar date of festival event. |
| `time_slot` | String | `HH:MM` | Synthetic / Live | Temporal | 24-hour time representation of the 15-minute interval slot. |
| `scenario_delay_mins` | Integer | Minutes (`0, 15, 30, 60`) | Manual / Config | Scenario Parameter | Configured operational event finale delay beyond nominal 21:00 headline finish. |
| `event_end_time` | String | `HH:MM` | Manual / Config | Input | Active headline finale finish time (e.g., 21:00, 21:30). |
| `weather` | String | Categorical (`Clear`, `Light Rain`, `Heavy Rain`) | Manual / Sensor / Synthetic | Environmental | Current meteorological condition at the festival venue. |
| `stop_id` | String | Identifier (`STOP_MAIN`, `STOP_NEARBY`, etc.) | Network Config | Master Data | Unique transit stop identifier. |
| `stop_name` | String | Text | Master Data | Master Data | Human-readable name and location of transit stop. |
| `is_hub` | Integer | Binary (`0` or `1`) | Network Topology | Topological | Flag indicating whether stop serves as the primary festival exit hub (`1`) or peripheral staging stop (`0`). |
| `venue_total_crowd` | Integer | Persons | Sensor / Simulation | Derived / Estimated | Total estimated attendance remaining inside the festival precinct before exit. |
| `passenger_departure_demand` | Integer | Persons per 15-min | Model / Ticketing | Forecast / Derived | Anticipated number of passengers presenting at the bus stop queue during the interval. |
| `stop_crowd_density_count` | Integer | Persons | Vision / Camera | Observed (Camera ROI) | Physical crowd count observed at stop perimeter via camera detectors. Distinct from departure queue. |
| `scheduled_buses` | Integer | Bus Count | Database | Operational State | Scheduled bus departures assigned to serve the stop during the interval wave. |
| `bus_capacity` | Integer | Passenger Seats | Database | Operational Constraint | Total seating and authorized standing capacity across scheduled buses (`70` passengers/bus). |
| `unmet_demand` | Integer | Persons | Optimization Metric | Derived Deficit | Expected passenger backlog exceeding scheduled transit capacity: `max(0, demand - capacity)`. |
| `est_wait_time_mins` | Integer | Minutes | Queue Model | Estimated | Projected queuing delay for passengers arriving at the stop. |
| `data_source` | String | Enum (`synthetic`, `manual`, `live`, `unknown`) | Audit Metadata | Provenance | Explicit provenance flag ensuring synthetic prototype data is never misrepresented as live telemetry. |

## Provenance Guidelines
- **`live`**: Genuine sensor feeds, camera vision detections, or real-time GPS telematic feeds.
- **`manual`**: Operational changes entered directly by an authorized Bus Depot Admin.
- **`synthetic`**: Reproducibly generated data created using fixed random seeds (`seed=42`) for modeling and testing.
- **`unknown`**: Data from external feeds during provider outages or unverified connections.
