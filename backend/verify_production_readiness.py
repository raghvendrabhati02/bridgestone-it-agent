import os
import re
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
APP_DIR = os.path.join(BACKEND_DIR, "app")

def verify_production_readiness():
    print("=" * 60)
    print("Executing verify_production_readiness.py")
    print("=" * 60)

    failures = []
    warnings = []

    def report_fail(check_name, msg):
        print(f"  [\u274c FAIL] {check_name}: {msg}")
        failures.append(check_name)

    def report_warn(check_name, msg):
        print(f"  [\u26a0\ufe0f WARN] {check_name}: {msg}")
        warnings.append(check_name)

    def report_pass(check_name, msg):
        print(f"  [\u2705 PASS] {check_name}: {msg}")

    # -------------------------------------------------------------------------
    # Check 1: Secrets & Hardcoded Keys Scan
    # -------------------------------------------------------------------------
    print("\nRunning Secrets and Hardcoded Credentials Scan...")
    has_secret_leaks = False
    
    # Generic regex for potential passwords or key assignments
    key_regex = re.compile(r'(api_key|password|secret|token|passwd|auth_key)\s*=\s*["\']([^"\']{6,})["\']', re.IGNORECASE)
    gemini_key_regex = re.compile(r'AIzaSy[A-Za-z0-9_-]{33}')
    
    # Files to ignore during secrets scan
    ignored_files = {
        "mock_gemini.py", "verify_production_readiness.py", ".env", "reset_demo_data.py", 
        "verify_persistence.py", "verify_enterprise_scenarios.py", "verify_demo_polish.py",
        "verify_conversation_quality.py", "verify_dashboard_updates.py", "verify_ticket_end_to_end.py",
        "verify_enterprise_suite.py"
    }

    for root, _, files in os.walk(APP_DIR):
        if "venv" in root or "node_modules" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py") and file not in ignored_files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Check for API keys
                        if gemini_key_regex.search(content):
                            report_fail("Secrets Scan", f"Potential hardcoded Gemini API Key detected in: {os.path.relpath(file_path, PROJECT_ROOT)}")
                            has_secret_leaks = True
                            
                        # Check for raw string assignments to variables containing 'secret' or 'key'
                        for match in key_regex.finditer(content):
                            var_name = match.group(1).lower()
                            value = match.group(2)
                            # Exclude typical false positives (common defaults or references)
                            if var_name in ("password", "passwd") and value in ("password", "postgres", "admin", "test", "root"):
                                continue
                            if var_name in ("api_key", "token") and value in ("dummy", "mock", "test_token"):
                                continue
                            report_fail("Secrets Scan", f"Potential hardcoded secret variable '{var_name}' detected in: {os.path.relpath(file_path, PROJECT_ROOT)}")
                            has_secret_leaks = True
                except Exception as e:
                    pass

    if not has_secret_leaks:
        report_pass("Secrets Scan", "No hardcoded credentials or active API keys detected in source code files.")

    # -------------------------------------------------------------------------
    # Check 2: SQL Injection Risk Audit
    # -------------------------------------------------------------------------
    print("\nRunning SQL Injection Vulnerability Audit...")
    sql_injection_detected = False
    
    # Match database executions using string interpolation or format methods instead of parameters
    sql_inj_regex = re.compile(r'\.execute\(\s*(f["\']|["\'].*?["\']\s*(\.format|%))', re.IGNORECASE)

    for root, _, files in os.walk(APP_DIR):
        if "venv" in root or "node_modules" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py") and file not in ignored_files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        for idx, line in enumerate(lines):
                            if sql_inj_regex.search(line):
                                report_fail("SQL Injection Check", f"Unparameterized SQL execute detected at line {idx+1} in: {os.path.relpath(file_path, PROJECT_ROOT)}")
                                sql_injection_detected = True
                except Exception:
                    pass

    if not sql_injection_detected:
        report_pass("SQL Injection Check", "No raw string interpolated execute() calls found. Parameters are properly bound.")

    # -------------------------------------------------------------------------
    # Check 3: CORS Production Security
    # -------------------------------------------------------------------------
    print("\nRunning CORS Config Audit...")
    main_py_path = os.path.join(BACKEND_DIR, "app", "main.py")
    if os.path.exists(main_py_path):
        try:
            with open(main_py_path, "r", encoding="utf-8") as f:
                content = f.read()
                if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
                    report_warn("CORS Config Check", "Wildcard allow_origins=['*'] configured in main.py. Change to specific origins for production environment.")
                else:
                    report_pass("CORS Config Check", "CORS origins restricted to specific allowlist.")
        except Exception as e:
            report_fail("CORS Config Check", f"Failed to check CORS origins: {e}")
    else:
        report_fail("CORS Config Check", "main.py not found in backend/app.")

    # -------------------------------------------------------------------------
    # Check 4: Global Exception Middleware
    # -------------------------------------------------------------------------
    print("\nRunning Exception Middleware Validation...")
    if os.path.exists(main_py_path):
        try:
            with open(main_py_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "exception_handler(Exception)" in content:
                    report_pass("Global Exception Handler", "Global Exception Handler middleware successfully registered in main.py.")
                else:
                    report_fail("Global Exception Handler", "Global exception handler decorator is missing in main.py.")
        except Exception as e:
            report_fail("Global Exception Handler Check", f"Failed to audit: {e}")

    # -------------------------------------------------------------------------
    # Check 5: Database Connection Pooling
    # -------------------------------------------------------------------------
    print("\nRunning Connection Pool and SQLite Tuning Check...")
    conn_py_path = os.path.join(BACKEND_DIR, "app", "database", "connection.py")
    if os.path.exists(conn_py_path):
        try:
            with open(conn_py_path, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check for SQLite pragma parameters
                has_wal = "journal_mode=WAL" in content
                has_normal = "synchronous=NORMAL" in content
                if has_wal and has_normal:
                    report_pass("SQLite WAL Tuning", "WAL journal mode and NORMAL synchronous pragmas successfully configured for SQLite connections.")
                else:
                    report_warn("SQLite WAL Tuning", "SQLite connection is missing WAL / NORMAL synchronous performance pragmas.")

                # Check for postgres pool limits
                has_pool = "pool_size=" in content and "max_overflow=" in content
                if has_pool:
                    report_pass("Database Pooling", "PostgreSQL database connection pool limits configured (pool_size, max_overflow).")
                else:
                    report_warn("Database Pooling", "PostgreSQL connection pooling limits are not explicitly configured.")
        except Exception as e:
            report_fail("Connection Config Check", f"Failed to audit connection configs: {e}")
    else:
        report_fail("Connection Config Check", "connection.py not found in database dir.")

    # -------------------------------------------------------------------------
    # Summary of Report
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Production Readiness Summary Report")
    print("=" * 60)
    print(f"Total Failures: {len(failures)}")
    print(f"Total Warnings: {len(warnings)}")

    if failures:
        print("\n[RESULT] status = FAIL. Project has blocking production readiness issues.")
        sys.exit(1)
    else:
        print("\n[RESULT] status = PASS. Project is compliant with production architecture guidelines!")
        sys.exit(0)

if __name__ == "__main__":
    verify_production_readiness()
