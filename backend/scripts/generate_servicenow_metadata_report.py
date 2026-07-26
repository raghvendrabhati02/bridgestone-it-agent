"""
generate_servicenow_metadata_report.py
─────────────────────────────────────────────────────────────────────────────
CLI Script to execute ServiceNow metadata validation and generate the official
docs/SERVICENOW_METADATA_REPORT.md file complete with metadata headers and
versioning timestamps.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.services.servicenow_metadata_cache import ServiceNowMetadataCache
from app.services.servicenow_metadata_validator import ServiceNowMetadataValidator


def main():
    print("==================================================")
    print("SERVICENOW METADATA REPORT GENERATOR")
    print("==================================================")

    # 1. Sync Cache
    cache = ServiceNowMetadataCache.get_instance()
    cache.sync(force=True)
    print(f"Metadata Cache Synced | Source: {cache.source} | Refreshed: {cache.last_refresh_iso}")

    # 2. Run Validator
    validator = ServiceNowMetadataValidator(cache=cache)
    report_md = validator.generate_report_markdown()

    # 3. Write to docs/SERVICENOW_METADATA_REPORT.md
    docs_dir = backend_dir.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "SERVICENOW_METADATA_REPORT.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[OK] Metadata Report generated successfully: {report_path}")
    print("==================================================")


if __name__ == "__main__":
    main()
