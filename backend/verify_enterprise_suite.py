import sys
import subprocess

def run_suite():
    print("=" * 60)
    print("Executing Phase C - Enterprise End-to-End Journey & QA Suite")
    print("=" * 60)
    
    scripts = [
        "backend/verify_enterprise_scenarios.py",
        "backend/verify_conversation_quality.py",
        "backend/verify_dashboard_updates.py",
        "backend/verify_ticket_end_to_end.py"
    ]
    
    failed = False
    for script in scripts:
        print(f"\nRunning {script}...")
        res = subprocess.run([sys.executable, script])
        if res.returncode != 0:
            print(f"[FAIL] {script} returned non-zero exit status.")
            failed = True
        else:
            print(f"[OK] {script} passed.")
            
    print("\n" + "=" * 60)
    if failed:
        print("[FAIL] Phase C Verification failed! Please check logs.")
        sys.exit(1)
    else:
        print("[PASS] Phase C - Enterprise End-to-End Journey & QA Suite SUCCESS!")
        sys.exit(0)

if __name__ == "__main__":
    run_suite()
