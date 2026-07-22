"""
Auth-segédlet -- Karrier-Ugynokseg backend

Ez adja a "vedett vegpont" mechanizmust: egy FastAPI Depends()-fuggvenyt,
ami minden hivasnal ellenorzi, hogy valodi, ervenyes Supabase-tokent
kuldtek-e a keresben. Ha nem, 401-es hibat ad (nem enged tovabb).

A tenyleges regisztracio/bejelentkezes a Supabase Auth (GoTrue) sajat
szolgaltatasa -- mi csak wrappeljuk, nem irjuk ujra a jelszo-kezelest.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

from utils.adatbazis import kliens, SUPABASE_URL, SUPABASE_SERVICE_KEY

_bearer = HTTPBearer()


def friss_auth_kliens():
    """
    FONTOS: a bejelentkezés/regisztráció (sign_in_with_password / sign_up)
    a KLIENS OBJEKTUM SAJÁT munkamenetét átírja a bejelentkező felhasználóéra
    -- élőben leteszteltük: ha ugyanazt a kliens-példányt használnánk, mint
    amit a kliens() (utils/adatbazis.py) mindenhol máshol megoszt, akkor egy
    bejelentkezés után a szolgáltatás-szintű (service_role) jogosultság
    ELVESZNE a teljes megosztott kliensről -- minden további Storage/DB
    művelet (más felhasználóké is!) ez után hibázna vagy rossz jogosultsággal
    futna. Ezért az auth-műveletekhez MINDIG egy ÚJ, eldobható klienst
    hozunk létre -- ez sose szennyezi a megosztott, mindenki más által
    használt kliens()-t.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def jelenlegi_felhasznalo(hitelesites: HTTPAuthorizationCredentials = Depends(_bearer)):
    """
    Kiolvassa a kérés fejlécéből a tokent ("Authorization: Bearer <token>"),
    és a Supabase-szel ellenőrizteti, hogy valódi és érvényes-e.

    Ezt kell megadni bármelyik vegpontnak, amit csak bejelentkezett
    felhasznalo erhet el: @app.get("/valami") def x(felh=Depends(jelenlegi_felhasznalo)).
    """
    token = hitelesites.credentials
    db = kliens()
    if not db:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                             "Az adatbázis-kapcsolat nem elérhető.")
    try:
        valasz = db.auth.get_user(token)
    except Exception:
        valasz = None
    if not valasz or not valasz.user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                             "Érvénytelen vagy lejárt bejelentkezés.")
    return valasz.user
