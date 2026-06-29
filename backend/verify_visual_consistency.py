import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def verify_visual_consistency():
    print("Running verify_visual_consistency.py...")
    
    # Path to frontend page
    page_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "app", "page.tsx"))
    if not os.path.exists(page_path):
        print(f"  [\u274c FAIL] Page path {page_path} not found.")
        sys.exit(1)
        
    failures = []
    
    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)
            
    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # 1. Verify no dummy EmptyState labels
    check(
        "No approvals available empty state replaced",
        "No approvals available" not in content,
        "Found legacy empty state label 'No approvals available'."
    )
    check(
        "No related requests empty state replaced",
        "No related requests" not in content,
        "Found legacy empty state label 'No related requests'."
    )
    check(
        "No customer comments empty state replaced",
        "No customer comments recorded." not in content,
        "Found legacy empty state label 'No customer comments recorded.'."
    )
    check(
        "No internal notes empty state replaced",
        "No internal notes recorded." not in content,
        "Found legacy empty state label 'No internal notes recorded.'."
    )

    # 2. Verify professional empty states are active
    check(
        "Polished approvals empty state present",
        "No approvals pending." in content,
        "Missing empty state: 'No approvals pending.'"
    )
    check(
        "Polished related empty state present",
        "No related incidents found." in content,
        "Missing empty state: 'No related incidents found.'"
    )
    check(
        "Polished customer comments empty state present",
        "No customer comments yet." in content,
        "Missing empty state: 'No customer comments yet.'"
    )
    check(
        "Polished internal notes empty state present",
        "No internal notes recorded yet." in content,
        "Missing empty state: 'No internal notes recorded yet.'"
    )

    if failures:
        print(f"[FAIL] verify_visual_consistency.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_visual_consistency.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_visual_consistency()
