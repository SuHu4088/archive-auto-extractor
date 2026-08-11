"""password_manager tests: CRUD, two-step delete, git commits."""
from __future__ import annotations

from pathlib import Path

from archive_extractor.core.password_manager import PasswordVault


def test_add_list_toggle(vault: PasswordVault):
    e1 = vault.add_password("Pass111", label="common")
    e2 = vault.add_password("Secret!", label="backup")
    assert len(vault.list_entries()) == 2
    assert len(vault.list_entries(enabled_only=True)) == 2

    assert vault.set_enabled(e2.id, False)
    assert len(vault.list_entries(enabled_only=True)) == 1


def test_iter_passwords_priority(vault: PasswordVault):
    e1 = vault.add_password("Pass111", label="common")
    vault.add_password("backup", label="backup")
    # No successes yet — both have use_count 0; record_success on e1.
    vault.record_success(e1.id, "foo.7z")
    order = [e.label for e, _ in vault.iter_passwords_for("foo.7z")]
    assert order[0] == "common"  # higher use_count sorts first


def test_two_step_delete_requires_token(vault: PasswordVault):
    e = vault.add_password("temp", label="temp")
    token = vault.prepare_delete(e.id)
    assert token is not None
    # Wrong token must NOT consume the real one.
    assert vault.delete_password(e.id, "wrong-token") is False
    assert vault.delete_password(e.id, token) is True
    assert len(vault.list_entries()) == 0


def test_delete_without_prepare_fails(vault: PasswordVault):
    e = vault.add_password("temp", label="temp")
    assert vault.delete_password(e.id, "any-token") is False
    assert len(vault.list_entries()) == 1


def test_record_failure_all(vault: PasswordVault):
    vault.record_failure_all("unsolved.zip")
    # No exception is the contract; commit happens internally.


def test_git_commit_log_descriptive(vault: PasswordVault):
    e = vault.add_password("Pass111", label="common")
    vault.record_success(e.id, "foo.7z")
    vault.record_failure_all("bar.7z")
    log = vault.commit_log()
    log_text = "\n".join(log)
    assert "Initialize password vault" in log_text
    assert "Add password 'common'" in log_text
    assert "Record success for 'common' on foo.7z" in log_text
    assert "All passwords failed for bar.7z" in log_text
