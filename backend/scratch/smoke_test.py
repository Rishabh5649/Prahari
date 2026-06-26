import json
import requests

BASE_URL = "http://localhost:8000"
CIRCULAR_ID = "b568b949-441b-4934-9ee2-16ed21fc010e"

def run_smoke_test():
    print("=== STARTING END-TO-END SMOKE TEST ===")

    # --- Step 1: Ingest URL (Expected to fail/succeed depending on URL & API key) ---
    print("\n[Step 1] POST /api/ingest/url")
    payload = {"url": "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NOTI15012025.pdf"}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(f"{BASE_URL}/api/ingest/url", json=payload, headers=headers, timeout=10)
        print(f"Status Code: {r.status_code}")
        print("Response Content:")
        try:
            print(json.dumps(r.json(), indent=2))
        except:
            print(r.text)
    except Exception as e:
        print(f"Request failed: {e}")

    # --- Step 2: GET /api/maps ---
    print(f"\n[Step 2] GET /api/maps?circular_id={CIRCULAR_ID}")
    try:
        r = requests.get(f"{BASE_URL}/api/maps", params={"circular_id": CIRCULAR_ID}, timeout=10)
        print(f"Status Code: {r.status_code}")
        print("Response Content (First 2 MAP objects in full):")
        maps_list = r.json()
        print(json.dumps(maps_list[:2], indent=2))
        # Find first MAP with status == 'assigned'
        assigned_map_id = next((m["id"] for m in maps_list if m["status"] == "assigned"), None)
    except Exception as e:
        print(f"Request failed: {e}")
        assigned_map_id = None

    # --- Step 3: GET /api/dashboard/circulars/{id} ---
    print(f"\n[Step 3] GET /api/dashboard/circulars/{CIRCULAR_ID}")
    try:
        r = requests.get(f"{BASE_URL}/api/dashboard/circulars/{CIRCULAR_ID}", timeout=10)
        print(f"Status Code: {r.status_code}")
        print("Response Shape (truncating raw_text to 100 chars):")
        data = r.json()
        if "raw_text" in data:
            data["raw_text"] = data["raw_text"][:100] + "..."
        if "maps" in data:
            for m in data["maps"]:
                if "what" in m:
                    m["what"] = m["what"][:100] + "..."
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Request failed: {e}")

    # --- Step 4: POST /api/evidence/submit ---
    if not assigned_map_id:
        print("\n[Step 4] Skipping due to missing assigned map_id from Step 2.")
        evidence_id = None
    else:
        print(f"\n[Step 4] POST /api/evidence/submit (map_id: {assigned_map_id})")
        files = {"file": ("test_evidence.txt", "This is some test evidence content for IT-Security.", "text/plain")}
        data = {"map_id": assigned_map_id, "submitted_by": "test@bank.com"}
        try:
            r = requests.post(f"{BASE_URL}/api/evidence/submit", data=data, files=files, timeout=10)
            print(f"Status Code: {r.status_code}")
            print("Response Content:")
            print(json.dumps(r.json(), indent=2))
            evidence_id = r.json().get("evidence_id")
        except Exception as e:
            print(f"Request failed: {e}")
            evidence_id = None

    # --- Step 5: POST /api/judgments/{map_id}/judge ---
    if not assigned_map_id or not evidence_id:
        print("\n[Step 5] Skipping due to missing map_id or evidence_id.")
    else:
        print(f"\n[Step 5] POST /api/judgments/{assigned_map_id}/judge")
        payload = {"evidence_id": evidence_id}
        try:
            r = requests.post(f"{BASE_URL}/api/judgments/{assigned_map_id}/judge", json=payload, headers=headers, timeout=10)
            print(f"Status Code: {r.status_code}")
            print("Response Content:")
            try:
                print(json.dumps(r.json(), indent=2))
            except:
                print(r.text)
        except Exception as e:
            print(f"Request failed: {e}")

    # --- Step 6: GET /api/audit?entity_id={circular_id} ---
    print(f"\n[Step 6] GET /api/audit?entity_id={CIRCULAR_ID}")
    try:
        r = requests.get(f"{BASE_URL}/api/audit", params={"entity_id": CIRCULAR_ID}, timeout=10)
        print(f"Status Code: {r.status_code}")
        print("Response (event_type only):")
        data = r.json()
        event_types = [item.get("event_type") for item in data.get("items", [])]
        print(event_types)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    run_smoke_test()
