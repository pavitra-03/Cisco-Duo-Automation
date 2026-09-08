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

TEST_PHONE = os.environ.get('TEST_PHONE_NUMBER', '+15550199999')
STATE_FILE = 'last_run.json'

def generate_duo_headers(ikey, skey, method, path, params=None):
    """
    Generates standard Cisco Duo HMAC-SHA1 signature headers.
    Ensures strict canonical sorting and standard URL-encoding for query string matching.
    """
    now_utc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Sort keys alphabetically and encode properly
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
# WRITE OPERATIONS (CREATES UI ENTITIES)
# ==============================================================================
def create_duo_user(username, email):
    """Creates an active user directly in the Duo UI."""
    path = "/admin/v1/users"
    params = {
        "username": username,
        "email": email,
        "realname": f"Automated User {username}",
        "status": "active"  # Forces user into the primary Active Users view
    }
    
    headers, query_str = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    url = f"https://{HOST}{path}"

    res = requests.post(url, headers=headers, data=params)
    print(f"\n[+] User Creation HTTP Response Code: {res.status_code}")
    print(f"[+] User Creation Response Body: {res.text}")

    if res.status_code == 200:
        user_id = res.json()['response']['user_id']
        print(f"[SUCCESS] User '{username}' Created! Visible in Duo UI -> Users (ID: {user_id})")
        return user_id
    else:
        print(f"[-] ERROR Creating User: {res.status_code} - {res.text}")
        return None

def create_duo_group(group_name):
    """Creates a group directly in the Duo UI."""
    path = "/admin/v1/groups"
    params = {"name": group_name, "desc": "Automated Pipeline Execution Group"}
    
    headers, query_str = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    url = f"https://{HOST}{path}"

    res = requests.post(url, headers=headers, data=params)
    print(f"\n[+] Group Creation HTTP Response Code: {res.status_code}")
    print(f"[+] Group Creation Response Body: {res.text}")

    if res.status_code == 200:
        print(f"[SUCCESS] Group '{group_name}' Created! Visible in Duo UI -> Groups")
    else:
        print(f"[-] ERROR Creating Group: {res.status_code} - {res.text}")

def attach_phone_and_send_sms(user_id, phone_number):
    """Creates phone device, attaches to user, and dispatches activation SMS."""
    path = "/admin/v1/phones"
    params = {"number": phone_number, "type": "mobile"}
    
    headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", path, params)
    res = requests.post(f"https://{HOST}{path}", headers=headers, data=params)
    
    if res.status_code == 200:
        phone_id = res.json()['response']['phone_id']
        
        # Attach to user
        assoc_path = f"/admin/v1/users/{user_id}/phones"
        assoc_params = {"phone_id": phone_id}
        assoc_headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", assoc_path, assoc_params)
        requests.post(f"https://{HOST}{assoc_path}", headers=assoc_headers, data=assoc_params)
        
        # Send SMS activation text
        sms_path = f"/admin/v1/phones/{phone_id}/send_sms_activation"
        sms_headers, _ = generate_duo_headers(ADMIN_IKEY, ADMIN_SKEY, "POST", sms_path)
        requests.post(f"https://{HOST}{sms_path}", headers=sms_headers)
        print(f"[SUCCESS] Phone attached and activation SMS sent to {phone_number}")

# ==============================================================================
# READ LOGS & EXPORT
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
            
        print(f"[+] Exported {usecase_name} to {file_name}")
    else:
        print(f"[-] Error fetching {usecase_name}: {res.status_code} - {res.text}")

def run_automation():
    if not ADMIN_IKEY or not ADMIN_SKEY or not HOST:
        raise ValueError("Missing DUO_IKEY, DUO_SKEY, or DUO_HOST environment variables.")

    now_ms = int(time.time() * 1000)
    three_hours_ms = 3 * 60 * 60 * 1000
    default_min_ms = now_ms - three_hours_ms

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            mintime_ms = json.load(f).get("last_run_ms", default_min_ms)
    else:
        mintime_ms = default_min_ms

    run_id = str(uuid.uuid4())[:8]
    username = f"user_{run_id}"
    email = f"auto_{run_id}@automation-test.org"
    group_name = f"Group_{run_id}"

    print(f"\n==========================================")
    print(f" RUNNING DUO PIPELINE [{run_id}]")
    print(f"==========================================")

    # 1. Create Entities in Duo UI
    user_id = create_duo_user(username, email)
    create_duo_group(group_name)
    
    if user_id:
        attach_phone_and_send_sms(user_id, TEST_PHONE)

    time.sleep(2)

    # 2. Retrieve All Use Case Data
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
