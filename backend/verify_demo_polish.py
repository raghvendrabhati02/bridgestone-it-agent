import sys
import subprocess

def run_suite():
    print("=" * 60)
    print("Executing Phase B - Demo Artifact Removal & Production Polish Suite")
    print("=" * 60)
    
    scripts = [
        "backend/verify_demo_cleanup.py",
        "backend/verify_visual_consistency.py",
        "backend/verify_dashboard_numbers.py",
        "backend/verify_text_labels.py"
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
        print("[FAIL] Phase B Verification failed! Please check logs.")
        sys.exit(1)
    else:
        print("[PASS] Phase B - Demo Artifact Removal & Production Polish Suite SUCCESS!")
        sys.exit(0)

if __name__ == "__main__":
    run_suite()
