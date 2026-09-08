import hmac
import hashlib
import base64
import json
import time
import os
import uuid
import requests
from urllib.parse import urlencode
from datetime import datetime, timezone

# 1. READ CREDENTIALS FROM ENVIRONMENT
ADMIN_IKEY = os.environ.get('DUO_IKEY')
ADMIN_SKEY = os.environ.get('DUO_SKEY')
HOST = os.environ.get('DUO_HOST')

# Set test phone number from environment or fallback to your screenshot's target number
TEST_PHONE = os.environ.get('TEST_PHONE_NUMBER', '+919741183942')
STATE_FILE = 'last_run.json'

def generate_duo_headers(ikey, skey, method, path, params=None):
    """
    Generates valid HMAC-SHA1 headers required by Cisco Duo Admin API.
    """
    now_utc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Duo requires parameters sorted alphabetically by key
    if params:
        query_string = urlencode(sorted(params.items()))
    else:
        query_string = ""

    canonical_str = f"{now_utc}\n{method.upper()}\n{HOST.lower()}\n{path}"
    canonical_str += f"\n{query_string}" if query_string else "\n"

    hmac_sig = hmac.new(
        skey.encode("utf-8"),
        canonical_str.encode("utf-8"),
        hashlib.sha1
    ).hexdigest().lower()

    auth_bytes = f"{ikey}:{hmac_sig}".encode("utf-8")
    auth_token = base64.b64encode(auth_bytes).decode("utf-8")

    return {"Date": now_utc, "Authorization": f"Basic {auth_token}"}, query_string

# ==============================================================================
# WRITE OPERATIONS (Triggers Admin Audit Logs and UI Entries)
# ==============================================================================
def create_duo_user(username, email):
    path = "/admin/v1/users"
    params = {
        "username": username,
        "email": email,
        "realname": f"Automated User {username}",
        "status": "active"
    }
    
    headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    res = requests.post(f"https://{HOST}{path}", headers=headers, data=params)
    
    print(f"[API] Create User Status: {res.status_code}")
    print(f"[API] Response: {res.text}")

    if res.status_code == 200:
        user_id = res.json()['response']['user_id']
        print(f"[SUCCESS] User '{username}' created with ID: {user_id}")
        return user_id
    else:
        print(f"[-] User Creation Failed: {res.text}")
        return None

def create_duo_group(group_name):
    path = "/admin/v1/groups"
    params = {"name": group_name, "desc": "Automated Group Execution"}
    
    headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    res = requests.post(f"https://{HOST}{path}", headers=headers, data=params)
    
    print(f"[API] Create Group Status: {res.status_code}")
    print(f"[API] Response: {res.text}")

def attach_phone_and_trigger_telephony(user_id, phone_number):
    path = "/admin/v1/phones"
    params = {"number": phone_number, "type": "mobile"}
    
    headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    res = requests.post(f"https://{HOST}{path}", headers=headers, data=params)
    
    if res.status_code == 200:
        phone_id = res.json()['response']['phone_id']
        
        # Associate phone to user
        assoc_path = f"/admin/v1/users/{user_id}/phones"
        assoc_params = {"phone_id": phone_id}
        assoc_headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", assoc_path, assoc_params)
        requests.post(f"https://{HOST}{assoc_path}", headers=assoc_headers, data=assoc_params)
        
        # Send SMS activation (triggers Telephony Log entry in UI and API)
        sms_path = f"/admin/v1/phones/{phone_id}/send_sms_activation"
        sms_headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", sms_path)
        sms_res = requests.post(f"https://{HOST}{sms_path}", headers=sms_headers)
        
        print(f"[API] Send SMS Status: {sms_res.status_code}")
        print(f"[API] Send SMS Response: {sms_res.text}")

# ==============================================================================
# READ LOGS (Fetches All 5 Endpoints)
# ==============================================================================
def fetch_and_save_data(usecase_name, path, params=None):
    headers, query_str = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "GET", path, params)
    url = f"https://{HOST}{path}" + (f"?{query_str}" if query_str else "")

    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"duo_{usecase_name.lower().replace(' ', '_')}_{timestamp_str}.json"
        
        with open(file_name, "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"[+] Saved {usecase_name} to {file_name}")
    else:
        print(f"[-] Error fetching {usecase_name}: {res.status_code} - {res.text}")

def run_automation():
    if not ADMIN_IKEY or not ADMIN_SKEY or not HOST:
        print("ERROR: Missing DUO_IKEY, DUO_SKEY, or DUO_HOST environment variables in GitHub Secrets.")
        return

    now_ms = int(time.time() * 1000)
    three_hours_ms = 3 * 60 * 60 * 1000
    default_min_ms = now_ms - three_hours_ms

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            mintime_ms = json.load(f).get("last_run_ms", default_min_ms)
    else:
        mintime_ms = default_min_ms

    run_id = str(uuid.uuid4())[:6]
    username = f"auto_user_{run_id}"
    email = f"user_{run_id}@sacumen.com"
    group_name = f"auto_group_{run_id}"

    print(f"\n--- Running Automated Pipeline ID: {run_id} ---")

    # 1. Perform Write Operations
    user_id = create_duo_user(username, email)
    create_duo_group(group_name)
    
    if user_id:
        attach_phone_and_trigger_telephony(user_id, TEST_PHONE)

    time.sleep(2)

    # 2. Fetch and Store Logs
    fetch_and_save_data("Users", "/admin/v1/users")
    fetch_and_save_data("Groups", "/admin/v1/groups")
    fetch_and_save_data("Administrator Logs", "/admin/v1/logs/administrator")
    fetch_and_save_data("Telephony Logs", "/admin/v1/logs/telephony")
    fetch_and_save_data(
        "Authentication Logs",
        "/admin/v2/logs/authentication",
        params={"maxtime": str(now_ms), "mintime": str(mintime_ms)}
    )

    with open(STATE_FILE, "w") as f:
        json.dump({"last_run_ms": now_ms}, f)

if __name__ == "__main__":
    run_automation()
