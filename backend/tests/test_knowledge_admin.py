"""
test_knowledge_admin.py
─────────────────────────────────────────────────────────────────────────────
Backend tests for Knowledge Base admin operations (knowledge_admin_service.py).
"""

from __future__ import annotations

import os
import json
import shutil
import pytest
import app.services.knowledge_service as ks
import app.services.knowledge_admin_service as kas


@pytest.fixture(autouse=True)
def setup_teardown_kb():
    """Backup KB_DIR and restore it after each test to keep tests deterministic."""
    kb_backup = ks.KB_DIR + "_backup"
    if os.path.isdir(ks.KB_DIR):
        shutil.copytree(ks.KB_DIR, kb_backup)
    
    yield
    
    if os.path.isdir(ks.KB_DIR):
        shutil.rmtree(ks.KB_DIR)
    if os.path.isdir(kb_backup):
        shutil.copytree(kb_backup, ks.KB_DIR)
        shutil.rmtree(kb_backup)


def test_list_all_articles():
    articles = kas.list_all_articles()
    assert len(articles) > 0
    # Make sure we retrieve article_id for each
    ids = [a.get("article_id") for a in articles]
    assert "KB0001" in ids
    assert "KB0002" in ids


def test_get_article():
    art = kas.get_article("KB0002")
    assert art is not None
    assert art["title"] == "GlobalProtect VPN Connection Guide"
    assert art["category"] == "VPN"


def test_create_and_delete_article():
    all_init = kas.list_all_articles()
    num_init = len(all_init)

    new_art = kas.create_article({
        "title": "Test Creation SOP",
        "category": "PRINTER",
        "problem": "Test problem description",
        "keywords": ["test", "creation"]
    })

    assert new_art["article_id"].startswith("KB")
    assert new_art["status"] == "draft"
    assert new_art["version"] == "1.0"
    
    # Ensure file exists
    filepath = kas._find_file_by_article_id(new_art["article_id"])
    assert filepath is not None
    assert os.path.isfile(filepath)

    # Verify active chat cache does NOT load drafts
    ks.load_articles()
    assert ks.get_article(new_art["article_id"]) is None

    # Delete article
    res = kas.delete_article(new_art["article_id"])
    assert res is True
    assert kas._find_file_by_article_id(new_art["article_id"]) is None


def test_update_article():
    art = kas.get_article("KB0002")
    original_problem = art["problem"]

    updated = kas.update_article("KB0002", {"problem": "New problem desc VPN"})
    assert updated["problem"] == "New problem desc VPN"

    # Fetch again to verify persistence
    fetched = kas.get_article("KB0002")
    assert fetched["problem"] == "New problem desc VPN"


def test_publish_and_archive_lifecycle():
    # 1. Create a draft article
    draft = kas.create_article({
        "title": "Lifecycle SOP",
        "category": "OUTLOOK"
    })
    art_id = draft["article_id"]
    assert draft["status"] == "draft"
    assert draft["version"] == "1.0"

    # Verify not indexed
    ks.load_articles()
    assert ks.get_article(art_id) is None

    # 2. Publish
    published = kas.publish_article(art_id)
    assert published["status"] == "published"
    assert published["version"] == "1.1"

    # Verify archived version was written
    history = kas.get_version_history(art_id)
    assert len(history) == 1
    assert history[0]["version"] == "1.0"

    # Verify chatbot active index loads it now
    ks.load_articles()
    assert ks.get_article(art_id) is not None

    # 3. Archive
    archived = kas.archive_article(art_id)
    assert archived["status"] == "archived"

    # Verify chatbot active index excludes it again
    ks.load_articles()
    assert ks.get_article(art_id) is None


def test_upload_screenshot(tmp_path):
    dummy_content = b"fake-png-content"
    filename = "test_screenshot_upload.png"

    saved_filename = kas.upload_screenshot("KB0002", filename, dummy_content)
    assert saved_filename == filename

    # Verify saved on backend
    backend_file = os.path.join(kas.IMAGES_DIR, filename)
    assert os.path.isfile(backend_file)
    with open(backend_file, "rb") as f:
        assert f.read() == dummy_content

    # Clean up uploaded test files
    if os.path.isfile(backend_file):
        os.remove(backend_file)
    frontend_file = os.path.join(kas.FRONTEND_IMAGES_DIR, filename)
    if os.path.isfile(frontend_file):
        os.remove(frontend_file)
