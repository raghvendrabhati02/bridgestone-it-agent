import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def verify_text_labels():
    print("Running verify_text_labels.py...")
    
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
        
    # 1. Verify legacy labels are removed
    # Outcome Details should not be in the file as a header label
    check(
        "Outcome Details label removed",
        "Outcome Details" not in content,
        "Found legacy label 'Outcome Details' in page.tsx."
    )
    # Action Executed should not be in the file as a label
    check(
        "Action Executed label removed",
        "Action Executed" not in content,
        "Found legacy label 'Action Executed' in page.tsx."
    )
    
    # 2. Verify new professional labels are active
    check(
        "Resolution Summary label active",
        "Resolution Summary" in content,
        "Missing professional label: 'Resolution Summary'"
    )
    check(
        "Recent Actions label active",
        "Recent Actions" in content,
        "Missing professional label: 'Recent Actions'"
    )
    
    # 3. Check for hardcoded employee directory mapping in ticket items
    check(
        "Enterprise employee mapping active in tickets",
        "Rahul Sharma" in content and "Priya Verma" in content and "Amit Patel" in content,
        "Missing enterprise directory mapping for ticket items."
    )

    if failures:
        print(f"[FAIL] verify_text_labels.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_text_labels.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_text_labels()
