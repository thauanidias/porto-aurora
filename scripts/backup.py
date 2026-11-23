"""Encrypted PostgreSQL + uploads + application keys backup and isolated restore."""

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b"TGPMBACKUP1\n"


def run(args, *, output=None, source=None, env=None):
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        stdin=source,
        stdout=output or subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if result.returncode:
        # Arguments and environment can include secrets; never print them.
        raise RuntimeError(
            "Falha no comando " + args[0] + ". Consulte os logs locais do serviço."
        )
    return result.stdout


def key(password, salt):
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())


def crypt(source, target, password, decrypt=False):
    with source.open("rb") as inp, target.open("wb") as out:
        if decrypt:
            if inp.read(len(MAGIC)) != MAGIC:
                raise ValueError("Formato de backup inválido.")
            salt, nonce = inp.read(16), inp.read(12)
            payload_start = inp.tell()
            inp.seek(-16, 2)
            end = inp.tell()
            tag = inp.read(16)
            inp.seek(payload_start)
            transform = Cipher(
                algorithms.AES(key(password, salt)), modes.GCM(nonce, tag)
            ).decryptor()
            remaining = end - payload_start
            while remaining:
                chunk = inp.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("Backup truncado.")
                out.write(transform.update(chunk))
                remaining -= len(chunk)
            out.write(transform.finalize())
        else:
            salt, nonce = os.urandom(16), os.urandom(12)
            out.write(MAGIC + salt + nonce)
            transform = Cipher(
                algorithms.AES(key(password, salt)), modes.GCM(nonce)
            ).encryptor()
            while chunk := inp.read(1024 * 1024):
                out.write(transform.update(chunk))
            out.write(transform.finalize())
            out.write(transform.tag)


def unpack(backup, folder, password):
    archive = folder / "decrypted.tar"
    crypt(backup, archive, password, True)
    with tarfile.open(archive) as tar:
        if {item.name for item in tar.getmembers()} != {
            "database.dump",
            "uploads.tar.gz",
            ".env",
            "manifest.json",
        }:
            raise ValueError("Conteúdo inesperado no backup.")
        tar.extractall(folder, filter="data")
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        if (
            hashlib.file_digest((folder / name).open("rb"), "sha256").hexdigest()
            != expected
        ):
            raise ValueError("Falha de integridade: " + name)
    return manifest


def create(password):
    destination = ROOT / "backups"
    destination.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / ("tgpm-" + stamp + ".tgpmbackup")
    compose = ["docker", "compose"]
    with tempfile.TemporaryDirectory(prefix="tgpm-backup-") as temp:
        folder = Path(temp)
        run(compose + ["stop", "backend", "worker", "beat"])
        try:
            with (folder / "database.dump").open("wb") as output:
                run(
                    compose
                    + [
                        "exec",
                        "-T",
                        "postgres",
                        "sh",
                        "-c",
                        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
                    ],
                    output=output,
                )
            with (folder / "uploads.tar.gz").open("wb") as output:
                run(
                    compose
                    + [
                        "run",
                        "--rm",
                        "--no-deps",
                        "--user",
                        "root",
                        "backend",
                        "tar",
                        "czf",
                        "-",
                        "-C",
                        "/data/uploads",
                        ".",
                    ],
                    output=output,
                )
            shutil.copy2(ROOT / ".env", folder / ".env")
            manifest = {
                "created_at": stamp,
                "format": 1,
                "sha256": {
                    name: hashlib.file_digest(
                        (folder / name).open("rb"), "sha256"
                    ).hexdigest()
                    for name in ["database.dump", "uploads.tar.gz", ".env"]
                },
            }
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
            archive = folder / "backup.tar"
            with tarfile.open(archive, "w") as tar:
                for name in [
                    "database.dump",
                    "uploads.tar.gz",
                    ".env",
                    "manifest.json",
                ]:
                    tar.add(folder / name, arcname=name)
            crypt(archive, target, password)
        finally:
            run(compose + ["start", "backend", "worker", "beat"])
    print("Backup criptografado: " + str(target))
    return target


def restore(backup, password, project, port):
    if not re.fullmatch(r"tgpm-restored-[a-z0-9-]{3,40}", project):
        raise ValueError("Use um nome novo iniciado por tgpm-restored-.")
    if not 1024 <= port <= 65535 or port == 8088:
        raise ValueError("Informe porta alternativa de 1024 a 65535.")
    if (
        project
        in run(["docker", "compose", "ls", "--all", "--format", "json"]).decode()
    ):
        raise ValueError("O projeto já existe. A restauração exige um projeto novo.")
    folder = ROOT / "restores" / project
    if folder.exists():
        raise ValueError("Pasta de restauração já existe.")
    folder.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="tgpm-restore-") as temp:
        extracted = Path(temp)
        unpack(backup, extracted, password)
        environment = (extracted / ".env").read_text(encoding="utf-8")
        replacements = {
            "HTTP_PORT": str(port),
            "PUBLIC_URL": "http://localhost:" + str(port),
            "CORS_ORIGINS": "http://localhost:" + str(port),
            "ENVIRONMENT": "development",
            "SMTP_ENABLED": "false",
            "LDAP_ENABLED": "false",
            "GRAPH_ENABLED": "false",
            "WEBHOOK_ALLOWED_HOSTS": "",
        }
        for name, value in replacements.items():
            environment = re.sub(
                r"^" + name + r"=.*$",
                name + "=" + value,
                environment,
                flags=re.MULTILINE,
            )
        env_file = folder / ".env"
        env_file.write_text(environment, encoding="utf-8")
        env = os.environ.copy()
        env["TGPM_ENV_FILE"] = str(env_file)
        env["HTTP_PORT"] = str(port)
        compose = ["docker", "compose", "-p", project, "--env-file", str(env_file)]
        run(
            compose + ["build", "backend", "migrate", "worker", "beat", "frontend"],
            env=env,
        )
        run(compose + ["up", "-d", "--wait", "postgres", "redis"], env=env)
        with (extracted / "database.dump").open("rb") as source:
            run(
                compose
                + [
                    "exec",
                    "-T",
                    "postgres",
                    "sh",
                    "-c",
                    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error',
                ],
                source=source,
                env=env,
            )
        with (extracted / "uploads.tar.gz").open("rb") as source:
            run(
                compose
                + [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--user",
                    "root",
                    "backend",
                    "tar",
                    "xzf",
                    "-",
                    "-C",
                    "/data/uploads",
                ],
                source=source,
                env=env,
            )
        # No notifications or integrations from the restored snapshot are delivered.
        run(
            compose
            + [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                "psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -v ON_ERROR_STOP=1 -c \"UPDATE webhooks SET enabled=false; UPDATE outbox SET status='DISABLED' WHERE kind IN ('EMAIL','WEBHOOK','GRAPH') AND status IN ('PENDING','RETRY');\"",
            ],
            env=env,
        )
        run(compose + ["up", "-d", "--wait"], env=env)
    print("Restauração isolada pronta: http://localhost:" + str(port))
    print("Ambiente: " + str(folder))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify", "restore"])
    parser.add_argument("--file", type=Path)
    parser.add_argument("--project", default="")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    password = os.environ.get("TGPM_BACKUP_PASSWORD") or getpass.getpass(
        "Senha de criptografia do backup (mínimo 16 caracteres): "
    )
    if len(password) < 16:
        raise ValueError("A senha deve ter pelo menos 16 caracteres.")
    if args.action == "create":
        create(password)
    elif not args.file or not args.file.is_file():
        raise ValueError("Informe --file com o backup existente.")
    elif args.action == "verify":
        with tempfile.TemporaryDirectory(prefix="tgpm-verify-") as temp:
            unpack(args.file, Path(temp), password)
        print("Autenticidade, descriptografia e hashes verificados.")
    else:
        restore(args.file, password, args.project, args.port)


if __name__ == "__main__":
    main()
