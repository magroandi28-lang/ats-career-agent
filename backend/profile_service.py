"""Szerveroldali, determinisztikus karrierprofil-szolgáltatás.

Az LLM nem írhat profilt. A felhasználó által megadott mezők először
vázlatba kerülnek, és csak kifejezett megerősítés után használhatók
személyre szabáshoz, rangsoroláshoz vagy dokumentumkészítéshez.
"""

from dataclasses import dataclass
import datetime
from typing import Final

from backend.career_state_machine import CareerIntent
from utils.adatbazis import kliens


PROFILE_RULE_VERSION: Final = "career-profile-v1"

STRING_FIELDS: Final = {
    "display_name",
    "current_role",
    "target_role",
    "location",
    "work_mode",
    "employment_type",
    "career_goal",
    "professional_summary",
    "cv_document_id",
    "job_ad_id",
}
LIST_FIELDS: Final = {
    "skills",
    "experience_roles",
    "education",
    "languages",
    "projects",
    "project_links",
    "constraints",
}
ALLOWED_FIELDS: Final = STRING_FIELDS | LIST_FIELDS


@dataclass(frozen=True)
class ProfileRequirement:
    code: str
    alternatives: tuple[str, ...]


COMMON_TARGET = ProfileRequirement("target_role", ("target_role",))
COMMON_SKILLS = ProfileRequirement("skills", ("skills",))
EXPERIENCE_OR_PROJECT = ProfileRequirement(
    "experience_or_project",
    ("experience_roles", "projects"),
)

REQUIREMENTS_BY_INTENT: Final[dict[CareerIntent, tuple[ProfileRequirement, ...]]] = {
    CareerIntent.CV_ELLENORZES: (
        ProfileRequirement("cv_document", ("cv_document_id",)),
    ),
    CareerIntent.CV_FRISSITES: (
        ProfileRequirement("cv_document", ("cv_document_id",)),
        COMMON_TARGET,
    ),
    CareerIntent.CV_KESZITES: (
        COMMON_TARGET,
        COMMON_SKILLS,
        EXPERIENCE_OR_PROJECT,
    ),
    CareerIntent.ALLAS_KERESES: (
        COMMON_TARGET,
        COMMON_SKILLS,
        ProfileRequirement("search_location", ("location", "work_mode")),
    ),
    CareerIntent.KONKRET_PALYAZAS: (
        ProfileRequirement("job_ad", ("job_ad_id",)),
        ProfileRequirement("cv_document", ("cv_document_id",)),
    ),
    CareerIntent.TANACSADAS: (
        ProfileRequirement("career_context", ("current_role", "career_goal")),
    ),
    CareerIntent.PALYAVALTAS: (
        ProfileRequirement("current_role", ("current_role",)),
        COMMON_SKILLS,
        ProfileRequirement("career_goal", ("career_goal",)),
    ),
    CareerIntent.PIACI_KORKEP: (COMMON_TARGET,),
    CareerIntent.KEPZES_KERESES: (COMMON_TARGET, COMMON_SKILLS),
    CareerIntent.PORTFOLIO: (
        ProfileRequirement("project", ("projects", "project_links")),
    ),
}


def _clean_string(value: object, max_length: int = 2000) -> str:
    if not isinstance(value, str):
        raise ValueError("A profilmező szöveges értéket vár.")
    cleaned = " ".join(value.strip().split())
    if not cleaned or len(cleaned) > max_length:
        raise ValueError("A profilmező üres vagy túl hosszú.")
    return cleaned


def sanitize_profile_patch(fields: dict) -> dict:
    """Zárt mezőlistát és méretkorlátokat érvényesít."""
    if not isinstance(fields, dict) or not fields:
        raise ValueError("Legalább egy profilmező szükséges.")
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Nem támogatott profilmező: {sorted(unknown)[0]}")

    cleaned = {}
    for field, value in fields.items():
        if field in STRING_FIELDS:
            cleaned[field] = _clean_string(value)
            continue
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise ValueError("A lista típusú profilmező 1–100 elemet vár.")
        cleaned[field] = [_clean_string(item, 500) for item in value]
    return cleaned


def confirmed_values(profile: dict | None) -> dict:
    return dict((profile or {}).get("confirmed_data") or {})


def missing_profile_fields(
    intent: CareerIntent,
    values: dict,
) -> list[str]:
    """Célfüggő kapu: nem létezik félrevezető, általános „100%-os profil”."""
    missing = []
    for requirement in REQUIREMENTS_BY_INTENT.get(intent, ()):
        if not any(values.get(field) for field in requirement.alternatives):
            missing.append(requirement.code)
    return missing


def profile_readiness(intent: CareerIntent, profile: dict | None) -> dict:
    values = confirmed_values(profile)
    missing = missing_profile_fields(intent, values)
    return {
        "ready": not missing,
        "missing_fields": missing,
        "confirmed_fields": sorted(values),
        "rule_version": PROFILE_RULE_VERSION,
    }


def profile_get_or_create(user_id: str) -> dict | None:
    db = kliens()
    if not db:
        return None
    try:
        table = db.schema("private").table("career_profiles")
        result = table.select(
            "id,draft_data,draft_version,confirmed_data,active_snapshot_id,updated_at"
        ).eq("user_id", user_id).limit(1).execute()
        if result.data:
            return result.data[0]
        created = table.insert({
            "user_id": user_id,
            "draft_data": {},
            "confirmed_data": {},
            "draft_version": 0,
            "rule_version": PROFILE_RULE_VERSION,
        }).execute()
        return created.data[0] if created.data else None
    except Exception as exc:
        print(f"[profile_service] profil-lekeres hiba: {exc}")
        return None


def profile_update_draft(user_id: str, fields: dict) -> dict | None:
    profile = profile_get_or_create(user_id)
    db = kliens()
    if not profile or not db:
        return None
    cleaned = sanitize_profile_patch(fields)
    draft = dict(profile.get("draft_data") or {})
    draft.update(cleaned)
    next_version = int(profile.get("draft_version") or 0) + 1
    try:
        result = (db.schema("private").table("career_profiles").update({
                "draft_data": draft,
                "draft_version": next_version,
                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            }).eq("id", profile["id"]).eq("user_id", user_id)
              .eq("draft_version", profile.get("draft_version", 0)).execute())
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"[profile_service] profil-vazlat hiba: {exc}")
        return None


def profile_confirm(
    user_id: str,
    fields: list[str],
    reason: str,
) -> dict | None:
    """A kiválasztott vázlatmezőket egy tranzakciós RPC erősíti meg."""
    profile = profile_get_or_create(user_id)
    db = kliens()
    if not profile or not db:
        return None
    if not fields or set(fields) - ALLOWED_FIELDS:
        raise ValueError("Csak létező, támogatott profilmező erősíthető meg.")
    draft = dict(profile.get("draft_data") or {})
    if any(field not in draft for field in fields):
        raise ValueError("Nem erősíthető meg hiányzó vázlatmező.")
    confirmed = dict(profile.get("confirmed_data") or {})
    confirmed.update({field: draft[field] for field in fields})
    try:
        result = db.schema("private").rpc("confirm_career_profile", {
            "p_user_id": user_id,
            "p_expected_draft_version": profile["draft_version"],
            "p_confirmed_data": confirmed,
            "p_reason": reason,
            "p_rule_version": PROFILE_RULE_VERSION,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"[profile_service] profil-megerosites hiba: {exc}")
        return None
