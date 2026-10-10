# FestivalFlow AI — Intelligent Festival Transit & Crowd Dispersal System

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5.0+-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![SQLite](https://img.shields.io/badge/SQLite-Authoritative-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)

**FestivalFlow AI** is an intelligent public-transport operations and crowd-dispersal planning system engineered for massive cultural events and festivals.

---

## 🎪 The Operational Problem

- **40,000 attendees** exit the festival arena simultaneously within a 2-hour dispersal window (21:45 – 22:45).
- **The Main Bus Stand** has 12 scheduled buses providing 840 seats per wave, creating an acute passenger bottleneck and unsafe platform overcrowding.
- **A nearby stop (Tech Hub North)**, located 2.0 km away (12 minutes transit), holds 4 mostly idle standby buses.
- **Strict Conservation Constraint:** Municipal transit fleets are strictly fixed (17 total buses across the regional network). No additional buses can be magically generated.
- **Minimum Service Guarantee:** Regional stops cannot be abandoned; source depots must retain minimum commuter coverage.

---

## ⚡ The Solution

FestivalFlow AI mathematically predicts crowd departure curves, identifies network capacity imbalances, and calculates proactive bus reallocations before critical congestion develops:
1. **Demand Estimation:** Deterministic attendee dispersal curves with live weather modifier adjustments.
2. **Proactive Optimization:** Calculates travel time and dispatches idle buses **before** the surge hits (staging departure at 21:40, arriving at 21:52 ahead of the 22:00 headline finale).
3. **Admin-in-the-Loop Dispatch:** Generates an executive operations report; requires explicit Depot Admin authorization before mobilizing vehicles.
4. **Driver Console:** Real-time driver portal with trip assignments, departure acknowledgement, and delay reporting.
5. **Interactive Telematics Tracking:** Full-screen Leaflet interactive map with route polylines and simulated telematics for all 17 buses.
6. **Live Weather Integration:** Real-time Open-Meteo REST integration providing live ambient conditions and precipitation risk assessment.
7. **AI Operations Explainer:** OpenRouter integration (`google/gemini-2.5-flash`) translating mathematical allocation vectors into clear natural-language briefings.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────┐
│               React 18 + Vite Frontend                 │
│  - Linear/Stripe/Vercel Enterprise Operations Design   │
│  - Report-First Admin Console & Mobile Driver View     │
│  - Full-Screen Leaflet Interactive Tracking Map        │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / JSON REST
┌──────────────────────────▼─────────────────────────────┐
│                 FastAPI Backend Gateway                │
│  - RBAC (Depot Admin & Bus Driver Role Enforcement)   │
│  - BusReallocationOptimizer (Fixed-Fleet Conservation) │
│  - Open-Meteo Weather Service & AI Explainer Gateway   │
└──────────────────────────┬─────────────────────────────┘
                           │ SQL Transactions
┌──────────────────────────▼─────────────────────────────┐
│            SQLite: app/data/festivalflow.db            │
│  - 17 Fixed Buses, 5 Users, Schedules & Telematics     │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm

### 1. Backend Setup
```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Start backend server
uvicorn main:app --host 127.0.0.1 --port 8081 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to access the operations console.

---

## 🔐 Credentials for Demonstration

| Role | Username | Password | Access Scope |
|---|---|---|---|
| **Depot Admin** | `admin_chennai` | `Admin@Depot2026` | Full Operations Report, Allocation Approval, Fleet Telematics |
| **Bus Driver** | `driver_ramesh` | `Driver@2026` | Assigned Bus Runs, Trip Acknowledgement, Incident Reports |

---

## 📋 Comprehensive Audit Report

A complete 10-section pre-demo audit and verification report is documented in:  
📄 **[PRE_DEMO_AUDIT_REPORT.md](PRE_DEMO_AUDIT_REPORT.md)**

---

## 📄 License

MIT License. Designed for Municipal Public Transport Systems and Large-Scale Event Operations.
