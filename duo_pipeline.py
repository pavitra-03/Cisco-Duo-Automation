import hmac
import hashlib
import base64
import json
import time
import os
import requests
from datetime import datetime

# Read credentials safely from environment variables
IKEY = os.getenv("DUO_IKEY")
SKEY = os.getenv("DUO_SKEY")
HOST = os.getenv("DUO_HOST")
STATE_FILE = "last_run.json"

if not IKEY or not SKEY or not HOST:
    raise ValueError("Missing required Duo API credentials in environment variables.")

def generate_headers(method, path, query_string=""):
    now_utc = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    canonical_str = f"{now_utc}\n{method.upper()}\n{HOST.lower()}\n{path}"
    canonical_str += f"\n{query_string}" if query_string else "\n"

    hmac_sig = hmac.new(
        SKEY.encode("utf-8"), 
        canonical_str.encode("utf-8"), 
        hashlib.sha1
    ).hexdigest().lower()
    
    auth_bytes = f"{IKEY}:{hmac_sig}".encode("utf-8")
    auth_token = base64.b64encode(auth_bytes).decode("utf-8")

    return {"Date": now_utc, "Authorization": f"Basic {auth_token}"}

def create_duo_user(username, email=""):
    path = "/admin/v1/users"
    params = {"username": username}
    if email:
        params["email"] = email

    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
    headers = generate_headers("POST", path, query_string)
    url = f"https://{HOST}{path}"

    print(f"\n[+] Adding User '{username}' to Duo UI...")
    res = requests.post(url, headers=headers, data=params)
    if res.status_code == 200:
        print(f"[SUCCESS] User created: {res.json()}")
    else:
        print(f"[-] Failed to create user ({res.status_code}): {res.text}")

def create_duo_group(group_name, desc="GitHub Actions Group"):
    path = "/admin/v1/groups"
    params = {"name": group_name, "desc": desc}

    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
    headers = generate_headers("POST", path, query_string)
    url = f"https://{HOST}{path}"

    print(f"\n[+] Adding Group '{group_name}' to Duo UI...")
    res = requests.post(url, headers=headers, data=params)
    if res.status_code == 200:
        print(f"[SUCCESS] Group created: {res.json()}")
    else:
        print(f"[-] Failed to create group ({res.status_code}): {res.text}")

def fetch_save_and_display(usecase_name, path, params=None):
    query_string = ""
    if params:
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])

    headers = generate_headers("GET", path, query_string)
    url = f"https://{HOST}{path}" + (f"?{query_string}" if query_string else "")

    print(f"\n=== FETCHING USE CASE: {usecase_name.upper()} ===")
    res = requests.get(url, headers=headers)

    if res.status_code == 200:
        data = res.json()
        os.makedirs("logs_output", exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"logs_output/duo_{usecase_name.lower().replace(' ', '_')}_{timestamp_str}.json"
        
        with open(file_name, "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"[+] Output saved to: {file_name}")
        print(f"[+] Response Data:\n{json.dumps(data, indent=2)}")
    else:
        print(f"[-] Error ({res.status_code}) fetching {usecase_name}: {res.text}")

def run_master_pipeline():
    now_ms = int(time.time() * 1000)
    three_hours_ms = 3 * 60 * 60 * 1000
    default_min_ms = now_ms - three_hours_ms

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            mintime_ms = state.get("last_run_ms", default_min_ms)
    else:
        mintime_ms = default_min_ms

    time_stamp_id = datetime.now().strftime("%H%M%S")

    # 1. Write Operations
    create_duo_user(username=f"auto_user_{time_stamp_id}", email=f"user_{time_stamp_id}@example.com")
    create_duo_group(group_name=f"auto_group_{time_stamp_id}")

    # 2. Read Operations
    fetch_save_and_display("Users", "/admin/v1/users")
    fetch_save_and_display("Groups", "/admin/v1/groups")
    fetch_save_and_display("Administrator Logs", "/admin/v1/logs/administrator")
    fetch_save_and_display("Telephony Logs", "/admin/v1/logs/telephony")
    fetch_save_and_display(
        "Authentication Logs",
        "/admin/v2/logs/authentication",
        params={"maxtime": str(now_ms), "mintime": str(mintime_ms)}
    )

    # Update local state tracking file
    with open(STATE_FILE, "w") as f:
        json.dump({"last_run_ms": now_ms}, f)

if __name__ == "__main__":
    run_master_pipeline()
