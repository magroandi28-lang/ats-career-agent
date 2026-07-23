"""Supabase Auth-integráció a FastAPI backendhez."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from backend.security import limit_auth_request, limit_user_request
from backend.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def friss_auth_kliens():
    """Minden auth-művelethez külön, publikus jogosultságú kliens készül."""

    settings = get_settings()
    if not settings.auth_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A bejelentkezés jelenleg nem elérhető.",
        )
    return create_client(
        settings.supabase_url,
        settings.supabase_publishable_key,
    )


def auth_keres_limit(request: Request) -> None:
    """Külön, IP-alapú védelem a regisztrációhoz és belépéshez."""

    limit_auth_request(request)


def jelenlegi_felhasznalo(
    request: Request,
    hitelesites: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Ellenőrzi a Bearer tokent a Supabase Auth szolgáltatásával."""

    if hitelesites is None or hitelesites.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bejelentkezés szükséges.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        valasz = friss_auth_kliens().auth.get_user(hitelesites.credentials)
    except Exception:
        valasz = None

    if not valasz or not valasz.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vagy lejárt bejelentkezés.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limit_user_request(request, str(valasz.user.id))
    request.state.user_id = str(valasz.user.id)
    return valasz.user
