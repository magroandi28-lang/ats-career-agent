"""Biztonságos, felhasználói jóváhagyáshoz kötött CV-import."""

from io import BytesIO
import datetime
from pathlib import Path
from uuid import UUID, uuid4

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from utils.adatbazis import kliens


CV_BUCKET = "cv-fajlok"
MAX_PDF_PAGES = 100
MAX_EXTRACTED_CHARACTERS = 120_000


def _normalized_text(value: str) -> str:
    lines = []
    for line in value.replace("\x00", "").splitlines():
        cleaned = " ".join(line.split())
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def extract_pdf_text(content: bytes) -> str:
    """Szöveges PDF-ből determinisztikusan kinyeri az ellenőrizhető szöveget."""

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ValueError("A jelszóval védett PDF nem dolgozható fel.")
        if not reader.pages or len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("A PDF oldalszáma nem támogatott.")

        text = _normalized_text(
            "\n".join(page.extract_text() or "" for page in reader.pages)
        )
    except ValueError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise ValueError("A PDF szövege nem olvasható.") from exc

    if not text:
        raise ValueError(
            "A PDF nem tartalmaz kinyerhető szöveget. Kérjük, szöveges PDF-et tölts fel."
        )
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError("A kinyert CV-szöveg túl hosszú.")
    return text


def _safe_file_name(file_name: str) -> str:
    return Path(file_name or "cv.pdf").name[:255] or "cv.pdf"


def _public_import(job: dict) -> dict:
    input_ref = dict(job.get("input_ref") or {})
    result_ref = dict(job.get("result_ref") or {})
    review_status = result_ref.get("review_status", "pending")
    text = (
        result_ref.get("approved_text")
        if review_status == "approved"
        else result_ref.get("extracted_text")
    )
    return {
        "id": job["id"],
        "status": job["status"],
        "file_name": input_ref.get("file_name"),
        "storage_path": input_ref.get("storage_path"),
        "extracted_text": text or "",
        "character_count": len(text or ""),
        "review_status": review_status,
    }


def cv_import_create(user_id: str, file_name: str, content: bytes) -> dict | None:
    """Kinyeri és privát tárba menti a CV-t; a profilhoz még nem kapcsolja."""

    text = extract_pdf_text(content)
    db = kliens()
    if not db:
        return None

    import_id = str(uuid4())
    storage_path = f"{user_id}/{import_id}.pdf"
    now = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        db.storage.from_(CV_BUCKET).upload(
            storage_path,
            content,
            file_options={
                "content-type": "application/pdf",
                "upsert": "false",
            },
        )
        result = db.schema("private").table("background_jobs").insert({
            "id": import_id,
            "user_id": user_id,
            "job_type": "cv_import",
            "status": "succeeded",
            "input_ref": {
                "file_name": _safe_file_name(file_name),
                "storage_path": storage_path,
                "size_bytes": len(content),
            },
            "result_ref": {
                "extracted_text": text,
                "character_count": len(text),
                "review_status": "pending",
            },
            "attempt_count": 1,
            "started_at": now,
            "completed_at": now,
            "updated_at": now,
        }).execute()
        return _public_import(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"[cv_import_service] CV-import hiba: {exc}")
        return None


def cv_import_get(user_id: str, import_id: str) -> dict | None:
    """Csak a tulajdonos saját CV-importját adja vissza."""

    try:
        normalized_id = str(UUID(import_id))
    except (ValueError, TypeError, AttributeError):
        return None

    db = kliens()
    if not db:
        return None
    try:
        result = (
            db.schema("private")
            .table("background_jobs")
            .select("id,status,input_ref,result_ref")
            .eq("id", normalized_id)
            .eq("user_id", user_id)
            .eq("job_type", "cv_import")
            .limit(1)
            .execute()
        )
        return _public_import(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"[cv_import_service] CV-import lekeresesi hiba: {exc}")
        return None


def cv_import_mark_approved(
    user_id: str,
    import_id: str,
    approved_text: str,
) -> dict | None:
    """Rögzíti a felhasználó által ténylegesen átnézett CV-szöveget."""

    job = cv_import_get(user_id, import_id)
    if not job:
        return None

    cleaned = _normalized_text(approved_text)
    if not cleaned:
        raise ValueError("A jóváhagyott CV-szöveg nem lehet üres.")
    if len(cleaned) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError("A jóváhagyott CV-szöveg túl hosszú.")
    if job["review_status"] == "approved":
        if job["extracted_text"] == cleaned:
            return job
        raise ValueError("Ezt a CV-importot már más szöveggel jóváhagytad.")

    db = kliens()
    if not db:
        return None
    try:
        current = (
            db.schema("private")
            .table("background_jobs")
            .select("result_ref")
            .eq("id", import_id)
            .eq("user_id", user_id)
            .eq("job_type", "cv_import")
            .limit(1)
            .execute()
        )
        if not current.data:
            return None
        result_ref = dict(current.data[0].get("result_ref") or {})
        result_ref.update({
            "approved_text": cleaned,
            "character_count": len(cleaned),
            "review_status": "approved",
            "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        })
        result = (
            db.schema("private")
            .table("background_jobs")
            .update({
                "result_ref": result_ref,
                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            })
            .eq("id", import_id)
            .eq("user_id", user_id)
            .eq("job_type", "cv_import")
            .execute()
        )
        return _public_import(result.data[0]) if result.data else None
    except Exception as exc:
        print(f"[cv_import_service] CV-jovahagyasi hiba: {exc}")
        return None
