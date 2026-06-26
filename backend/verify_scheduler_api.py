import subprocess
import time
import requests
import sys
import os

def main():
    print("\n" + "=" * 60)
    print("  VERIFY_SCHEDULER_API: FastAPI REST Endpoints Tests")
    print("=" * 60)

    print("Starting FastAPI backend on port 8080...")
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8080"],
        cwd=backend_dir,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    # Wait for uvicorn to start
    time.sleep(8)

    all_passed = True
    try:
        # Authenticate as ADMIN to perform administrative actions
        print("\n[TEST 1] Authenticating as ADMIN...")
        login_res = requests.post(
            "http://127.0.0.1:8080/auth/login",
            json={"username": "admin", "password": "adminpassword"}
        )
        if login_res.status_code != 200:
            print(f"  [FAIL] Login failed: {login_res.status_code} - {login_res.text}")
            all_passed = False
            return
        
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [PASS] Successfully logged in as ADMIN.")

        # Test 2: GET /jobs
        print("\n[TEST 2] GET /jobs: Checking active jobs configuration...")
        res = requests.get("http://127.0.0.1:8080/jobs", headers=headers)
        if res.status_code != 200:
            print(f"  [FAIL] GET /jobs returned status code {res.status_code}")
            all_passed = False
        else:
            jobs = res.json()
            print(f"  Info: Jobs listed from API: {[j.get('job_name') for j in jobs]}")
            if len(jobs) >= 3:
                print(f"  [PASS] Successfully retrieved {len(jobs)} background jobs config.")
            else:
                print(f"  [FAIL] Expected at least 3 jobs, got {len(jobs)}")
                all_passed = False

        # Test 3: POST /jobs/disable/{job_name}
        print("\n[TEST 3] POST /jobs/disable/notification_job...")
        res = requests.post("http://127.0.0.1:8080/jobs/disable/notification_job", headers=headers)
        if res.status_code != 200:
            print(f"  [FAIL] POST /jobs/disable returned status code {res.status_code}")
            all_passed = False
        else:
            print("  [PASS] Disable API returned success.")
            # Verify status in GET /jobs
            res_jobs = requests.get("http://127.0.0.1:8080/jobs", headers=headers).json()
            notif_job = next((j for j in res_jobs if j.get("job_name") == "notification_job"), None)
            if notif_job and not notif_job.get("is_enabled"):
                print("  [PASS] Job is_enabled successfully toggled to False in DB and scheduler.")
            else:
                print(f"  [FAIL] Job is_enabled is still: {notif_job.get('is_enabled') if notif_job else 'None'}")
                all_passed = False

        # Test 4: POST /jobs/enable/{job_name}
        print("\n[TEST 4] POST /jobs/enable/notification_job...")
        res = requests.post("http://127.0.0.1:8080/jobs/enable/notification_job", headers=headers)
        if res.status_code != 200:
            print(f"  [FAIL] POST /jobs/enable returned status code {res.status_code}")
            all_passed = False
        else:
            print("  [PASS] Enable API returned success.")
            # Verify status in GET /jobs
            res_jobs = requests.get("http://127.0.0.1:8080/jobs", headers=headers).json()
            notif_job = next((j for j in res_jobs if j.get("job_name") == "notification_job"), None)
            if notif_job and notif_job.get("is_enabled"):
                print("  [PASS] Job is_enabled successfully toggled to True.")
            else:
                print(f"  [FAIL] Job is_enabled is still: {notif_job.get('is_enabled') if notif_job else 'None'}")
                all_passed = False

        # Test 5: POST /jobs/run/{job_name}
        print("\n[TEST 5] POST /jobs/run/sla_monitor_job...")
        res = requests.post("http://127.0.0.1:8080/jobs/run/sla_monitor_job", headers=headers)
        if res.status_code != 200:
            print(f"  [FAIL] POST /jobs/run returned status code {res.status_code}")
            all_passed = False
        else:
            print("  [PASS] Manual run trigger returned success.")

        # Test 6: GET /jobs/history
        print("\n[TEST 6] GET /jobs/history...")
        res = requests.get("http://127.0.0.1:8080/jobs/history", headers=headers)
        if res.status_code != 200:
            print(f"  [FAIL] GET /jobs/history returned status code {res.status_code}")
            all_passed = False
        else:
            history = res.json()
            print(f"  Info: Total history rows returned: {len(history)}")
            if len(history) > 0:
                print("  [PASS] Job history successfully retrieved with logs.")
                print(f"         Latest log item: Job Name='{history[0]['job_name']}', Status='{history[0]['status']}'")
            else:
                print("  [FAIL] Expected history records but got 0.")
                all_passed = False

    except Exception as e:
        print("  [FAIL] Exception raised during API verification:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend on port 8080...")
        proc.terminate()
        proc.wait()

    print("\n" + "=" * 60)
    if all_passed:
        print("  ALL SCHEDULER API TESTS PASSED ✅")
        print("=" * 60 + "\n")
        sys.exit(0)
    else:
        print("  SOME SCHEDULER API TESTS FAILED ❌")
        print("=" * 60 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
