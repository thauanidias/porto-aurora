"""Read CV text locally and suggest only explicitly recognizable profile facts."""

import io
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from pypdf import PdfReader

from app.core.errors import DomainError


def legacy_doc_text(content: bytes) -> str:
    if not content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ValueError("DOC inválido")
    if not shutil.which("antiword"):
        raise ValueError("Leitor DOC indisponível")
    with TemporaryDirectory(prefix="tgpm-cv-") as directory:
        path = Path(directory) / "curriculo.doc"
        path.write_bytes(content)
        result = subprocess.run(["antiword", "-m", "UTF-8.txt", str(path)], capture_output=True, timeout=15, check=True)
        return result.stdout.decode("utf-8")[:50000]


def ocr_page(content: bytes, page_number: int) -> str:
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise ValueError("OCR indisponível")
    with TemporaryDirectory(prefix="tgpm-ocr-") as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(content)
        prefix = str(Path(directory) / "page")
        subprocess.run(["pdftoppm", "-f", str(page_number), "-l", str(page_number),
                        "-r", "140", "-scale-to", "2000", "-singlefile", "-png", str(source), prefix],
                       capture_output=True, timeout=15, check=True)
        result = subprocess.run(["tesseract", prefix + ".png", "stdout", "-l", "por+eng"],
                                capture_output=True, timeout=20, check=True)
        return result.stdout.decode("utf-8")


def read_resume(content: bytes, mime: str, progress=None) -> dict:
    metadata = {"pages": 1, "ocr_pages": []}
    try:
        if mime == "application/pdf":
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 30:
                raise ValueError("PDF protegido ou muito longo")
            metadata["pages"] = len(reader.pages)
            parts = []
            for index, page in enumerate(reader.pages):
                if progress:
                    progress(index, len(reader.pages))
                stream = page.get_contents()
                if stream and len(stream.get_data()) > 5 * 1024 * 1024:
                    raise ValueError("Página muito grande")
                page_text = page.extract_text(extraction_mode="layout") or ""
                if len(page_text.strip()) < 30:
                    page_text = ocr_page(content, index + 1)
                    metadata["ocr_pages"].append(index + 1)
                parts.append(page_text)
            text = "\n\f\n".join(parts)
        elif mime == "application/msword":
            text = legacy_doc_text(content)
        else:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                text = "\n".join(
                    "".join(node.text or "" for node in p.findall(".//w:t", ns)) for p in root.findall(".//w:p", ns)
                )
    except Exception as exc:
        raise DomainError(
            "O currículo foi salvo em Documentos, mas não foi possível ler seu texto. "
            "O arquivo pode estar protegido, ilegível ou exceder o limite de 30 páginas. "
            "Preencha o perfil manualmente ou envie um arquivo com texto selecionável.",
            422,
        ) from exc
    if len(text) > 300000:
        raise DomainError("O currículo excede 300 mil caracteres. Envie uma versão menor; nenhum trecho foi descartado silenciosamente.", 422)
    return {"text": text.strip(), **metadata}


def resume_text(content: bytes, mime: str) -> str:
    return read_resume(content, mime)["text"]


def profile_suggestions(text: str) -> dict:
    suggestions: dict[str, object] = {}
    phone = re.search(r"(?:\+55\s*)?\(?[1-9]\d\)?[ .-]*(?:9[ .-]*)?\d{4}[ .-]*\d{4}\b", text)
    if phone:
        suggestions["phone"] = phone.group().strip()
    lines = [re.sub(r"^[\s\x7f•●▪◦\-–]+", "", line).strip() for line in text.splitlines() if line.strip()]
    contact_end = next((index for index, line in enumerate(lines) if re.match(r"^(?:forma[cç][aã]o|experi[eê]ncia|cursos|certifica[cç][oõ]es|idiomas|habilidades|compet[eê]ncias)\b", line, re.I)), len(lines))
    for line in lines[:contact_end]:
        match = re.match(r"(?:nome(?: completo)?)\s*:\s*(.{3,180})$", line, re.I)
        if match:
            suggestions["name"] = match.group(1)
            break
    if "name" not in suggestions and lines and any(re.match(r"(?:telefone|celular|cidade|e-mail|email)\s*:", line, re.I) for line in lines[1:6]):
        header = lines[0]
        if not re.search(r"curr[ií]cul|resumo|objetivo|forma[cç][aã]o", header, re.I) and re.fullmatch(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+(?:\s+(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+|de|da|do|dos|das|e)){1,7}", header):
            suggestions["name"] = header
    for line in lines:
        location = re.fullmatch(r"(?:cidade\s*:\s*)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,100}?)\s*[-/,|]\s*([A-Z]{2})", line, re.I)
        if location and location[2].upper() in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split():
            suggestions["city"], suggestions["state"] = location[1].strip(), location[2].upper()
            break
    profile = {}
    links = list(dict.fromkeys(re.findall(r"https?://[^\s<>]+", text)))[:10]
    if links:
        profile["links"] = [link.rstrip(".,;)") for link in links]
    skills = next((re.split(r"\s*[,;|]\s*", line.split(":", 1)[1]) for line in lines
                   if re.match(r"(?:competências|competencias|habilidades)\s*:", line, re.I)), [])
    if skills:
        profile["skills"] = [skill.strip()[:180] for skill in skills if skill.strip()][:100]
    else:
        in_skills = False
        collected = []
        for line in lines:
            if re.fullmatch(r"(?:compet[eê]ncias(?: t[eé]cnicas)?|habilidades|conhecimentos(?: t[eé]cnicos)?)\s*:?", line, re.I):
                in_skills = True
                continue
            if in_skills and re.match(r"^(?:forma[cç][aã]o|experi[eê]ncia|objetivo|idiomas|cursos|certifica[cç][oõ]es|refer[eê]ncias|dados pessoais)\b", line, re.I):
                break
            if in_skills and len(line) >= 2:
                collected.append(line[:180])
        if collected:
            profile["skills"] = list(dict.fromkeys(collected))[:100]
    notes = []
    note_section = ""
    for line in lines:
        if re.fullmatch(r"(?:objetivo(?: profissional)?|experi[eê]ncia(?: profissional)?)\s*:?", line, re.I):
            note_section = line.rstrip(":")
            continue
        if re.match(r"^(?:forma[cç][aã]o|habilidades|compet[eê]ncias|idiomas|cursos|certifica[cç][oõ]es|refer[eê]ncias|dados pessoais)\b", line, re.I):
            note_section = ""
        if note_section:
            notes.append(line)
    if notes:
        profile["notes"] = "\n".join(notes)[:2000]
    if profile:
        suggestions["profile"] = profile
    return suggestions
