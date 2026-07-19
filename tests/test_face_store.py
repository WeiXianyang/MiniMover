import pytest

from face import store


def _use_temp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "face_users.db")
    monkeypatch.setattr(store, "FACE_DIR", tmp_path / "face_images")
    store.init_db()


def test_demo_username_migration_is_idempotent_and_keeps_user_ids(monkeypatch, tmp_path):
    _use_temp_store(monkeypatch, tmp_path)
    first_id = store.create_user("\u9b4f\u8d24\u7080", "pw", "", "")
    second_id = store.create_user("\u9ec4\u7231\u96f7", "pw", "", "")

    assert store.migrate_demo_usernames() == 2
    assert store.migrate_demo_usernames() == 0

    assert store.get_user_by_id(first_id)["username"] == "\u5f20\u4e09"
    assert store.get_user_by_id(second_id)["username"] == "\u674e\u56db"


def test_demo_username_migration_rolls_back_on_target_conflict(monkeypatch, tmp_path):
    _use_temp_store(monkeypatch, tmp_path)
    old_id = store.create_user("\u9b4f\u8d24\u7080", "pw", "", "")
    store.create_user("\u5f20\u4e09", "pw", "", "")

    with pytest.raises(ValueError, match="target username already exists"):
        store.migrate_demo_usernames()

    assert store.get_user_by_id(old_id)["username"] == "\u9b4f\u8d24\u7080"
