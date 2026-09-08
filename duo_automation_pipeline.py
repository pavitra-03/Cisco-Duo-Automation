import os
import sys
import time
import random
import duo_client

# Load Cisco Duo Admin API credentials from GitHub Secrets / Environment
DUO_IKEY = os.environ.get("DUO_IKEY")
DUO_SKEY = os.environ.get("DUO_SKEY")
DUO_API_HOST = os.environ.get("DUO_HOST")

if not all([DUO_IKEY, DUO_SKEY, DUO_API_HOST]):
    print("Error: Missing required environment variables (DUO_IKEY, DUO_SKEY, DUO_HOST)")
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

    # 1. CREATE USER
    user_id = None
    print(f"\n[1/4] Creating User '{username}'...")
    try:
        user = admin_api.add_user(username=username, realname=f"Test User {random_id}")
        user_id = user["user_id"]
        print(f"  -> Success! Created User ID: {user_id}")
    except Exception as e:
        print(f"  -> Error creating User: {str(e)}")

    # 2. CREATE GROUP (FIX: Method is create_group, not add_group)
    group_id = None
    print(f"\n[2/4] Creating Group '{group_name}'...")
    try:
        group = admin_api.create_group(name=group_name, desc="Automated test log group")
        group_id = group["group_id"]
        print(f"  -> Success! Created Group ID: {group_id}")
    except Exception as e:
        print(f"  -> Error creating Group: {str(e)}")

    # 3. ASSOCIATE USER TO GROUP
    if user_id and group_id:
        print(f"\n[3/4] Associating User '{user_id}' with Group '{group_id}'...")
        try:
            admin_api.add_user_group(user_id=user_id, group_id=group_id)
            print("  -> Success! User added to group.")
        except Exception as e:
            print(f"  -> Error linking User to Group: {str(e)}")

    # 4. TRIGGER ADMIN LOG
    print("\n[4/4] Triggering Administrator Activity Log...")
    if user_id:
        try:
            admin_api.update_user(user_id=user_id, notes="Automated test log event update - User Retained")
            print("  -> User updated successfully (Admin Log Event Generated)")
        except Exception as e:
            print(f"  -> Error generating Admin Log event: {str(e)}")

    print("\nPipeline execution completed. Check your Duo Admin Console under Users and Groups.")

if __name__ == "__main__":
    generate_duo_events()
