import os
import sys
import time
import random
import duo_client

# Load Cisco Duo Admin API credentials from GitHub Secrets / Environment
DUO_IKEY = os.environ.get("DUO_IKEY")
DUO_SKEY = os.environ.get("DUO_SKEY")
DUO_API_HOST = os.environ.get("DUO_API_HOST")

if not all([DUO_IKEY, DUO_SKEY, DUO_API_HOST]):
    print("Error: Missing required environment variables (DUO_IKEY, DUO_SKEY, DUO_API_HOST)")
    sys.exit(1)

# Initialize Duo Admin Client
admin_api = duo_client.Admin(
    ikey=DUO_IKEY,
    skey=DUO_SKEY,
    host=DUO_API_HOST
)

def generate_duo_events():
    random_id = str(random.randint(100000, 999999))
    username = f"test_user_{random_id}"
    group_name = f"Test_Group_{random_id}"
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    print(f"[{timestamp}] Starting Cisco Duo Event Generation Pipeline...")

    # 1. CREATE USER & GROUP (Triggers User & Group Management Events)
    print(f"\n[1/3] Creating User '{username}' and Group '{group_name}'...")
    try:
        user = admin_api.add_user(username=username, realname=f"Test User {random_id}")
        user_id = user["user_id"]
        print(f"  -> Created User ID: {user_id}")

        group = admin_api.add_group(name=group_name, desc="Automated test log group")
        group_id = group["group_id"]
        print(f"  -> Created Group ID: {group_id}")

        # Associate User with Group
        admin_api.add_user_group(user_id=user_id, group_id=group_id)
        print(f"  -> Associated User {user_id} with Group {group_id}")
    except Exception as e:
        print(f"  -> Error creating User/Group: {str(e)}")
        return

    time.sleep(2)

    # 2. TRIGGER ADMIN LOG (Updating User Attributes)
    print("\n[2/3] Triggering Administrator Activity Log...")
    try:
        # Updating user details generates an Admin Audit Log event
        admin_api.update_user(user_id=user_id, notes="Automated test log event update - User Retained")
        print("  -> User updated successfully (Admin Log Event Generated)")
    except Exception as e:
        print(f"  -> Error generating Admin Log event: {str(e)}")

    # 3. TRIGGER TELEPHONY & AUTHENTICATION LOG ATTEMPTS
    print("\n[3/3] Triggering Telephony & Auth Verification Checks...")
    try:
        # Fetching user bypass codes triggers an Auth/Security Audit Event
        bypass_codes = admin_api.get_user_bypass_codes(user_id=user_id)
        print(f"  -> Checked bypass code status for User {user_id} (Auth/Security Audit Event Generated)")
    except Exception as e:
        print(f"  -> Error triggering Auth/Telephony event: {str(e)}")

    print("\nPipeline execution completed. User and Group have been retained in Cisco Duo.")

if __name__ == "__main__":
    generate_duo_events()
