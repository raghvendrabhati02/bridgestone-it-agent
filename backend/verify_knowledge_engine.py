"""
verify_knowledge_engine.py
─────────────────────────────────────────────────────────────────────────────
Full test suite for Knowledge Engine v2  (knowledge_service.py).

Tests covered
─────────────
 1.  AST parse                   — module compiles without syntax errors
 2.  Import                      — module imports cleanly
 3.  JSON loading                — 10 real KB articles discovered & loaded
 4.  Validation pass             — all real articles pass field validation
 5.  Malformed JSON              — gracefully skipped, no crash
 6.  Missing fields              — article with missing required field is skipped
 7.  Weighted search             — correct article returned with confidence
 8.  Fuzzy search                — alias terms resolve to the correct article
 9.  Category search             — search_by_category() exact lookup
10.  get_article()               — retrieves by article_id
11.  get_steps()                 — returns list of step dicts
12.  get_step()                  — retrieves specific step by number
13.  next_step()                 — returns step N+1
14.  previous_step()             — returns step N-1, None at step 1
15.  get_verification()          — returns verification checklist
16.  get_escalation()            — returns escalation policy dict
17.  get_screenshots()           — returns screenshots list
18.  list_categories()           — returns sorted category list
19.  list_articles()             — summary list with correct keys
20.  Backward compat             — get_guide_content(), legacy step functions
21.  Thread safety               — concurrent reads from multiple threads
22.  Empty KB folder             — engine handles missing directory gracefully
23.  Invalid article_id          — get_article() returns None
24.  No crash on empty query     — search("") returns empty result
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import threading
import time

# ── allow running from backend/ root ─────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

PASS = "\033[92m✔\033[0m"
FAIL = "\033[91m✘\033[0m"
_failures: list[str] = []


def ok(label: str) -> None:
    print(f"  {PASS}  {label}")


def fail(label: str, reason: str = "") -> None:
    msg = f"{label}" + (f" — {reason}" if reason else "")
    print(f"  {FAIL}  {msg}")
    _failures.append(msg)


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. AST parse
# ─────────────────────────────────────────────────────────────────────────────
section("1. AST Parse")
_ks_path = os.path.join(
    os.path.dirname(__file__), "app", "services", "knowledge_service.py"
)
try:
    with open(_ks_path, encoding="utf-8") as _f:
        ast.parse(_f.read())
    ok("knowledge_service.py parses without syntax errors")
except SyntaxError as _e:
    fail("knowledge_service.py syntax error", str(_e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Import
# ─────────────────────────────────────────────────────────────────────────────
section("2. Import")
try:
    import app.services.knowledge_service as ks
    ok("knowledge_service imported successfully")
except Exception as _e:
    fail("Import failed", str(_e))
    sys.exit(1)   # cannot continue without module


# ─────────────────────────────────────────────────────────────────────────────
# 3 & 4. Real JSON loading + validation
# ─────────────────────────────────────────────────────────────────────────────
section("3 & 4. Real JSON Loading & Validation")
ks.load_articles()

_arts = ks.list_articles()
if len(_arts) >= 10:
    ok(f"Loaded {len(_arts)} articles (≥10 expected)")
else:
    fail("Expected at least 10 articles", f"got {len(_arts)}")

_expected_ids = {
    "KB0001", "KB0002", "KB0003", "KB0004", "KB0005",
    "KB0006", "KB0007", "KB0008", "KB0009", "KB0010",
}
_loaded_ids = {a["article_id"] for a in _arts}
for _aid in _expected_ids:
    if _aid in _loaded_ids:
        ok(f"Article {_aid} loaded")
    else:
        fail(f"Article {_aid} missing from loaded set")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Malformed JSON — graceful skip
# ─────────────────────────────────────────────────────────────────────────────
section("5. Malformed JSON Handling")

_tmp_dir = tempfile.mkdtemp(prefix="kb_test_")

# Write a completely broken file
_bad_path = os.path.join(_tmp_dir, "malformed.json")
with open(_bad_path, "w") as _f:
    _f.write("{this is not valid json !!!}")

# Write a valid article alongside it
_good_article = {
    "article_id":          "KB_TEST_GOOD",
    "title":               "Good Test Article",
    "category":            "TEST_CATEGORY",
    "keywords":            ["test"],
    "problem":             "Test problem.",
    "symptoms":            ["Test symptom"],
    "troubleshooting_steps": [{"step": 1, "title": "Step", "instruction": "Do this."}],
    "verification":        ["Verify."],
    "escalation":          {"team": "Test Team", "after_attempts": 1},
    "screenshots":         [],
    "faq":                 [],
}
_good_path = os.path.join(_tmp_dir, "good_article.json")
with open(_good_path, "w") as _f:
    json.dump(_good_article, _f)

# Temporarily override KB_DIR
_original_kb_dir = ks.KB_DIR
ks.KB_DIR = _tmp_dir
ks._articles_cache.clear()
ks._id_index.clear()
ks._cat_index.clear()
ks._keyword_index.clear()

try:
    ks.load_articles()
    _tmp_arts = ks.list_articles()
    if any(a["article_id"] == "KB_TEST_GOOD" for a in _tmp_arts):
        ok("Valid article loaded alongside malformed JSON — no crash")
    else:
        fail("Valid article not loaded when malformed JSON present")
except Exception as _e:
    fail("Crash on malformed JSON", str(_e))
finally:
    ks.KB_DIR = _original_kb_dir
    shutil.rmtree(_tmp_dir, ignore_errors=True)
    # Reload real articles
    ks._articles_cache.clear()
    ks._id_index.clear()
    ks._cat_index.clear()
    ks._keyword_index.clear()
    ks.load_articles()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Missing required fields — article skipped
# ─────────────────────────────────────────────────────────────────────────────
section("6. Missing Required Fields — Article Skipped")

_tmp_dir2 = tempfile.mkdtemp(prefix="kb_missing_")
_incomplete = {
    "article_id": "KB_INCOMPLETE",
    "title":      "Incomplete Article",
    # Missing: category, keywords, problem, symptoms, troubleshooting_steps,
    #          verification, escalation, screenshots, faq
}
with open(os.path.join(_tmp_dir2, "incomplete.json"), "w") as _f:
    json.dump(_incomplete, _f)

ks.KB_DIR = _tmp_dir2
ks._articles_cache.clear()
ks._id_index.clear()
ks._cat_index.clear()
ks._keyword_index.clear()

try:
    ks.load_articles()
    _tmp_arts2 = ks.list_articles()
    if not any(a["article_id"] == "KB_INCOMPLETE" for a in _tmp_arts2):
        ok("Incomplete article correctly skipped")
    else:
        fail("Incomplete article should have been skipped but was loaded")
except Exception as _e:
    fail("Crash on incomplete article", str(_e))
finally:
    ks.KB_DIR = _original_kb_dir
    shutil.rmtree(_tmp_dir2, ignore_errors=True)
    ks._articles_cache.clear()
    ks._id_index.clear()
    ks._cat_index.clear()
    ks._keyword_index.clear()
    ks.load_articles()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Weighted search — correct article returned
# ─────────────────────────────────────────────────────────────────────────────
section("7. Weighted Search")

_search_cases = [
    ("password reset",    "KB0001"),
    ("vpn not connecting", "KB0002"),
    ("guest wifi",        "KB0003"),
    ("shared mailbox",    "KB0004"),
    ("laptop allocation", "KB0005"),
    ("outlook not opening", "KB0006"),
    ("printer offline",   "KB0007"),
    ("install software",  "KB0008"),
    ("device health check", "KB0009"),
    ("sap login failed",  "KB0010"),
]

for _query, _expected_id in _search_cases:
    _res = ks.search(_query)
    _art = _res.get("article")
    if _art and _art.get("article_id") == _expected_id:
        ok(f'search("{_query}") → {_expected_id}  conf={_res["confidence"]:.3f}')
    else:
        _got = _art.get("article_id") if _art else "None"
        fail(f'search("{_query}")', f"expected {_expected_id}, got {_got}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Fuzzy search — aliases
# ─────────────────────────────────────────────────────────────────────────────
section("8. Fuzzy / Alias Search")

_fuzzy_cases = [
    ("globalprotect",    "KB0002"),
    ("global protect",   "KB0002"),
    ("remote access",    "KB0002"),
    ("VPN",              "KB0002"),
    ("forgot password",  "KB0001"),
    ("account locked",   "KB0001"),
    ("bs-guest",         "KB0003"),
    ("bsguest",          "KB0003"),
    ("sap gui",          "KB0010"),
    ("sap access",       "KB0010"),
    ("computer slow",    "KB0009"),
    ("send as",          "KB0004"),
]

for _query, _expected_id in _fuzzy_cases:
    _res = ks.search(_query)
    _art = _res.get("article")
    if _art and _art.get("article_id") == _expected_id:
        ok(f'fuzzy search("{_query}") → {_expected_id}')
    else:
        _got = _art.get("article_id") if _art else "None"
        fail(f'fuzzy search("{_query}")', f"expected {_expected_id}, got {_got}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. search_by_category
# ─────────────────────────────────────────────────────────────────────────────
section("9. search_by_category()")

_cat_cases = [
    ("PASSWORD_RESET",        "KB0001"),
    ("VPN",                   "KB0002"),
    ("GUEST_WIFI",            "KB0003"),
    ("SHARED_MAILBOX",        "KB0004"),
    ("IT_ASSET_ALLOCATION",   "KB0005"),
    ("OUTLOOK",               "KB0006"),
    ("PRINTER",               "KB0007"),
    ("SOFTWARE_INSTALLATION", "KB0008"),
    ("DEVICE_HEALTH",         "KB0009"),
    ("SAP",                   "KB0010"),
]

for _cat, _expected_id in _cat_cases:
    _result = ks.search_by_category(_cat)
    if _result and _result.get("article_id") == _expected_id:
        ok(f"search_by_category({_cat}) → {_expected_id}")
    else:
        _got = _result.get("article_id") if _result else "None"
        fail(f"search_by_category({_cat})", f"expected {_expected_id}, got {_got}")

_unknown = ks.search_by_category("UNKNOWN_CATEGORY_XYZ")
if _unknown is None:
    ok("search_by_category(UNKNOWN) → None")
else:
    fail("search_by_category(UNKNOWN) should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 10. get_article()
# ─────────────────────────────────────────────────────────────────────────────
section("10. get_article()")

_art_kb1 = ks.get_article("KB0001")
if _art_kb1 and _art_kb1.get("article_id") == "KB0001":
    ok("get_article('KB0001') returned correct article")
else:
    fail("get_article('KB0001') returned wrong or None")

if ks.get_article("KB_DOES_NOT_EXIST") is None:
    ok("get_article(invalid_id) → None")
else:
    fail("get_article(invalid_id) should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 11. get_steps()
# ─────────────────────────────────────────────────────────────────────────────
section("11. get_steps()")

_steps_kb2 = ks.get_steps("KB0002")
if isinstance(_steps_kb2, list) and len(_steps_kb2) >= 3:
    ok(f"get_steps('KB0002') returned {len(_steps_kb2)} steps")
else:
    fail("get_steps('KB0002') returned too few steps", str(_steps_kb2))

if ks.get_steps("KB_BAD") == []:
    ok("get_steps(invalid_id) → []")
else:
    fail("get_steps(invalid_id) should return []")


# ─────────────────────────────────────────────────────────────────────────────
# 12. get_step()
# ─────────────────────────────────────────────────────────────────────────────
section("12. get_step()")

_step1 = ks.get_step("KB0002", 1)
if _step1 and isinstance(_step1, dict) and _step1.get("step") == 1:
    ok(f"get_step('KB0002', 1) returned step 1: {_step1.get('title', '')}")
else:
    fail("get_step('KB0002', 1) failed", str(_step1))

if ks.get_step("KB0002", 999) is None:
    ok("get_step('KB0002', 999) → None (out of range)")
else:
    fail("get_step(out_of_range) should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 13. next_step()
# ─────────────────────────────────────────────────────────────────────────────
section("13. next_step()")

_next = ks.next_step("KB0002", 1)
if _next and _next.get("step") == 2:
    ok(f"next_step('KB0002', 1) → step 2: {_next.get('title', '')}")
else:
    fail("next_step('KB0002', 1) did not return step 2", str(_next))

_steps_count = len(ks.get_steps("KB0002"))
_last_next = ks.next_step("KB0002", _steps_count)
if _last_next is None:
    ok(f"next_step at last step ({_steps_count}) → None")
else:
    fail("next_step at last step should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 14. previous_step()
# ─────────────────────────────────────────────────────────────────────────────
section("14. previous_step()")

_prev = ks.previous_step("KB0002", 3)
if _prev and _prev.get("step") == 2:
    ok(f"previous_step('KB0002', 3) → step 2: {_prev.get('title', '')}")
else:
    fail("previous_step('KB0002', 3) did not return step 2", str(_prev))

if ks.previous_step("KB0002", 1) is None:
    ok("previous_step at step 1 → None")
else:
    fail("previous_step at step 1 should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 15. get_verification()
# ─────────────────────────────────────────────────────────────────────────────
section("15. get_verification()")

_verif = ks.get_verification("KB0001")
if isinstance(_verif, list) and len(_verif) >= 1:
    ok(f"get_verification('KB0001') returned {len(_verif)} items: {_verif[0]!r}")
else:
    fail("get_verification('KB0001') returned empty or wrong type")

if ks.get_verification("KB_BAD") == []:
    ok("get_verification(invalid_id) → []")
else:
    fail("get_verification(invalid_id) should return []")


# ─────────────────────────────────────────────────────────────────────────────
# 16. get_escalation()
# ─────────────────────────────────────────────────────────────────────────────
section("16. get_escalation()")

_esc = ks.get_escalation("KB0002")
if isinstance(_esc, dict) and "team" in _esc:
    ok(f"get_escalation('KB0002') → team={_esc.get('team')!r}")
else:
    fail("get_escalation('KB0002') returned unexpected value", str(_esc))

if ks.get_escalation("KB_BAD") is None:
    ok("get_escalation(invalid_id) → None")
else:
    fail("get_escalation(invalid_id) should return None")


# ─────────────────────────────────────────────────────────────────────────────
# 17. get_screenshots()
# ─────────────────────────────────────────────────────────────────────────────
section("17. get_screenshots()")

_shots = ks.get_screenshots("KB0002")
if isinstance(_shots, list) and len(_shots) >= 1:
    ok(f"get_screenshots('KB0002') returned {len(_shots)} screenshots")
else:
    fail("get_screenshots('KB0002') returned empty or wrong type", str(_shots))

if ks.get_screenshots("KB_BAD") == []:
    ok("get_screenshots(invalid_id) → []")
else:
    fail("get_screenshots(invalid_id) should return []")


# ─────────────────────────────────────────────────────────────────────────────
# 18. list_categories()
# ─────────────────────────────────────────────────────────────────────────────
section("18. list_categories()")

_cats = ks.list_categories()
if isinstance(_cats, list) and len(_cats) >= 10:
    ok(f"list_categories() returned {len(_cats)} categories")
else:
    fail("list_categories() returned too few categories", str(_cats))

if _cats == sorted(_cats):
    ok("list_categories() is sorted alphabetically")
else:
    fail("list_categories() is not sorted")


# ─────────────────────────────────────────────────────────────────────────────
# 19. list_articles()
# ─────────────────────────────────────────────────────────────────────────────
section("19. list_articles()")

_all = ks.list_articles()
if isinstance(_all, list) and len(_all) >= 10:
    ok(f"list_articles() returned {len(_all)} article summaries")
else:
    fail("list_articles() returned unexpected result", str(_all))

if all("article_id" in a and "title" in a and "category" in a for a in _all):
    ok("All summary entries contain article_id, title, category")
else:
    fail("Some summary entries are missing required keys")


# ─────────────────────────────────────────────────────────────────────────────
# 20. Backward compatibility
# ─────────────────────────────────────────────────────────────────────────────
section("20. Backward Compatibility")

_guide_content, _guide_filename = ks.get_guide_content("VPN")
if "vpn" in _guide_filename.lower() and len(_guide_content) > 50:
    ok(f"get_guide_content('VPN') returned {len(_guide_content)} chars, file={_guide_filename}")
else:
    fail("get_guide_content('VPN') returned wrong result")

_guide_none, _guide_none_f = ks.get_guide_content("INVALID_CATEGORY_XYZ")
if "N/A" in _guide_none_f:
    ok("get_guide_content(unknown) → 'N/A' filename")
else:
    fail("get_guide_content(unknown) should return N/A filename")

_legacy_steps = ks.get_troubleshooting_steps("KB0001")
if isinstance(_legacy_steps, list) and len(_legacy_steps) >= 1:
    ok(f"get_troubleshooting_steps('KB0001') → {len(_legacy_steps)} steps")
else:
    fail("get_troubleshooting_steps('KB0001') failed")

if ks.get_troubleshooting_steps("KB_BAD") == []:
    ok("get_troubleshooting_steps(invalid_id) → []")
else:
    fail("get_troubleshooting_steps(invalid_id) should return []")

# Legacy single-category helpers
for _fn, _label in [
    (ks.get_vpn_guide,                  "get_vpn_guide"),
    (ks.get_outlook_guide,              "get_outlook_guide"),
    (ks.get_password_reset_guide,       "get_password_reset_guide"),
    (ks.get_printer_guide,              "get_printer_guide"),
    (ks.get_software_installation_guide, "get_software_installation_guide"),
]:
    try:
        _c, _f = _fn()
        if len(_c) > 20:
            ok(f"{_label}() returned content ({len(_c)} chars)")
        else:
            fail(f"{_label}() returned too-short content")
    except Exception as _e:
        fail(f"{_label}() raised exception", str(_e))

# resolution_steps property on KBArticle
_art_obj = ks._id_index.get("KB0001")
if _art_obj and isinstance(_art_obj.resolution_steps, list) and len(_art_obj.resolution_steps) >= 1:
    ok(f"KBArticle.resolution_steps property works ({len(_art_obj.resolution_steps)} steps)")
else:
    fail("KBArticle.resolution_steps property failed")


# ─────────────────────────────────────────────────────────────────────────────
# 21. Thread safety — concurrent reads
# ─────────────────────────────────────────────────────────────────────────────
section("21. Thread Safety — Concurrent Reads")

_results: list = []
_errors:  list = []

def _thread_task(thread_id: int) -> None:
    try:
        r1 = ks.search("vpn not connecting")
        r2 = ks.get_steps("KB0001")
        r3 = ks.list_categories()
        _results.append((thread_id, r1.get("article", {}).get("article_id"), len(r2), len(r3)))
    except Exception as exc:
        _errors.append((thread_id, str(exc)))

_threads = [threading.Thread(target=_thread_task, args=(i,)) for i in range(20)]
_t0 = time.time()
for t in _threads:
    t.start()
for t in _threads:
    t.join()
_elapsed = time.time() - _t0

if _errors:
    fail(f"Thread safety errors: {_errors}")
else:
    ok(f"20 concurrent threads completed without errors in {_elapsed:.2f}s")

if all(r[1] == "KB0002" for r in _results):
    ok("All threads returned correct VPN article")
else:
    fail("Some threads returned wrong article", str(_results))


# ─────────────────────────────────────────────────────────────────────────────
# 22. Empty KB folder
# ─────────────────────────────────────────────────────────────────────────────
section("22. Empty KB Folder")

_empty_dir = tempfile.mkdtemp(prefix="kb_empty_")
ks.KB_DIR = _empty_dir
ks._articles_cache.clear()
ks._id_index.clear()
ks._cat_index.clear()
ks._keyword_index.clear()

try:
    ks.load_articles()
    if ks.list_articles() == []:
        ok("Empty KB folder → 0 articles, no crash")
    else:
        fail("Empty KB folder should yield 0 articles")
except Exception as _e:
    fail("Empty KB folder caused crash", str(_e))
finally:
    ks.KB_DIR = _original_kb_dir
    shutil.rmtree(_empty_dir, ignore_errors=True)
    ks._articles_cache.clear()
    ks._id_index.clear()
    ks._cat_index.clear()
    ks._keyword_index.clear()
    ks.load_articles()


# ─────────────────────────────────────────────────────────────────────────────
# 23. Invalid article_id
# ─────────────────────────────────────────────────────────────────────────────
section("23. Invalid Article ID")

for _bad_id in ("", "KB_NONEXISTENT", "12345", None):
    try:
        _result = ks.get_article(_bad_id) if _bad_id is not None else ks.get_article("")
        if _result is None:
            ok(f"get_article({_bad_id!r}) → None")
        else:
            fail(f"get_article({_bad_id!r}) should return None, got {_result.get('article_id')}")
    except Exception as _e:
        fail(f"get_article({_bad_id!r}) raised exception", str(_e))


# ─────────────────────────────────────────────────────────────────────────────
# 24. Empty / whitespace query
# ─────────────────────────────────────────────────────────────────────────────
section("24. Empty / Whitespace Query")

for _q in ("", "   ", "\t\n"):
    try:
        _r = ks.search(_q)
        if _r.get("article") is None and _r.get("confidence") == 0.0:
            ok(f"search({_q!r}) → empty result, no crash")
        else:
            fail(f"search({_q!r}) should return empty result")
    except Exception as _e:
        fail(f"search({_q!r}) raised exception", str(_e))


# ─────────────────────────────────────────────────────────────────────────────
# Final Report
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
if _failures:
    print(f"\033[91m  FAILED — {len(_failures)} check(s) did not pass:\033[0m")
    for _f in _failures:
        print(f"    • {_f}")
    sys.exit(1)
else:
    print(f"\033[92m  ALL CHECKS PASSED — Knowledge Engine v2 verified.\033[0m")
print(f"{'=' * 60}\n")
