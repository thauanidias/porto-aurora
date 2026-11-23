import hashlib
import io
import socket
import struct
import warnings
import zipfile
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import DomainError


def prepare_profile_photo(content: bytes) -> bytes:
    if not content or len(content) > 5 * 1024 * 1024:
        raise DomainError("Envie uma foto de até 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise DomainError("Envie uma foto em JPG, PNG ou WebP.")
                if source.width * source.height > 20_000_000:
                    raise DomainError("A foto deve ter no máximo 20 milhões de pixels.")
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGB")
                photo.thumbnail((800, 800))
                output = io.BytesIO()
                # Re-encode pixels only: never retain GPS/EXIF or uploaded executable content.
                photo.save(output, format="JPEG", quality=88)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise DomainError("Não foi possível ler a foto. Envie uma imagem JPG, PNG ou WebP válida.") from exc


def validate_file(filename: str, content: bytes, *, allow_doc: bool = False) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if not content or len(content) > settings().max_upload_mb * 1024 * 1024:
        raise DomainError("Arquivo vazio ou maior que o limite permitido.")
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise DomainError("O conteúdo não corresponde a um PDF válido.")
        return "application/pdf", suffix
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                names = {info.filename for info in infos}
                if not {"[Content_Types].xml", "word/document.xml"} <= names:
                    raise DomainError("O conteúdo não corresponde a um DOCX.")
                if len(infos) > 1000 or sum(i.file_size for i in infos) > 50 * 1024 * 1024:
                    raise DomainError("Arquivo compactado excede o limite de expansão.")
                if any(
                    "vbaproject" in name.lower() or name.startswith("/") or ".." in name.split("/")
                    for name in names
                ):
                    raise DomainError("Documento contém conteúdo não permitido.")
        except zipfile.BadZipFile as exc:
            raise DomainError("DOCX inválido.") from exc
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", suffix
    if suffix == ".doc" and allow_doc:
        from app.services.resume_profile import legacy_doc_text
        try:
            legacy_doc_text(content)
        except Exception as exc:
            raise DomainError("Não foi possível ler o DOC. Envie um DOC válido, PDF ou DOCX.") from exc
        return "application/msword", suffix
    raise DomainError("Envie somente PDF ou DOCX.")


def scan(content: bytes) -> str:
    if not settings().clamav_enabled:
        if settings().environment == "production":
            raise DomainError("Validação antimalware indisponível.", 503)
        return "NOT_CONFIGURED"
    try:
        with socket.create_connection((settings().clamav_host, 3310), timeout=15) as sock:
            sock.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 65536):
                chunk = content[offset : offset + 65536]
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))
            response = sock.recv(4096)
        if b"FOUND" in response:
            raise DomainError("O arquivo foi recusado pela verificação de segurança.")
        if b"OK" not in response:
            raise DomainError("Não foi possível validar o arquivo.", 503)
        return "CLEAN"
    except OSError as exc:
        raise DomainError("Verificação de arquivos indisponível. Tente novamente.", 503) from exc


def store_file(content: bytes, suffix: str) -> tuple[str, str]:
    key = uuid4().hex + suffix
    directory = Path(settings().upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / key).write_bytes(content)
    return key, hashlib.sha256(content).hexdigest()
