# biometric_service.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from zk import ZK
from zk.exception import ZKNetworkError, ZKErrorResponse
from contextlib import contextmanager

app = FastAPI()

DEVICE_IP = '192.168.1.201'
DEVICE_PORT = 4370

@contextmanager
def get_device():
    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=5, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()
        yield conn
    finally:
        if conn:
            conn.enable_device()
            conn.disconnect()

# --- 1. Sync student to device ---
class StudentSync(BaseModel):
    uid: int          # your DB primary key (must be unique int)
    name: str
    user_id: str      # same as uid, as string

@app.post("/device/sync-student")
def sync_student(student: StudentSync):
    try:
        with get_device() as conn:
            conn.set_user(
                uid=student.uid,
                name=student.name[:24],
                privilege=0,
                password='',
                user_id=student.user_id
            )
        return {"status": "synced", "uid": student.uid}
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- 2. Trigger enrollment mode ---
@app.post("/device/enroll/{uid}")
def enroll_student(uid: int):
    try:
        with get_device() as conn:
            conn.enroll_user(uid=uid)
        return {"status": "enrollment_started", "uid": uid}
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- 3. Pull attendance logs ---
@app.get("/device/attendance")
def get_attendance():
    try:
        with get_device() as conn:
            logs = conn.get_attendance()
            return [
                {
                    "user_id": a.user_id,
                    "timestamp": str(a.timestamp),
                    "punch": a.punch  # 0=in, 1=out
                }
                for a in logs
            ]
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- 4. Get all users on device ---
@app.get("/device/users")
def get_users():
    try:
        with get_device() as conn:
            users = conn.get_users()
            return [
                {"uid": u.uid, "name": u.name, "user_id": u.user_id}
                for u in users
            ]
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))


# from zk import ZK
# from zk.exception import ZKNetworkError, ZKErrorResponse

# zk = ZK('192.168.1.201', port=4370, timeout=5, ommit_ping=True)
# conn = None
# try:
#     conn = zk.connect()
#     conn.disable_device()

#     # Check existing users
#     users = conn.get_users()
#     print(f"Total users on device: {len(users)}")
#     for user in users:
#         print(f"  UID: {user.uid} | Name: {user.name} | User ID: {user.user_id}")

#     # Check attendance logs
#     attendance = conn.get_attendance()
#     print(f"\nTotal attendance records: {len(attendance)}")

#     conn.enable_device()
# except ZKNetworkError as e:
#     print(f"Network error: {e}")
# except ZKErrorResponse as e:
#     print(f"Device error: {e}")
# finally:
#     if conn:
#         conn.disconnect()

# --- Delete a single user ---
@app.delete("/device/user/{uid}")
def delete_user(uid: int):
    try:
        with get_device() as conn:
            conn.delete_user(uid=uid)
        return {"status": "deleted", "uid": uid}
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- Get single user detail ---
@app.get("/device/user/{uid}")
def get_user(uid: int):
    try:
        with get_device() as conn:
            users = conn.get_users()
            user = next((u for u in users if u.uid == uid), None)
            if not user:
                raise HTTPException(status_code=404, detail="User not found on device")
            return {
                "uid": user.uid,
                "name": user.name,
                "user_id": user.user_id,
                "privilege": user.privilege,
                "password": user.password,
                "group_id": user.group_id,
            }
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- Clear all attendance logs ---
@app.delete("/device/attendance")
def clear_attendance():
    try:
        with get_device() as conn:
            conn.clear_attendance()
        return {"status": "cleared"}
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- Delete all users (factory reset users) ---
@app.delete("/device/users/all")
def delete_all_users():
    try:
        with get_device() as conn:
            conn.clear_data()
        return {"status": "all users and data cleared"}
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))

# --- Device info ---
@app.get("/device/info")
def device_info():
    try:
        zk = ZK('192.168.1.201', port=4370, timeout=5, ommit_ping=True)
        conn = zk.connect()
        info = {
            "firmware": conn.get_firmware_version(),
            "serialnumber": conn.get_serialnumber(),
            "platform": conn.get_platform(),
            "device_name": conn.get_device_name(),
            "user_count": conn.get_users_count() if hasattr(conn, 'get_users_count') else None,
            "time": str(conn.get_time()),
        }
        conn.disconnect()
        return info
    except ZKNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))