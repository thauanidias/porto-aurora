"""Exercise encrypted backup and restoration into a disposable, isolated Compose project."""

import os
import secrets
import shutil
import tempfile
import urllib.request
from pathlib import Path

import backup
from cryptography.exceptions import InvalidTag

password = secrets.token_urlsafe(36)
project = "tgpm-restored-qa-" + secrets.token_hex(4)
folder = backup.ROOT / "restores" / project
archive = None
try:
    archive = backup.create(password)
    with tempfile.TemporaryDirectory(prefix="tgpm-qa-") as temp:
        metadata = backup.unpack(archive, Path(temp), password)
        assert set(metadata["sha256"]) == {"database.dump", "uploads.tar.gz", ".env"}
    try:
        with tempfile.TemporaryDirectory(prefix="tgpm-qa-wrong-") as temp:
            backup.unpack(archive, Path(temp), password + "wrong")
    except InvalidTag:
        print("Senha incorreta rejeitada.", flush=True)
    else:
        raise AssertionError("Senha incorreta aceita")
    backup.restore(archive, password, project, 8099)
    with urllib.request.urlopen(
        "http://localhost:8099/readiness", timeout=15
    ) as response:
        assert response.status == 200
    env = os.environ.copy()
    env["TGPM_ENV_FILE"] = str(folder / ".env")
    env["HTTP_PORT"] = "8099"
    command = ["docker", "compose", "-p", project, "--env-file", str(folder / ".env")]
    counts = (
        backup.run(
            command
            + [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM candidates), (SELECT count(*) FROM vacancies);"',
            ],
            env=env,
        )
        .decode()
        .strip()
    )
    assert counts == "0|0|0", counts
    print(
        "Backup AES-GCM, hashes, senha incorreta e restauração isolada: PASSOU. Base operacional inicial vazia preservada.",
        flush=True,
    )
finally:
    if folder.exists() and (folder / ".env").exists():
        env = os.environ.copy()
        env["TGPM_ENV_FILE"] = str(folder / ".env")
        backup.run(
            [
                "docker",
                "compose",
                "-p",
                project,
                "--env-file",
                str(folder / ".env"),
                "down",
                "-v",
            ],
            env=env,
        )
    if (
        folder.resolve().parent == (backup.ROOT / "restores").resolve()
        and folder.name.startswith("tgpm-restored-qa-")
        and folder.exists()
    ):
        shutil.rmtree(folder)
    if archive and archive.resolve().parent == (backup.ROOT / "backups").resolve():
        archive.unlink(missing_ok=True)
