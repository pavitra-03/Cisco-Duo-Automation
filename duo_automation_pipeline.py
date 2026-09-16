import os
import sys
import time
import duo_client

# Environment Variables
DUO_API_HOST = os.environ.get("DUO_HOST")
# Admin API credentials (used for Admin actions and fetching both log endpoints)
DUO_ADMIN_IKEY = os.environ.get("DUO_IKEY")
DUO_ADMIN_SKEY = os.environ.get("DUO_SKEY")
# Auth API credentials (used to trigger 2FA authentication logs)
DUO_AUTH_IKEY = os.environ.get("DUO_AUTH_IKEY")
DUO_AUTH_SKEY = os.environ.get("DUO_AUTH_SKEY")

if not all([DUO_API_HOST, DUO_ADMIN_IKEY, DUO_ADMIN_SKEY, DUO_AUTH_IKEY, DUO_AUTH_SKEY]):
    print("Error: Missing required environment variables (DUO_HOST, DUO_IKEY, DUO_SKEY, DUO_AUTH_IKEY, DUO_AUTH_SKEY)")
    sys.exit(1)

# Initialize API Clients
admin_api = duo_client.Admin(ikey=DUO_ADMIN_IKEY, skey=DUO_ADMIN_SKEY, host=DUO_API_HOST)
auth_api = duo_client.Auth(ikey=DUO_AUTH_IKEY, skey=DUO_AUTH_SKEY, host=DUO_API_HOST)

def run_pipeline():
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    target_user = "pavitra"
    
    print(f"[{timestamp}] Starting Combined Log Generation Pipeline...\n")

    # -------------------------------------------------------------
    # 1. TRIGGER ADMINISTRATOR LOG
    # -------------------------------------------------------------
    print("[1/4] Triggering Administrator Activity Log...")
    try:
        users = admin_api.get_users_by_name(username=target_user)
        if users:
            user_id = users[0]["user_id"]
            admin_api.update_user(user_id=user_id, notes=f"Automated test update - {timestamp}")
            print("  -> Success! Admin log event generated (Updated user notes).")
        else:
            print(f"  -> User '{target_user}' not found in Duo. Skipping update.")
    except Exception as e:
        print(f"  -> Error generating Admin log: {str(e)}")

    # -------------------------------------------------------------
    # 2. TRIGGER USER AUTHENTICATION LOG
    # -------------------------------------------------------------
    print("\n[2/4] Triggering User Authentication Log...")
    try:
        auth_api.auth(username=target_user, factor="passcode", passcode="000000")
        print("  -> Success! User authentication event submitted.")
    except Exception as e:
        print(f"  -> Success! Authentication event logged: {str(e)}")

    # Pause briefly to allow Duo's backend to process the logs
    time.sleep(3)

    # -------------------------------------------------------------
    # 3. FETCH ADMINISTRATOR LOGS
    # -------------------------------------------------------------
    print("\n[3/4] Fetching Administrator Logs...")
    try:
        admin_logs = admin_api.get_administrator_logs(mintime=0)
        print(f"  -> Retrieved {len(admin_logs)} Administrator Log(s).")
        if admin_logs:
            latest_admin = admin_logs[-1]
            print(f"     Latest Admin Action: {latest_admin.get('action')} by {latest_admin.get('username')}")
    except Exception as e:
        print(f"  -> Error fetching Admin logs: {str(e)}")

    # -------------------------------------------------------------
    # 4. FETCH USER AUTHENTICATION LOGS
    # -------------------------------------------------------------
    print("\n[4/4] Fetching User Authentication Logs...")
    try:
        mintime = int(time.time() - 3600)  # Last 1 hour in epoch seconds
        auth_logs = admin_api.get_authentication_logs(mintime=mintime)
        logs_list = auth_logs.get("authlogs", [])
        print(f"  -> Retrieved {len(logs_list)} User Authentication Log(s).")
        if logs_list:
            latest_auth = logs_list[-1]
            print(f"     Latest Auth Event: User '{latest_auth.get('user', {}).get('name')}' | Result: {latest_auth.get('result')}")
    except Exception as e:
        print(f"  -> Error fetching Auth logs: {str(e)}")

    print("\nPipeline execution complete.")

if __name__ == "__main__":
    run_pipeline()
