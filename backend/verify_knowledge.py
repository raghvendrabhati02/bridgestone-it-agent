"""
Verify knowledge_service functionality.
"""
import ast
import os
import shutil

# 1. AST check
ast.parse(open('app/services/knowledge_service.py', encoding='utf-8').read())
print("AST OK")

# 2. Imports check
from app.services.knowledge_service import (
    load_articles,
    search,
    search_by_category,
    get_article,
    get_troubleshooting_steps,
    get_screenshots,
    list_categories,
    get_guide_content,
)

# Initialize and bootstrap
load_articles()
print("Bootstrapped and loaded articles.")

# 3. Test list_categories
cats = list_categories()
assert "VPN" in cats
assert "PASSWORD_RESET" in cats
assert "GUEST_WIFI" in cats
assert "SHARED_MAILBOX" in cats
assert "IT_ASSET_ALLOCATION" in cats
# Placeholders
assert "SAP" in cats
assert "PRINTER" in cats
print("list_categories: OK")

# 4. Test search VPN
res_vpn = search("my vpn client is disconnected")
assert res_vpn["article"] is not None
assert res_vpn["article"]["category"] == "VPN"
assert res_vpn["confidence"] > 0.5
print("Search (VPN keyword): OK  confidence=%.2f" % res_vpn["confidence"])

# 5. Test search guest wifi
res_wifi = search("how do I get guest wifi internet portal access")
assert res_wifi["article"] is not None
assert res_wifi["article"]["category"] == "GUEST_WIFI"
print("Search (GUEST_WIFI keywords): OK  confidence=%.2f" % res_wifi["confidence"])

# 6. Test search placeholder (Printer)
res_print = search("my printer is not working")
assert res_print["article"] is not None
assert res_print["article"]["category"] == "PRINTER"
assert res_print["confidence"] == 0.5
print("Search placeholder fallback (PRINTER): OK")

# 7. Test get_article and details
art_id = "KB0001"
art = get_article(art_id)
assert art is not None
assert art["title"] == "Active Directory Password Reset Guide"

steps = get_troubleshooting_steps(art_id)
assert len(steps) == 5
assert steps[0] == "Verify employee identification details."

screens = get_screenshots(art_id)
assert len(screens) == 2
assert screens[0]["step"] == 2
assert screens[0]["image"] == "ad_search.png"
print("get_article + details + screenshots: OK")

# 8. Test legacy compatibility
content, filename = get_guide_content("VPN")
assert "GlobalProtect" in content
assert "gp_guide.json" in filename or "vpn_guide.json" in filename
print("Legacy backward compatibility get_guide_content: OK")

print("\nAll knowledge checks passed.")
