import os
import subprocess
import glob

def run_all_tests():
    backend_dir = r"c:\Projects\bridgestone-it-agent\backend"
    python_exe = os.path.join(backend_dir, "venv_312", "Scripts", "python.exe")
    
    test_files = sorted(glob.glob(os.path.join(backend_dir, "verify_*.py")))
    print(f"Found {len(test_files)} verification scripts.")
    
    passed = []
    failed = []
    
    # Set TESTING environment variable to prevent APScheduler locking issues
    env = os.environ.copy()
    env["TESTING"] = "True"
    
    for test_file in test_files:
        basename = os.path.basename(test_file)
        # Skip this running script if it gets matched
        if basename == "run_all_tests.py":
            continue
        print(f"Running {basename}...")
        try:
            res = subprocess.run(
                [python_exe, test_file],
                capture_output=True,
                text=True,
                env=env,
                timeout=45
            )
            if res.returncode == 0:
                print(f"  [PASS] {basename}")
                passed.append(basename)
            else:
                print(f"  [FAIL] {basename}")
                print("--- STDOUT ---")
                print(res.stdout)
                print("--- STDERR ---")
                print(res.stderr)
                failed.append((basename, res.returncode, res.stdout, res.stderr))
        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] {basename}")
            failed.append((basename, "TIMEOUT", "", "Timeout Expired after 45s"))
        except Exception as e:
            print(f"  [ERROR] {basename}: {e}")
            failed.append((basename, "ERROR", "", str(e)))
            
    print("\n=================================")
    print(f"Passed: {len(passed)} / {len(test_files)}")
    print(f"Failed: {len(failed)} / {len(test_files)}")
    print("=================================")
    if failed:
        print("\nFailing Tests Summary:")
        for name, code, stdout, stderr in failed:
            print(f"- {name} (Return Code: {code})")

if __name__ == "__main__":
    run_all_tests()
