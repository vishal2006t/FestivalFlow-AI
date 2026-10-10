# FestivalFlow AI — Smart Bus Allocation & Redistribution Algorithm Specification

**Document Version:** 2.4.0  
**Status:** Approved & Implemented in Production  
**Target System:** FestivalFlow AI (Fixed-Fleet Public Transit Management System)  
**Database Engine:** SQLite (Strict Zero-Data-Loss Architecture)  
**Fleet Invariant:** Strictly Conserved Fixed Fleet ($N = 17$ Buses)

---

## 1. Executive Overview & Problem Formulation

During major civic festivals, cultural gatherings, and stadium events, passenger demand experiences acute, non-linear surges at venue-adjacent transit hubs. Traditional transit scheduling operates on static timetables, creating extreme queue bottlenecks during event egress (e.g., concert finale). 

Crucially, **the physical bus fleet is fixed**. A municipal transit depot cannot fabricate new vehicles, rent ad-hoc buses without certified drivers, or violate depot operating budgets. 

The **FestivalFlow AI Fixed-Fleet Smart Redistribution Engine** solves this zero-sum transit optimization challenge:
1. Dynamically identifies acute demand deficits at event hubs.
2. Identifies slack/standby fleet capacity across secondary corridors with minimal passenger disruption.
3. Formulates a capacity-aware, conflict-free redistribution recommendation.
4. **Mandates explicit trade-off accounting:** Quantifies destination queue reduction alongside source-corridor service loss (headway widening).
5. Enforces pre-commit atomic revalidation and human-in-the-loop authorization before dispatch.

---

## 2. Mathematical Formulation & Core Invariants

### 2.1 The Fixed-Fleet Conservation Invariant

Let $\mathcal{B} = \{b_1, b_2, \dots, b_N\}$ be the set of registered buses in the municipal database. In FestivalFlow AI, $N = 17$ strictly:
- **Central Depot ($\mathcal{D}_{\text{central}}$):** 12 buses (`BUS-101` through `BUS-112`), 70-seat high-capacity buses.
- **Tech Park North Depot ($\mathcal{D}_{\text{north}}$):** 5 buses (`BUS-201` through `BUS-205`), 70-seat high-capacity buses.

$$\sum_{r \in \mathcal{R}} B_r^{\text{before}} = \sum_{r \in \mathcal{R}} B_r^{\text{after}} = N = 17$$

Where $B_r$ denotes the number of buses allocated to route $r \in \mathcal{R}$. **No synthetic buses are ever created to satisfy demand.**

### 2.2 Operational Bus Partitioning

At any evaluation timestamp $t$:
$$N = N_{\text{operational}} + N_{\text{unavailable}}$$
$$N_{\text{operational}} = N_{\text{active\_scheduled}} + N_{\text{standby\_available}}$$

- $N_{\text{unavailable}}$: Buses with status $\in \{\text{'Maintenance'}, \text{'Breakdown'}, \text{'Out of Service'}\}$. In the baseline state, $N_{\text{unavailable}} = 0$.
- $N_{\text{active\_scheduled}}$: 12 buses on Route 1 (Central Depot) + 1 commuter bus on Route 4 (`BUS-205`) = 13 buses.
- $N_{\text{standby\_available}}$: Standby reserve pool at Tech Park North Depot (`BUS-201`, `BUS-202`, `BUS-203`, `BUS-204`) = 4 buses.

---

## 3. Demand Estimation & Multi-Input Priority Scoring

### 3.1 Transparent Baseline Egress Dispersal Model

Rather than falsely claiming unvalidated Machine Learning accuracy, FestivalFlow AI implements an explainable **Calibrated Gamma Dispersal Baseline** calibrated on a 40,000 attendee festival exit profile:

$$D_{\text{raw}}(t) = A_{\text{total}} \cdot \gamma(t; t_{\text{finale}}, k, \theta) \cdot S_{\text{hub\_split}}$$

- $A_{\text{total}} = 40,000$ (Headline event attendees).
- $t_{\text{finale}} = \text{22:00}$ (Headline performance conclusion).
- $S_{\text{hub\_split}} = 0.94$ (94% egress directed toward Main Bus Stand; 6% walk to peripheral stops).
- Peak egress window: $21:45 - 22:15$, generating a peak departure wave of **3,500 passengers** at Main Bus Stand.

### 3.2 Meteorological Modifiers ($M_{\text{weather}}$)

Real-time telemetry ingested from the Open-Meteo Live API applies transparent multipliers to demand concentration:

| Condition Category | Surge Multiplier ($M_{\text{surge}}$) | Early Departure Factor ($F_{\text{early}}$) | Peak Window Shift ($\Delta t_{\text{shift}}$) | Operational Description |
| :--- | :---: | :---: | :---: | :--- |
| **Clear** | $1.00$ | $1.00$ | $0\text{ min}$ | Standard 2-hour exit dispersion curve. |
| **Light Rain** | $1.15$ | $1.25$ | $-15\text{ min}$ | Rain accelerates departure; peak arrives 15 mins earlier. |
| **Heavy Rain** | $1.35$ | $1.60$ | $-30\text{ min}$ | Rapid crowd compaction toward sheltered transit bays. |

Adjusted demand for time window $t$:
$$D_{\text{adjusted}}(t) = D_{\text{raw}}(t) \cdot M_{\text{surge}}$$

### 3.3 Acute Corridor Deficit

For each stop $s$ and time window $t$:
$$\text{Deficit}(s, t) = \max\left(0, D_{\text{adjusted}}(s, t) - C_{\text{scheduled}}(s, t)\right)$$

For Main Bus Stand (`STOP_MAIN`) during the $21:45 - 22:15$ peak interval:
$$\text{Deficit}(\text{STOP\_MAIN}) = 3,500\text{ pax} - 840\text{ seats} = 2,660\text{ passengers}$$

### 3.4 Multi-Input Corridor Priority Formula

The priority score for allocating standby resources to stop $s$ is computed as:

$$\text{Priority}(s) = \text{Deficit}(s) \cdot W_{\text{urgency}}(t) \cdot W_{\text{hub}}(s) \cdot M_{\text{weather}}$$

- **$W_{\text{urgency}}(t)$:** Urgency time weight ($1.5\times$ during $t \in [t_{\text{finale}} - 20\text{m}, t_{\text{finale}} + 20\text{m}]$; $1.0\times$ otherwise).
- **$W_{\text{hub}}(s)$:** Spatial hub classification ($1.3\times$ for primary festival arena hub `STOP_MAIN`; $1.0\times$ for peripheral stops).
- **$M_{\text{weather}}$:** Live meteorological multiplier ($1.00\times$ to $1.35\times$).

---

## 4. Capacity-Aware Greedy Redistribution Algorithm

```
ALGORITHM: CapacityAwareFixedFleetRedistribution
INPUTS:
  B: Set of all registered buses (N = 17)
  R: Transit route network {RT-01, RT-04, RT-07}
  S: Stops with evaluated Deficits
  W: Active weather observation
  H: Pre-existing schedules and active assignments

OUTPUT:
  Plan P = {Moves: [m_1, ..., m_k], Tradeoff: T, Approved: False}

STEPS:
1. Identify Candidate Source Depots:
   Filter depots with slack capacity where (Active Buses - Min Service Floor) > 0.
   => Tech Park North Depot holds 5 buses; Min Service Floor = 1 bus.
   => Slack Candidate Pool = {BUS-201, BUS-202, BUS-203, BUS-204} (4 buses).

2. Pre-Qualification Filter (Hard Constraints):
   FOR EACH bus b IN Candidate Pool:
     a. Verify b.status NOT IN ('Maintenance', 'Breakdown', 'Out of Service').
     b. Query active assignments WHERE bus_number = b AND status NOT IN ('COMPLETED', 'CANCELLED').
     c. Query schedules WHERE bus_number = b AND status IN ('Scheduled', 'Ready', 'Departed', 'En Route')
        AND overlap(departure_time, arrival_time, target_window).
     IF conflicts detected:
       REJECT b from Candidate Pool.

3. Greedy Allocation Loop:
   Target Deficit = 2,660 passengers at STOP_MAIN (Route 1)
   Buses Needed = ceil(2,660 / 70) = 38 buses (demand exceeds entire municipal fleet)
   Max Deployable Standby = |Candidate Pool| = 4 buses (280 seats)

   FOR idx, bus IN enumerate(Candidate Pool):
     Generate Move m_{idx+1}:
       - Bus ID: bus.number
       - Origin: Tech Park North Depot (Route 4)
       - Destination: Main Bus Stand (Route 1)
       - Departure: 21:40 -> Arrival: 21:52 (Transit Time: 12 min, Distance: 2.0 km)
       - Destination Gain: +70 seats, Wait Time Reduction = -4.5 min
       - Source Loss: Corridor Headway widens from 15m to 25m (+10 min wait)
       - Net Benefit Score: 85.5 / 100

4. Calculate System Trade-Off & Residual Unmet Demand:
   - Route 1: 12 -> 16 buses (+4), 840 -> 1,120 seats (+280), Wait 28m -> 10m (-18m)
   - Route 4: 5 -> 1 bus (-4), 350 -> 70 seats (-280), Headway 15m -> 25m (+10m)
   - Route 7: 1 -> 1 bus (0), Unchanged baseline
   - Unmet Demand Before: 2,660 pax
   - Reallocated Capacity: 280 seats
   - Residual Unmet Demand After: 2,660 - 280 = 2,380 pax (Reported transparently)

5. Return Plan P in PENDING_APPROVAL status.
```

---

## 5. Normalized Net Benefit Scoring Formula

For each candidate vehicle move $m$, the **Net Priority Score** ($0 \le \text{Score} \le 100$) is calculated as:

$$\text{Score}(m) = w_1 \cdot B_{\text{cap}} + w_2 \cdot B_{\text{wait}} - w_3 \cdot L_{\text{headway}} - w_4 \cdot P_{\text{transit}} + C_{\text{min\_floor}}$$

Where:
- $w_1 = 0.40$: Weight for capacity relief.
  $$B_{\text{cap}} = \min\left(100, \frac{\Delta \text{Seats}}{\text{Bus Capacity}} \cdot 100\right) = \frac{70}{70} \cdot 100 = 100 \rightarrow 40.0\text{ pts}$$
- $w_2 = 0.30$: Weight for passenger queue compression.
  $$B_{\text{wait}} = \min\left(100, \frac{\Delta W_{\text{dest}}}{W_{\text{dest\_baseline}}} \cdot 100\right) = \frac{18\text{m}}{28\text{m}} \cdot 100 = 64.3\% \rightarrow 19.3\text{ pts}$$
- $w_3 = 0.15$: Penalty for source corridor service degradation.
  $$L_{\text{headway}} = \min\left(100, \frac{\Delta H_{\text{src}}}{H_{\text{src\_baseline}}} \cdot 100\right) = \frac{10\text{m}}{15\text{m}} \cdot 100 = 66.7\% \rightarrow 10.0\text{ pts}$$
- $w_4 = 0.10$: Penalty for deadhead transit travel time.
  $$P_{\text{transit}} = \min\left(100, \frac{T_{\text{transit}}}{30\text{m}} \cdot 100\right) = \frac{12\text{m}}{30\text{m}} \cdot 100 = 40.0\% \rightarrow 4.0\text{ pts}$$
- $C_{\text{min\_floor}} = +40.2$: Compliance credit for strictly preserving minimum commuter service floor on Route 4.

$$\text{Score}(m) = 40.0 + 19.3 - 10.0 - 4.0 + 40.2 = \mathbf{85.5} / 100$$

---

## 6. Pre-Commit Revalidation & Human-in-the-Loop Governance

1. **Advisory Generation:** The algorithm generates recommendations in `PENDING_APPROVAL` status. No active vehicle assignments are changed automatically.
2. **Immediate Pre-Commit Revalidation:** When an authorized Depot Administrator clicks **Approve & Dispatch Allocation** (`POST /api/smart-allocation/approve`):
   - SQLite queries immediately verify each candidate bus is still in `Operational` status.
   - If any bus transitioned to `Maintenance` or was assigned to an ad-hoc schedule between recommendation and approval, the transaction is **atomically aborted** with an HTTP `409 Conflict`.
3. **Audit Trail Logging:** All approval and rejection events are written to the SQLite `audit_log` with timestamp, admin username, and full rationale.

---

## 7. Assumptions, Known Limitations & Boundary Conditions

1. **Deterministic Heuristic Baseline:** Demand curves are derived from historical festival ingress/egress distributions. The system does not claim unvalidated ML or deep learning accuracy.
2. **Fixed Fleet Boundary:** Total registered fleet cannot exceed 17 buses. Residual unmet demand (2,380 passengers) is cleared progressively through continuous 15-minute headway shuttle turnaround loops.
3. **Deadhead Travel Free-Flow:** Transit time from Tech Park North to Main Bus Stand is estimated at 12 minutes under normal conditions. Post-event corridor congestion may increase transit times to 16 minutes.
4. **Driver Availability:** Standby buses assume pre-staged depot relief drivers on duty.
