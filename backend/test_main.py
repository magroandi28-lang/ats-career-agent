"""
Az ELSO teszt -- a legegyszerubb vegpontra (/healthz).

Ez bebizonyitja: a szerver elindul, a /healthz valaszol, es PONTOSAN azt
adja vissza, amit varunk tole.

Ket uj szo:
- TestClient: a FastAPI sajat teszt-eszkoze. Ugy hivhatod a vegpontjaidat,
  mintha egy bongeszo lenne, de kozben nem indul el valodi szerver -- gyors.
- assert: Python/pytest kulcsszo. Jelentese: "ellenorizd, hogy ez igaz-e --
  ha nem, a teszt piros lesz (elbukik), es pontosan megmutatja mi ternel el."
"""

from fastapi.testclient import TestClient

from backend.main import app

kliens = TestClient(app)


def test_healthz_valaszol():
    """A /healthz mindig 200-as statusszal es status='ok'-val valaszoljon."""
    valasz = kliens.get("/healthz")

    assert valasz.status_code == 200
    assert valasz.json() == {"status": "ok", "uzenet": "Elek!"}
