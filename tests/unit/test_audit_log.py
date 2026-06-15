import tempfile
import json
import pytest
from pathlib import Path
from nak.audit.audit_log import AuditLogger

def test_audit_log_basic_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.log"
        logger = AuditLogger(str(log_path))

        # Initially empty
        assert logger.get_current_size() == 0
        assert logger.get_entry_count() == 0
        assert logger.read_entries() == []
        assert logger.validate_integrity() is True

        # Log some entries
        logger.log("ws", "t1", "test.txt", "write", "h1", "h2", "approved", "patched")
        logger.log("ws", "t2", "test2.txt", "read", "h3", "h4", "approved", "patched")

        assert logger.get_entry_count() == 2
        entries = logger.read_entries()
        assert len(entries) == 2
        assert entries[0]["task_id"] == "t1"
        assert entries[1]["file_path"] == "test2.txt"
        assert logger.validate_integrity() is True

        # Truncate
        size_before_second = logger.get_current_size()
        # Log a third entry
        logger.log("ws", "t3", "test3.txt", "write", "h5", "h6", "approved", "patched")
        assert logger.get_entry_count() == 3

        # Truncate to size_before_second
        logger.truncate_to_size(size_before_second)
        assert logger.get_entry_count() == 2
        entries_after_trunc = logger.read_entries()
        assert len(entries_after_trunc) == 2
        assert entries_after_trunc[-1]["task_id"] == "t2"
        assert logger.validate_integrity() is True

def test_audit_log_invalid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "corrupt.log"
        logger = AuditLogger(str(log_path))

        # Write corrupt lines
        log_path.write_text("{\"valid\": true}\nthis is corrupt text\n")
        assert logger.get_entry_count() == 2
        assert logger.validate_integrity() is False
