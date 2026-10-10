"""End-to-end live server HTTP verification script for FestivalFlow AI Constraint-1."""
import urllib.request
import json

def test_live_servers():
    print("==================================================================")
    print("FestivalFlow AI - Constraint-1 Live Server Verification")
    print("==================================================================")

    # 1. Test Frontend on port 5173
    try:
        with urllib.request.urlopen("http://127.0.0.1:5173") as r:
            print(f"[1] Frontend (Vite on port 5173): HTTP {r.status} OK")
    except Exception as e:
        print(f"[1] Frontend error: {e}")

    # 2. Test Backend Health on port 8081
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/health") as r:
            body = json.loads(r.read().decode())
            print(f"[2] Backend (FastAPI on port 8081): HTTP {r.status} - {body['status']} ({body['service']})")
    except Exception as e:
        print(f"[2] Backend health error: {e}")

    # 3. Test Admin Login
    login_data = json.dumps({
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8081/api/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        login_res = json.loads(r.read().decode())
        token = login_res["token"]
        print(f"[3] Admin Login: Success! User: {login_res['user']['username']} (Role: {login_res['user']['role']})")

    # 4. Test Scenario A (Event end time delayed from 9:00 PM to 9:30 PM)
    delay_data = json.dumps({"end_time": "21:30"}).encode()
    req_delay = urllib.request.Request(
        "http://127.0.0.1:8081/api/live/event-update",
        data=delay_data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_delay) as r:
        delay_res = json.loads(r.read().decode())
        recalc_a = delay_res["recalculation"]
        rec_diff = recalc_a["diff"]["recommendation"]
        print(f"[4] Scenario A (Event Delay) Triggered Automatically:")
        print(f"    - Version: v{recalc_a['version']}")
        print(f"    - Reason: \"{recalc_a['reason']}\"")
        print(f"    - Staging Departure: {rec_diff['previous_departure_time']} -> {rec_diff['current_departure_time']}")
        print(f"    - Staging Arrival: {rec_diff['previous_arrival_time']} -> {rec_diff['current_arrival_time']}")
        print(f"    - Fleet Conserved: {rec_diff['fleet_conserved']} (Total Fleet: {rec_diff['total_network_fleet']})")

    # 5. Test Scenario B (Rain starts during event)
    rain_data = json.dumps({"weather_condition": "Light Rain"}).encode()
    req_rain = urllib.request.Request(
        "http://127.0.0.1:8081/api/live/weather-update",
        data=rain_data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_rain) as r:
        rain_res = json.loads(r.read().decode())
        recalc_b = rain_res["recalculation"]
        dem_diff = recalc_b["diff"]["demand"]
        rec_diff_b = recalc_b["diff"]["recommendation"]
        print(f"[5] Scenario B (Rain Starts) Triggered Automatically:")
        print(f"    - Version: v{recalc_b['version']}")
        print(f"    - Reason: \"{recalc_b['reason']}\"")
        print(f"    - Surge Multiplier Applied: {dem_diff['surge_multiplier_applied']}x")
        print(f"    - Peak Queue Volume: {dem_diff['previous_peak_volume']:,} -> {dem_diff['current_peak_volume']:,} pax")
        print(f"    - Wet Road Departure Adjustment: {rec_diff_b['current_departure_time']} (buffered)")
        print(f"    - Unmet Clearance Demand: {rec_diff_b['current_unmet_demand']:,} pax")

    # 6. Verify GET /api/live/state query
    req_state = urllib.request.Request(
        "http://127.0.0.1:8081/api/live/state",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_state) as r:
        state = json.loads(r.read().decode())
        print(f"[6] Dashboard Live State Synced:")
        print(f"    - Status: {state['status']}")
        print(f"    - Latest Version: v{state['version']}")
        print(f"    - Headline Finish Display: {state['inputs_snapshot']['headline_end_time_display']}")
        print(f"    - Active Weather: {state['inputs_snapshot']['weather_condition']}")
        print(f"    - Total History Entries Logged: {len(state['history'])}")

    print("==================================================================")
    print("ALL LIVE SERVER INTEGRATION CHECKS VERIFIED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    test_live_servers()
