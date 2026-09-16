import os
import sys
import time
import duo_client

# Environment Variables from GitHub Secrets
DUO_API_HOST = os.environ.get("DUO_HOST")
DUO_ADMIN_IKEY = os.environ.get("DUO_IKEY")
DUO_ADMIN_SKEY = os.environ.get("DUO_SKEY")
DUO_AUTH_IKEY = os.environ.get("DUO_AUTH_IKEY")
DUO_AUTH_SKEY = os.environ.get("DUO_AUTH_SKEY")

if not all([DUO_API_HOST, DUO_ADMIN_IKEY, DUO_ADMIN_SKEY, DUO_AUTH_IKEY, DUO_AUTH_SKEY]):
    print("Error: Missing required GitHub Secrets.")
    sys.exit(1)

# Initialize API Clients
admin_api = duo_client.Admin(ikey=DUO_ADMIN_IKEY, skey=DUO_ADMIN_SKEY, host=DUO_API_HOST)
auth_api = duo_client.Auth(ikey=DUO_AUTH_IKEY, skey=DUO_AUTH_SKEY, host=DUO_API_HOST)

def run_pipeline():
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    target_user = "pavitra"
    
    print(f"[{timestamp}] Triggering events on Cisco Duo...")

    # 1. TRIGGER ADMIN LOG (Updates user notes)
    print("\n[1/2] Generating Administrator Event...")
    try:
        users = admin_api.get_users_by_name(username=target_user)
        if users:
            user_id = users[0]["user_id"]
            admin_api.update_user(user_id=user_id, notes=f"Automated test trigger - {timestamp}")
            print("  -> Admin event successfully triggered!")
        else:
            print(f"  -> User '{target_user}' not found.")
    except Exception as e:
        print(f"  -> Admin event failed: {str(e)}")

    # 2. TRIGGER AUTH LOG (Submits 2FA passcode attempt)
    print("\n[2/2] Generating User Authentication Event...")
    try:
        auth_api.auth(username=target_user, factor="passcode", passcode="000000")
        print("  -> User Authentication event successfully triggered!")
    except Exception as e:
        print(f"  -> Authentication event logged: {str(e)}")

    print("\nEvents triggered successfully. Go check your Cisco Duo UI for the new entries!")

if __name__ == "__main__":
    run_pipeline()
