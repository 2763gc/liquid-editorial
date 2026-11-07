import gzip
from datetime import datetime

import app.cli as cli


def test_backup_and_restore(tmp_path, monkeypatch):
    # 备份写到临时目录，不碰仓库里的 backups/（B25）
    monkeypatch.setattr(cli, "BASE_DIR", tmp_path)
    db_file = cli.get_raw_db_file()
    assert db_file.exists(), "测试库副本应当存在"

    cli.backup_database()

    today = datetime.now().strftime("%Y-%m-%d")
    backup_file = tmp_path / "backups" / today / "blog.db.gz"
    assert backup_file.exists(), f"备份文件 {backup_file} 应当存在"
    assert backup_file.stat().st_size > 0

    with gzip.open(backup_file, "rb") as f:
        assert f.read(16) == b"SQLite format 3\x00", "备份必须是合法的 SQLite 文件"
