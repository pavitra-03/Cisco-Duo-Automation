import hmac
import hashlib
import base64
import json
import time
import os
import uuid
import requests
from datetime import datetime, timezone

# Read API Credentials from Environment Variables (GitHub Secrets)
IKEY = os.environ.get('DUO_IKEY')
SKEY = os.environ.get('DUO_SKEY')
HOST = os.environ.get('DUO_HOST')

# Test phone number to receive the simulated SMS log (e.g., +15550199999 or your test number)
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER', '+15550199999')
STATE_FILE = 'last_run.json'

def generate_headers(method, path, query_string=""):
    """Generates the required HMAC-SHA1 Authorization header for Cisco Duo."""
    now_utc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
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

# ==============================================================================
# 1. WRITE OPERATIONS (Creates Users, Groups, Devices & Triggers Telephony)
# ==============================================================================
def create_duo_user(username, email):
    """Creates a user in Duo UI."""
    path = "/admin/v1/users"
    params = {"username": username, "email": email, "realname": f"Automated User {username}"}
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])

    headers = generate_headers("POST", path, query_string)
    url = f"https://{HOST}{path}"

    response = requests.post(url, headers=headers, data=params)
    if response.status_code == 200:
        user_data = response.json()['response']
        print(f"[SUCCESS] User Created: {username} (ID: {user_data['user_id']})")
        return user_data['user_id']
    else:
        print(f"[-] Failed to create user: {response.status_code} - {response.text}")
        return None

def create_duo_group(group_name, description):
    """Creates a group in Duo UI."""
    path = "/admin/v1/groups"
    params = {"name": group_name, "desc": description}
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])

    headers = generate_headers("POST", path, query_string)
    url = f"https://{HOST}{path}"

    response = requests.post(url, headers=headers, data=params)
    if response.status_code == 200:
        group_data = response.json()['response']
        print(f"[SUCCESS] Group Created: {group_name}")
        return group_data['group_id']
    else:
        print(f"[-] Failed to create group: {response.status_code} - {response.text}")
        return None

def attach_phone_and_send_sms(user_id, phone_number):
    """
    1. Creates a phone device and associates it with the user.
    2. Sends an SMS installation/passcode text.
    3. Triggers Telephony Log events in Duo UI and Telephony API.
    """
    # Step A: Create Phone
    phone_path = "/admin/v1/phones"
    phone_params = {"number": phone_number, "type": "mobile"}
    phone_query = "&".join([f"{k}={v}" for k, v in sorted(phone_params.items())])
    phone_headers = generate_headers("POST", phone_path, phone_query)
    
    phone_res = requests.post(f"https://{HOST}{phone_path}", headers=phone_headers, data=phone_params)
    
    if phone_res.status_code == 200:
        phone_id = phone_res.json()['response']['phone_id']
        print(f"[SUCCESS] Phone Device Created: {phone_id}")

        # Step B: Associate Phone to User
        assoc_path = f"/admin/v1/users/{user_id}/phones"
        assoc_params = {"phone_id": phone_id}
        assoc_query = f"phone_id={phone_id}"
        assoc_headers = generate_headers("POST", assoc_path, assoc_query)
        
        requests.post(f"https://{HOST}{assoc_path}", headers=assoc_headers, data=assoc_params)
        print(f"[SUCCESS] Associated Phone {phone_id} with User {user_id}")

        # Step C: Send SMS (Triggers Telephony & Auth Events)
        sms_path = f"/admin/v1/phones/{phone_id}/send_sms_activation"
        sms_headers = generate_headers("POST", sms_path)
        
        sms_res = requests.post(f"https://{HOST}{sms_path}", headers=sms_headers)
        if sms_res.status_code == 200:
            print(f"[SUCCESS] SMS Passcode/Activation dispatched! Telephony Log Generated.")
        else:
            print(f"[-] SMS dispatch note: {sms_res.status_code} - {sms_res.text}")
    else:
        print(f"[-] Phone creation note: {phone_res.status_code} - {phone_res.text}")

# ==============================================================================
# 2. READ OPERATIONS (Retrieves Log Files Across All 5 Use Cases)
# ==============================================================================
def fetch_and_save_data(usecase_name, path, params=None):
    """Fetches records from Duo and exports local JSON files."""
    query_string = ""
    if params:
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])

    headers = generate_headers("GET", path, query_string)
    url = f"https://{HOST}{path}" + (f"?{query_string}" if query_string else "")

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"duo_{usecase_name.lower().replace(' ', '_')}_{timestamp_str}.json"

        with open(file_name, "w") as f:
            json.dump(data, f, indent=4)

        print(f"[+] Retrieved {usecase_name} -> Saved to local file: {file_name}")
        return data
    else:
        print(f"[-] Error fetching {usecase_name}: {response.status_code} - {response.text}")
        return None

# ==============================================================================
# 3. RUN AUTOMATION
# ==============================================================================
def run_automation():
    if not all([IKEY, SKEY, HOST]):
        raise ValueError("Missing Duo API credentials.")

    now_ms = int(time.time() * 1000)
    three_hours_ms = 3 * 60 * 60 * 1000
    default_min_ms = now_ms - three_hours_ms

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            mintime_ms = state.get("last_run_ms", default_min_ms)
    else:
        mintime_ms = default_min_ms

    run_id = str(uuid.uuid4())[:8]
    print(f"\n--- Starting Automated Duo Log-Generation Run [{run_id}] ---")

    # 1. Create User & Group
    username = f"user_{run_id}"
    dynamic_email = f"auto_test_{run_id}@automation-test.org"
    group_name = f"Log_Group_{run_id}"

    user_id = create_duo_user(username, dynamic_email)
    create_duo_group(group_name, f"Automated execution group for run {run_id}")

    # 2. Trigger Telephony Event (Pushes SMS)
    if user_id:
        attach_phone_and_send_sms(user_id, TEST_PHONE_NUMBER)

    # Short pause to allow Duo background servers to write the events
    time.sleep(3)

    # 3. Retrieve All 5 Log & Management Endpoints
    fetch_and_save_data("Users", "/admin/v1/users")
    fetch_and_save_data("Groups", "/admin/v1/groups")
    fetch_and_save_data("Administrator Logs", "/admin/v1/logs/administrator")
    fetch_and_save_data("Telephony Logs", "/admin/v1/logs/telephony")
    fetch_and_save_data(
        "Authentication Logs",
        "/admin/v2/logs/authentication",
        params={"maxtime": str(now_ms), "mintime": str(mintime_ms)}
    )

    # 4. Save state
    with open(STATE_FILE, "w") as f:
        json.dump({"last_run_ms": now_ms}, f)

if __name__ == "__main__":
    run_automation()
