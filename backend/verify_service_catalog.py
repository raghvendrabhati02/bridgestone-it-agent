import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.service_catalog import ServiceCatalogItem

def verify_catalog():
    print("=== Service Catalog Verification ===")
    db = SessionLocal()
    failures = []
    
    def check(name, condition, message):
        if condition:
            print(f"  [PASS] {name}: {message}")
        else:
            print(f"  [FAIL] {name}: {message}")
            failures.append(name)

    try:
        # 1. Total items count
        items_count = db.query(ServiceCatalogItem).count()
        check("Catalog Count", items_count == 15, f"Expected 15 service catalog items, got {items_count}.")
        
        # 2. Check a few specific items
        srv001 = db.query(ServiceCatalogItem).filter(ServiceCatalogItem.service_id == "SRV001").first()
        check("SRV001 Retrieval", srv001 is not None, "Failed to retrieve SRV001.")
        if srv001:
            check("SRV001 Name", srv001.name == "Software Installation", f"Expected Software Installation, got {srv001.name}.")
            check("SRV001 Approval Required", srv001.approval_required is True, "Expected approval_required to be True.")
            check("SRV001 Category", srv001.category == "Software", f"Expected category 'Software', got {srv001.category}.")

        srv005 = db.query(ServiceCatalogItem).filter(ServiceCatalogItem.service_id == "SRV005").first()
        check("SRV005 Retrieval", srv005 is not None, "Failed to retrieve SRV005.")
        if srv005:
            check("SRV005 Name", srv005.name == "Active Directory Account Unlock", f"Expected Active Directory Account Unlock, got {srv005.name}.")
            check("SRV005 Approval Required", srv005.approval_required is False, "Expected approval_required to be False.")

        # 3. Categories count
        categories = db.query(ServiceCatalogItem.category).distinct().all()
        categories = [c[0] for c in categories]
        check("Categories Distinct Count", len(categories) >= 5, f"Expected at least 5 distinct categories, got {len(categories)}: {categories}.")
        
        print("\n" + "="*55)
        if len(failures) == 0:
            print("  ALL SERVICE CATALOG CHECKS PASSED [OK]")
        else:
            print(f"  VERIFICATION FAILED: {len(failures)} checks failed [ERROR]")
        print("="*55)
        
    finally:
        db.close()

if __name__ == "__main__":
    verify_catalog()
