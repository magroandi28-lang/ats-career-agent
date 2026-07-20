# -*- coding: utf-8 -*-
"""EGÉSZ EMBER PROFIL — a kísérő ebből tudja, kivel beszél.

Csak a munkamenetben él (GDPR: nem tárolódik el sehova).
Minden modul ide írhat: CV-elemzés, teszt, jóllét-kérdések, érdeklődés.
"""

import streamlit as st


def profil() -> dict:
    """A munkamenet profil-objektuma (üres dict, ha még nincs semmi)."""
    return st.session_state.setdefault("profil", {})


def profil_frissit(**mezok):
    """Új információ beírása a profilba (a None/üres értékeket kihagyja)."""
    p = profil()
    for kulcs, ertek in mezok.items():
        if ertek not in (None, "", [], {}):
            p[kulcs] = ertek


def profil_osszefoglalo() -> str:
    """Rövid, ember-olvasható összefoglaló a sidebarba (és később a promptba).
    Üres string, ha még nincs profil."""
    p = profil()
    if not p:
        return ""
    sorok = []
    if p.get("szakma"):
        sorok.append(f"**Szakma:** {p['szakma']}")
    if p.get("keszsegek"):
        sorok.append(f"**Erősségek:** {', '.join(p['keszsegek'][:5])}")
    if p.get("holland_tipus"):
        sorok.append(f"**Érdeklődés-típus:** {p['holland_tipus']}")
    if p.get("karrierhorgony"):
        sorok.append(f"**Karrierhorgony:** {p['karrierhorgony']}")
    if p.get("jollet_jelzes"):
        sorok.append(f"**Jóllét:** {p['jollet_jelzes']}")
    if p.get("erdeklodes"):
        sorok.append(f"**Épp foglalkoztatja:** {', '.join(sorted(set(p['erdeklodes']))[:3])}")
    return "\n\n".join(sorok)


def erdeklodes_jelzes(mit: str):
    """Viselkedési jel rögzítése (pl. 'szakmaváltás', 'külföldi munka')."""
    p = profil()
    lista = p.setdefault("erdeklodes", [])
    if mit not in lista:
        lista.append(mit)
