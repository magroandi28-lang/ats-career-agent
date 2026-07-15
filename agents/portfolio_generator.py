# -*- coding: utf-8 -*-
# Portfolio Generátor Ágens - agents/portfolio_generator.py
# CV (PDF) → adatkinyerés → HTML portfólió generálás

import anthropic
import json
import os
import re
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SABLON_UTVONAL = "templates/portfolio_sablon.html"

SZIN_PALETTA = {
    "arany":      {"accent": "#C9A84C", "accent2": "#E8C97A", "accent3": "rgba(201,168,76,0.15)",  "rgb": "201,168,76"},
    "kek":        {"accent": "#4A9EFF", "accent2": "#7BBFFF", "accent3": "rgba(74,158,255,0.15)",   "rgb": "74,158,255"},
    "turkiz":     {"accent": "#2DD4BF", "accent2": "#5EEAD4", "accent3": "rgba(45,212,191,0.15)",   "rgb": "45,212,191"},
    "lila":       {"accent": "#A78BFA", "accent2": "#C4B5FD", "accent3": "rgba(167,139,250,0.15)",  "rgb": "167,139,250"},
    "terrakotta": {"accent": "#F97316", "accent2": "#FB923C", "accent3": "rgba(249,115,22,0.15)",   "rgb": "249,115,22"},
    "zold":       {"accent": "#4ADE80", "accent2": "#86EFAC", "accent3": "rgba(74,222,128,0.15)",   "rgb": "74,222,128"},
    "rozsa":      {"accent": "#FB7185", "accent2": "#FDA4AF", "accent3": "rgba(251,113,133,0.15)",  "rgb": "251,113,133"},
    "ezust":      {"accent": "#94A3B8", "accent2": "#CBD5E1", "accent3": "rgba(148,163,184,0.15)",  "rgb": "148,163,184"},
}

# ── A "munkáid" szekció címkéi SZAKMA szerint ─────────────────
# A modell által felismert szakma/pozíció alapján átcímkézzük a PROJEKTEK szekciót,
# hogy ne mindenkinek "Projektek" legyen (orvosnak, jogásznak más illik).
MUNKA_CIMKEK = {
    "it":          {"eyebrow": "Munkáim",       "cim": "Projektek"},
    "egeszsegugy": {"eyebrow": "Szakmai munka", "cim": "Szakterületek & publikációk"},
    "jog":         {"eyebrow": "Szakmai munka", "cim": "Szakterületek & ügytípusok"},
    "penzugy":     {"eyebrow": "Munkáim",       "cim": "Elemzések & eredmények"},
    "mernok":      {"eyebrow": "Munkáim",       "cim": "Megvalósult munkák"},
    "alap":        {"eyebrow": "Munkáim",       "cim": "Kiemelt munkáim"},
}

# A szakma-specifikus EXTRA modul (publikációk/tanúsítványok/ügytípusok) szekciócíme
MODUL_CIMEK = {
    "it":          {"eyebrow": "Szakmai kiemelések", "cim": "Technológiai kiemelések"},
    "egeszsegugy": {"eyebrow": "Szakmai kiemelések", "cim": "Publikációk & szakterületek"},
    "jog":         {"eyebrow": "Szakmai kiemelések", "cim": "Ügytípusok & szakterületek"},
    "penzugy":     {"eyebrow": "Szakmai kiemelések", "cim": "Kiemelt elemzések & eredmények"},
    "mernok":      {"eyebrow": "Szakmai kiemelések", "cim": "Tanúsítványok & megvalósult munkák"},
    "alap":        {"eyebrow": "Szakmai kiemelések", "cim": "Kiemelések"},
}


def _szakma_kulcs(adatok: dict) -> str:
    """A felismert szakma kulcsa (it/egeszsegugy/jog/penzugy/mernok/alap)."""
    szoveg = f"{adatok.get('szakma_terulet','')} {adatok.get('pozicio','')}".lower()
    if any(k in szoveg for k in ["fejlesztő", "developer", "programoz", "it", "szoftver",
                                  "data", "adat", "mérnök informatik", "devops", "ai", "ml",
                                  "tesztel", "qa", "rendszergazda"]):
        return "it"
    if any(k in szoveg for k in ["orvos", "ápoló", "egészség", "gyógy", "klinik", "nővér", "doktor"]):
        return "egeszsegugy"
    if any(k in szoveg for k in ["jog", "ügyvéd", "jogász", "paraleg"]):
        return "jog"
    if any(k in szoveg for k in ["pénzügy", "közgazd", "számvitel", "könyvel", "controlling",
                                  "elemző", "bank", "audit", "finance"]):
        return "penzugy"
    if any(k in szoveg for k in ["mérnök", "engineer", "gépész", "építész", "villamos", "tervező"]):
        return "mernok"
    return "alap"


def _munka_cimke(adatok: dict) -> dict:
    """A felismert szakma alapján a munka-szekció címkéi."""
    return MUNKA_CIMKEK[_szakma_kulcs(adatok)]


def _csere_blokk(html, kezdo_jel, veg_jel, tartalom):
    """A kezdo_jel és veg_jel közti részt cseréli a tartalomra (a jelek megmaradnak)."""
    minta = re.escape(kezdo_jel) + r".*?" + re.escape(veg_jel)
    return re.sub(minta, kezdo_jel + tartalom + veg_jel, html, flags=re.DOTALL)


def adatok_kinyerese(cv_szoveg: str) -> dict:
    prompt = f"""Olvasd el ezt a CV-t és nyerd ki az adatokat PONTOSAN JSON formátumban.

FONTOS szabályok:
- Csak azt írd amit ténylegesen szerepel a CV-ben — ne találj ki semmit!
- Ha valami nem szerepel, írj null-t
- A szin_valasztas mezőbe válassz egyet: arany, kek, turkiz, lila, terrakotta, zold, rozsa, ezust
- A szín a szakmához és a CV által sugallt személyiséghez illjen

CV szövege:
{cv_szoveg}

Válaszolj KIZÁRÓLAG ezzel a JSON struktúrával, semmi más szöveg ne legyen:

{{
  "nev": "Teljes név",
  "nev_elso": "Keresztnév",
  "nev_vezetek": "Vezetéknév",
  "nev_rovid": "Monogram vagy rövid név pl. V. Andrea",
  "pozicio": "Jelenlegi vagy keresett pozíció",
  "szakma_terulet": "Pl. Mesterséges Intelligencia · Automatizáció",
  "email": "email@example.com",
  "telefon": "+36 XX XXX XXXX vagy null",
  "varos": "Város neve vagy null",
  "ev": "{datetime.now().year}",
  "evek_szama": "Pl. 19 — a legjelentősebb tapasztalat évei (csak szám)",
  "evek_label": "Pl. év tapasztalat",
  "szin_valasztas": "arany",
  "tapasztalat": [
    {{"ev": "2024–napjainkig", "cim": "Pozíció", "ceg": "Cég", "leiras": "Rövid leírás max 2 mondat"}}
  ],
  "tanulmanyok": [
    {{"ev": "2025–2026", "intezmeny": "Iskola/Egyetem", "vegzettseg": "Diploma/Tanfolyam"}}
  ],
  "keszsegek": [
    {{"kategoria": "Pl. Programozás", "elemek": ["skill1", "skill2", "skill3", "skill4"]}}
  ],
  "_keszseg_utasitas": "A keszsegek tömbbe 4-6 kategóriát adj, kategóriánként 4-8 konkrét elemmel — gazdag, részletes legyen, a CV alapján.",
  "nyelvek": [
    {{"nev": "Magyar", "szint": "Anyanyelv", "zaszlo": "HU"}}
  ],
  "poziciok_keresett": [
    {{"nev": "Pozíció", "tech": "Releváns technológiák/területek vesszővel"}}
  ],
  "szakma_kiemelesek": [
    {{"cim": "Pl. publikáció / tanúsítvány / kiemelt eredmény címe", "leiras": "1 mondat"}}
  ]
}}

A "szakma_kiemelesek" mezőbe CSAK akkor tegyél elemeket, ha a CV-ben TÉNYLEGESEN szerepelnek
ilyenek (publikációk, tanúsítványok, díjak, kiemelt eredmények, ügytípusok). Ha nincs ilyen, adj üres listát: []."""

    response = client.messages.create(
        model="claude-haiku-4-5", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    szoveg = response.content[0].text.strip()
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(szoveg)
    except json.JSONDecodeError:
        return {}


def szovegek_generalasa(adatok: dict, extra_info: dict) -> dict:
    # Az eredmények (számszerű sikerek) a felhasználótól jönnek — ha vannak,
    # ezeket KÖTELEZŐEN beleszőjük a bemutatkozásba és a cél-szövegbe, mert ettől hiteles.
    eredmenyek = (extra_info or {}).get("eredmenyek", "").strip()
    eredmeny_utasitas = ""
    if eredmenyek:
        eredmeny_utasitas = (
            f"\n\nA JELÖLT SZÁMSZERŰ EREDMÉNYEI (építsd be természetesen a bemutatkozásba "
            f"és a cél-szövegbe, mert ezek teszik hitelessé — ne csak felsorold, hanem mondatba ágyazd):\n{eredmenyek}"
        )

    prompt = f"""Te egy profi karriertanácsadó vagy aki portfólió szövegeket ír.
Magyar anyanyelvű, gördülékeny, magabiztos de hiteles szövegeket írsz.

A jelölt adatai:
- Név: {adatok.get('nev','')}
- Pozíció: {adatok.get('pozicio','')}
- Tapasztalat: {json.dumps(adatok.get('tapasztalat',[]), ensure_ascii=False)}
- Tanulmányok: {json.dumps(adatok.get('tanulmanyok',[]), ensure_ascii=False)}{eredmeny_utasitas}

Írj személyre szabott szövegeket. Válaszolj KIZÁRÓLAG JSON formátumban:

{{
  "bemutatkozas": "2-3 mondatos bemutatkozó, ami kiemeli az egyedi értéket. Magabiztos de hiteles.",
  "cel_szoveg": "3-4 mondatos célok és motiváció. Személyes és őszinte.",
  "kontakt_cim": "2-3 szavas fejléc pl. Dolgozzunk",
  "kontakt_cim_2": "1 szó kurzívhoz pl. együtt",
  "kontakt_szoveg": "1-2 mondatos megszólítás a recruitereknek"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )
    szoveg = response.content[0].text.strip()
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(szoveg)
    except json.JSONDecodeError:
        return {}


def _lista(d, kulcs):
    """Biztonságos lista-lekérés: ha hiányzik VAGY None, üres listát ad."""
    ertek = d.get(kulcs) if isinstance(d, dict) else None
    return ertek if isinstance(ertek, list) else []


def html_generalas(adatok: dict, szovegek: dict, extra_info: dict, foto_base64: str = None) -> str:
    with open(SABLON_UTVONAL, "r", encoding="utf-8") as f:
        html = f.read()

    szin_nev = adatok.get("szin_valasztas", "arany")
    if szin_nev not in SZIN_PALETTA:
        szin_nev = "arany"
    szin = SZIN_PALETTA[szin_nev]

    html = html.replace("{{ACCENT_SZIN}}", szin["accent"])
    html = html.replace("{{ACCENT_SZIN2}}", szin["accent2"])
    html = html.replace("{{ACCENT_SZIN3}}", szin["accent3"])
    html = html.replace("{{ACCENT_RGB}}", szin["rgb"])

    csere = {
        "{{NEV}}": adatok.get("nev", ""), "{{NEV_ELSO}}": adatok.get("nev_elso", ""),
        "{{NEV_VEZETEK}}": adatok.get("nev_vezetek", ""), "{{NEV_ROVID}}": adatok.get("nev_rovid", ""),
        "{{POZICIO}}": adatok.get("pozicio", ""), "{{SZAKMA_TERULET}}": adatok.get("szakma_terulet", ""),
        "{{EMAIL}}": adatok.get("email", ""), "{{TELEFON}}": adatok.get("telefon", "") or "",
        "{{VAROS}}": adatok.get("varos", "") or "", "{{EV}}": str(adatok.get("ev", datetime.now().year)),
        "{{EVEK_SZAMA}}": str(adatok.get("evek_szama", "") or ""), "{{EVEK_LABEL}}": adatok.get("evek_label", ""),
        "{{NYELV}}": "hu",
        "{{BEMUTATKOZAS}}": szovegek.get("bemutatkozas", ""), "{{CEL_SZOVEG}}": szovegek.get("cel_szoveg", ""),
        "{{CEL_CIM}}": (f"Cél: <em>{adatok.get('pozicio','')}</em>" if adatok.get('pozicio') else "Célom"),
        "{{KONTAKT_CIM}}": szovegek.get("kontakt_cim", "Dolgozzunk"),
        "{{KONTAKT_CIM_2}}": szovegek.get("kontakt_cim_2", "együtt"),
        "{{KONTAKT_SZOVEG}}": szovegek.get("kontakt_szoveg", ""),
        "{{GITHUB_LINK}}": extra_info.get("github", "") or "#",
        "{{GITHUB_LINK_ROVID}}": (extra_info.get("github", "") or "").replace("https://", "").replace("http://", ""),
        "{{LINKEDIN_LINK}}": extra_info.get("linkedin", "") or "#",
        "{{LINKEDIN_LINK_ROVID}}": (extra_info.get("linkedin", "") or "").replace("https://", "").replace("http://", ""),
        "{{DEMO_LINK}}": extra_info.get("demo_link", "") or "#",
        "{{DEMO_NEV}}": extra_info.get("demo_nev", "") or "",
    }
    for ph, ertek in csere.items():
        html = html.replace(ph, str(ertek) if ertek else "")

    # ── DUPLA STATISZTIKA a Cél-doboznál ──
    stat1 = str(adatok.get("evek_szama", "") or "").strip()
    stat1_label = adatok.get("evek_label", "") or "év tapasztalat"
    proj_szam = len([p for p in _lista(extra_info, "projektek") if p.get("cim")])
    stat2 = str(proj_szam) if proj_szam > 0 else ""
    stat2_label = "kiemelt projekt" if proj_szam > 0 else ""
    # Ha nincs év-szám, a projekt-szám lép az első helyre (ne legyen üres nagy szám)
    if not stat1:
        stat1, stat1_label = stat2, stat2_label
        stat2, stat2_label = "", ""
    if stat2:
        html = html.replace("{{STAT2}}", stat2).replace("{{STAT2_LABEL}}", stat2_label)
    else:
        html = _csere_blokk(html, "<!-- STAT2 START -->", "<!-- STAT2 END -->", "")
    html = html.replace("{{STAT1}}", stat1 or "").replace("{{STAT1_LABEL}}", stat1_label or "")

    # ── FOTÓ ──
    if foto_base64:
        foto = f'<div class="foto-keret"><img src="data:image/jpeg;base64,{foto_base64}" alt="{adatok.get("nev","")}"></div>'
    else:
        foto = f'<div class="foto-placeholder"><span>&#128100;</span><p>{adatok.get("nev_elso","")}</p></div>'
    html = _csere_blokk(html, "<!-- FOTO START -->", "<!-- FOTO END -->", foto)

    # ── TAPASZTALAT ──
    tap_html = ""
    for tap in _lista(adatok,"tapasztalat"):
        tap_html += f'''
    <div class="timeline-item">
      <div class="timeline-ev">{tap.get("ev","")}</div>
      <div class="timeline-cim">{tap.get("cim","")}</div>
      <div class="timeline-ceg">{tap.get("ceg","")}</div>
      <div class="timeline-leiras">{tap.get("leiras","")}</div>
    </div>'''
    html = _csere_blokk(html, "<!-- TAPASZTALAT TIMELINE START -->", "<!-- TAPASZTALAT TIMELINE END -->", tap_html)

    # ── TANULMÁNYOK ──
    tan_html = ""
    for tan in _lista(adatok,"tanulmanyok"):
        tan_html += f'''
    <div class="tanulmany-item">
      <div class="tanulmany-ev">{tan.get("ev","")}</div>
      <div class="tanulmany-nev">{tan.get("vegzettseg","")}</div>
      <div class="tanulmany-int">{tan.get("intezmeny","")}</div>
    </div>'''
    html = _csere_blokk(html, "<!-- TANULMANYOK START -->", "<!-- TANULMANYOK END -->", tan_html)

    # ── KÉSZSÉGEK ──
    keszs_html = ""
    for kat in _lista(adatok,"keszsegek"):
        elemek = "".join([f"<li>{e}</li>" for e in (kat.get("elemek") or [])])
        keszs_html += f'''
    <div class="keszs-kartya">
      <div class="keszs-cim">{kat.get("kategoria","")}</div>
      <ul class="keszs-lista">{elemek}</ul>
    </div>'''
    html = _csere_blokk(html, "<!-- KESZSEGEK START -->", "<!-- KESZSEGEK END -->", keszs_html)

    # ── PROJEKTEK / MUNKÁID (csak ha van) — SZAKMA szerint átcímkézve ──
    projektek = _lista(extra_info,"projektek")
    if projektek:
        cimke = _munka_cimke(adatok)
        proj_kartyak = ""
        for i, proj in enumerate(projektek):
            tagek = "".join([f'<span class="projekt-tag">{t}</span>' for t in (proj.get("tagek") or [])])
            ikon = (proj.get("ikon") or "").strip()
            ikon_html = f'<div class="projekt-ikon">{ikon}</div>' if ikon else ""
            # Szám / opcionális címke (pl. "01 / Diplomamunka")
            cimke_szoveg = (proj.get("cimke") or "").strip()
            szam = f"0{i+1}" + (f" / {cimke_szoveg}" if cimke_szoveg else "")
            # Akár 3 link: élő demó (primary), GitHub, egyéb (pl. rendszerterv)
            linkek_html = ""
            demo = (proj.get("demo_link") or "").strip()
            github = (proj.get("github_link") or "").strip()
            egyeb = (proj.get("egyeb_link") or "").strip()
            egyeb_nev = (proj.get("egyeb_nev") or "Megnézem").strip()
            # visszafelé kompatibilis: a régi egyszerű "link" mező
            regi = (proj.get("link") or "").strip()
            if demo:
                linkek_html += f'<a href="{demo}" target="_blank" class="projekt-link primary">&#128640; Élő demó</a>'
            if github:
                linkek_html += f'<a href="{github}" target="_blank" class="projekt-link">&#128230; GitHub</a>'
            if egyeb:
                linkek_html += f'<a href="{egyeb}" target="_blank" class="projekt-link">&#128203; {egyeb_nev}</a>'
            if not (demo or github or egyeb) and regi and regi != "#":
                linkek_html += f'<a href="{regi}" target="_blank" class="projekt-link">Megnézem &rarr;</a>'
            linkek_blokk = f'<div class="projekt-linkek">{linkek_html}</div>' if linkek_html else ""
            proj_kartyak += f'''
    <div class="projekt-kartya">
      <div class="projekt-szam">{szam}</div>
      {ikon_html}
      <h3 class="projekt-cim">{proj.get("cim","")}</h3>
      <p class="projekt-leiras">{proj.get("leiras","")}</p>
      <div class="projekt-tagek">{tagek}</div>
      {linkek_blokk}
    </div>'''
        proj_szekcio = f'''
<section id="projektek">
  <div class="szekc-eyebrow">{cimke["eyebrow"]}</div>
  <h2 class="szekc-cim">{cimke["cim"]}</h2>
  <div class="projektek-grid">{proj_kartyak}
  </div>
</section>
<div class="elvalaszto"></div>'''
    else:
        proj_szekcio = ""
    html = _csere_blokk(html, "<!-- PROJEKTEK START -->", "<!-- PROJEKTEK END -->", proj_szekcio)

    # ── SZAKMA-MODUL (opcionális, szakma-specifikus kiemelések) ──
    kiemelesek = _lista(adatok, "szakma_kiemelesek")
    if kiemelesek:
        mc = MODUL_CIMEK[_szakma_kulcs(adatok)]
        kartyak = ""
        for k in kiemelesek:
            cim = (k.get("cim", "") if isinstance(k, dict) else str(k))
            leiras = (k.get("leiras", "") if isinstance(k, dict) else "")
            if not cim:
                continue
            kartyak += f'''
    <div class="projekt-kartya">
      <h3 class="projekt-cim">{cim}</h3>
      <p class="projekt-leiras">{leiras}</p>
    </div>'''
        if kartyak:
            modul_szekcio = f'''
<section id="szakma-modul">
  <div class="szekc-eyebrow">{mc["eyebrow"]}</div>
  <h2 class="szekc-cim">{mc["cim"]}</h2>
  <div class="projektek-grid">{kartyak}
  </div>
</section>
<div class="elvalaszto"></div>'''
        else:
            modul_szekcio = ""
    else:
        modul_szekcio = ""
    html = _csere_blokk(html, "<!-- SZAKMA_MODUL START -->", "<!-- SZAKMA_MODUL END -->", modul_szekcio)

    # ── NYELVEK (csak ha több mint 1) ──
    nyelvek = _lista(adatok,"nyelvek")
    if len(nyelvek) > 1:
        nyelv_kartyak = ""
        for ny in nyelvek:
            nyelv_kartyak += f'''
    <div class="nyelv-kartya">
      <div class="nyelv-zaszlo">{ny.get("zaszlo","")}</div>
      <div>
        <div class="nyelv-nev">{ny.get("nev","")}</div>
        <div class="nyelv-szint">{ny.get("szint","")}</div>
      </div>
    </div>'''
        nyelv_szekcio = f'''
<section id="nyelvek">
  <div class="szekc-eyebrow">Kommunikáció</div>
  <h2 class="szekc-cim">Nyelvek</h2>
  <div class="nyelv-grid">{nyelv_kartyak}
  </div>
</section>
<div class="elvalaszto"></div>'''
    else:
        nyelv_szekcio = ""
    html = _csere_blokk(html, "<!-- NYELVEK START -->", "<!-- NYELVEK END -->", nyelv_szekcio)

    # ── PRÓBÁLJ KI (opcionális, a felhasználó saját kihívása) ──
    probald = (extra_info.get("probald_ki", "") or "").strip()
    if probald:
        # A < és > jeleket biztonságosra cseréljük, hogy ne törje a HTML-t
        probald_biztos = probald.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # CTA gombok: email (ha van) + GitHub (ha van)
        email = adatok.get("email", "") or ""
        github = (extra_info.get("github", "") or "").strip()
        gombok = ""
        if email:
            gombok += f'<a href="mailto:{email}?subject=Pr%C3%B3b%C3%A1lj%20ki%20%E2%80%94%20feladat" class="btn-primary" style="padding:14px 32px;">&#9993;&#65039; Írj egy feladatot!</a>'
        if github:
            gombok += f'<a href="{github}" target="_blank" class="btn-sec" style="padding:14px 32px;">&#128230; Nézd meg a munkáim</a>'
        gombok_blokk = f'<div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:24px; position:relative; z-index:1;">{gombok}</div>' if gombok else ""
        probald_szekcio = f'''
<section id="probald">
  <div class="szekc-eyebrow">Mielőtt döntesz</div>
  <h2 class="szekc-cim">Próbálj ki!</h2>
  <div class="probald-box">
    <div class="probald-szoveg">{probald_biztos}</div>
    {gombok_blokk}
  </div>
</section>
<div class="elvalaszto"></div>'''
    else:
        probald_szekcio = ""
    html = _csere_blokk(html, "<!-- PROBALD_KI START -->", "<!-- PROBALD_KI END -->", probald_szekcio)

    # ── LETÖLTHETŐ DOKUMENTUMOK (opcionális: CV / motivációs levél base64-ben) ──
    # extra_info["dokumentumok"] = [{"nev": "Önéletrajz", "fajlnev": "...pdf", "b64": "..."}]
    dokumentumok = _lista(extra_info, "dokumentumok")
    if dokumentumok:
        dok_kartyak = ""
        for d in dokumentumok:
            b64 = d.get("b64", "")
            if not b64:
                continue
            nev = d.get("nev", "Dokumentum")
            fajlnev = d.get("fajlnev", "dokumentum.pdf")
            dok_kartyak += f'''
    <a class="dok-kartya" href="data:application/pdf;base64,{b64}" download="{fajlnev}">
      <div class="dok-ikon"><i class="fa-regular fa-file-pdf"></i></div>
      <div>
        <div class="dok-nev">{nev}</div>
        <div class="dok-meta">PDF · LETÖLTÉS</div>
      </div>
    </a>'''
        if dok_kartyak:
            dok_szekcio = f'''
<section id="dokumentumok">
  <div class="szekc-eyebrow">Dokumentumok</div>
  <h2 class="szekc-cim">Töltsd le</h2>
  <div class="dok-grid">{dok_kartyak}
  </div>
</section>
<div class="elvalaszto"></div>'''
        else:
            dok_szekcio = ""
    else:
        dok_szekcio = ""
    html = _csere_blokk(html, "<!-- DOKUMENTUMOK START -->", "<!-- DOKUMENTUMOK END -->", dok_szekcio)

    # ── KERESETT POZÍCIÓK ──
    poz_html = ""
    poziciok = _lista(adatok,"poziciok_keresett")
    for i, poz in enumerate(poziciok):
        utolso = (i == len(poziciok) - 1)
        ikon = "fa-bullseye" if utolso else "fa-arrow-right"
        nev_style = ' style="color:var(--accent2);"' if utolso else ""
        poz_html += f'''
        <div class="pozicio-item">
          <i class="fa-solid {ikon}" style="color:var(--accent); font-size:13px; flex-shrink:0;"></i>
          <div>
            <div class="pozicio-nev"{nev_style}>{poz.get("nev","")}</div>
            <div class="pozicio-tech">{poz.get("tech","")}</div>
          </div>
        </div>'''
    html = _csere_blokk(html, "<!-- POZICIOK START -->", "<!-- POZICIOK END -->", poz_html)

    # ── OPCIONÁLIS KONTAKT-SOROK (ha nincs adat, töröljük a blokkot) ──
    if not adatok.get("telefon"):
        html = _csere_blokk(html, "<!-- TELEFON START -->", "<!-- TELEFON END -->", "")
    if not extra_info.get("linkedin"):
        html = _csere_blokk(html, "<!-- LINKEDIN START -->", "<!-- LINKEDIN END -->", "")
    if not extra_info.get("github"):
        html = _csere_blokk(html, "<!-- GITHUB START -->", "<!-- GITHUB END -->", "")
    if not extra_info.get("demo_link"):
        html = _csere_blokk(html, "<!-- DEMO START -->", "<!-- DEMO END -->", "")

    return html


def mentes(html: str, nev: str) -> str:
    os.makedirs("outputs", exist_ok=True)
    nev_tiszta = re.sub(r'[^a-zA-Z0-9_-]', '_', nev)
    fajlnev = f"outputs/portfolio_{nev_tiszta}.html"
    with open(fajlnev, "w", encoding="utf-8") as f:
        f.write(html)
    return fajlnev


# ── PORTFÓLIÓ-CHAT (egy, szigorúan behatárolt szerkesztő agens) ──

_PROJEKT_KULCSOK = {"cim", "leiras", "tagek", "ikon", "cimke",
                    "demo_link", "github_link", "egyeb_link", "egyeb_nev", "link"}


def _tiszta_projekt(p: dict, reszleges: bool = False) -> dict:
    """A chat által adott projekt-objektumot a megengedett kulcsokra szűkíti
    (guardrail: ismeretlen kulcsok kiesnek, a tagek string→lista)."""
    out = {}
    for k, v in (p or {}).items():
        if k in _PROJEKT_KULCSOK:
            if k == "tagek" and isinstance(v, str):
                v = [t.strip() for t in v.split(",") if t.strip()]
            out[k] = v
    if not reszleges:
        out.setdefault("cim", out.get("cim", "Új projekt"))
        out.setdefault("tagek", out.get("tagek", []))
    return out


def portfolio_chat(allapot: dict, felhasznalo_uzenet: str) -> dict:
    """Egyetlen, szigorúan behatárolt portfólió-szerkesztő agens.
    EGY strukturált műveletet ad vissza (JSON). SOHA nem ír szabad HTML-t.
    allapot = {"adatok": {...}, "szovegek": {...}, "extra_info": {...}}"""
    szovegek = allapot.get("szovegek", {}) or {}
    extra = allapot.get("extra_info", {}) or {}
    projektek = extra.get("projektek", []) or []
    proj_attekintes = "\n".join(
        [f"[{i}] {p.get('cim','')} — {(p.get('leiras','') or '')[:60]}" for i, p in enumerate(projektek)]
    ) or "(nincs projekt)"

    rendszer = (
        "Te egy portfólió-szerkesztő asszisztens vagy a „Karrier-Ügynökség” alkalmazásban. "
        "KIZÁRÓLAG a felhasználó portfóliójának TARTALMÁN és MEGFOGALMAZÁSÁN dolgozol. "
        "Ha a felhasználó bármi mással próbálkozik (általános kérdés, időjárás, recept, kód, "
        "vagy bármi, ami nem a portfólióról szól), udvariasan tereld vissza, és a \"muvelet\" "
        "legyen \"nincs_valtozas\". SOHA ne írj HTML-t vagy programkódot. Csak a megadott "
        "JSON-műveletek EGYIKÉT adhatod vissza. Magyar, profi, gördülékeny szövegeket írsz."
    )

    prompt = f"""A portfólió jelenlegi, SZERKESZTHETŐ tartalma:

- bemutatkozas: {szovegek.get('bemutatkozas','')}
- cel_szoveg: {szovegek.get('cel_szoveg','')}
- kontakt_szoveg: {szovegek.get('kontakt_szoveg','')}
- eredmenyek: {extra.get('eredmenyek','')}
- probald_ki: {extra.get('probald_ki','')}
- projektek:
{proj_attekintes}

A FELHASZNÁLÓ KÉRÉSE: {felhasznalo_uzenet}

Add vissza KIZÁRÓLAG egy JSON objektumot, semmi mást:

{{
  "muvelet": "szoveg_modositas | szekcio_beallitas | projekt_hozzaadas | projekt_modositas | projekt_torles | nincs_valtozas",
  "cel": "bemutatkozas | cel_szoveg | kontakt_szoveg | probald_ki | eredmenyek | projekt",
  "index": 0,
  "ertek": "az új szöveg, VAGY projekt-műveletnél objektum: {{\\"cim\\":\\"\\",\\"leiras\\":\\"\\",\\"tagek\\":[],\\"demo_link\\":\\"\\",\\"github_link\\":\\"\\"}}",
  "uzenet": "Rövid, barátságos magyar válasz: mit módosítottál (1-2 mondat)."
}}

Szabályok:
- szoveg_modositas: a cel egyike: bemutatkozas, cel_szoveg, kontakt_szoveg. Az ertek a TELJES új szöveg (kész, profi).
- szekcio_beallitas: a cel egyike: probald_ki, eredmenyek. Az ertek a teljes új szöveg; ÜRES string ("") = a szekció eltüntetése.
- projekt_hozzaadas: ertek egy projekt-objektum.
- projekt_modositas: index = melyik projekt (0-tól), ertek a frissített mezőkkel.
- projekt_torles: index = melyik projektet töröljük.
- nincs_valtozas: ha a kérés NEM a portfólióról szól; az uzenet udvariasan tereljen vissza.
- A szövegeket MINDIG kész, magyaros, profi formában add (ne instrukciót)."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=1200,
            system=rendszer,
            messages=[{"role": "user", "content": prompt}]
        )
        t = resp.content[0].text.strip()
        if "```json" in t:
            t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t:
            t = t.split("```")[1].split("```")[0].strip()
        return json.loads(t)
    except Exception:
        return {"muvelet": "nincs_valtozas",
                "uzenet": "Bocsánat, ezt nem sikerült értelmeznem — próbáld más megfogalmazással."}


def chat_muvelet_alkalmazasa(allapot: dict, muvelet: dict) -> dict:
    """A chat műveletét BIZTONSÁGOSAN alkalmazza az állapotra (whitelist).
    Ismeretlen művelet/cél/index esetén nem történik semmi."""
    szovegek = allapot.setdefault("szovegek", {})
    extra = allapot.setdefault("extra_info", {})
    m = (muvelet or {}).get("muvelet", "")
    cel = (muvelet or {}).get("cel", "")
    ertek = (muvelet or {}).get("ertek", "")
    idx = (muvelet or {}).get("index")

    if m == "szoveg_modositas" and cel in {"bemutatkozas", "cel_szoveg", "kontakt_szoveg"} and isinstance(ertek, str):
        szovegek[cel] = ertek
    elif m == "szekcio_beallitas" and cel in {"probald_ki", "eredmenyek"} and isinstance(ertek, str):
        extra[cel] = ertek
    elif m == "projekt_hozzaadas" and isinstance(ertek, dict):
        extra.setdefault("projektek", []).append(_tiszta_projekt(ertek))
    elif m == "projekt_modositas" and isinstance(idx, int) and isinstance(ertek, dict):
        prj = extra.setdefault("projektek", [])
        if 0 <= idx < len(prj):
            prj[idx].update(_tiszta_projekt(ertek, reszleges=True))
    elif m == "projekt_torles" and isinstance(idx, int):
        prj = extra.setdefault("projektek", [])
        if 0 <= idx < len(prj):
            prj.pop(idx)
    # nincs_valtozas / ismeretlen: szándékosan nem módosítunk semmit
    return allapot


def run(cv_szoveg: str, extra_info: dict, foto_base64: str = None) -> dict:
    adatok = adatok_kinyerese(cv_szoveg)
    if not adatok:
        return {"hiba": "Nem sikerült az adatokat kinyerni a CV-ből."}
    szovegek = szovegek_generalasa(adatok, extra_info)
    html = html_generalas(adatok, szovegek, extra_info, foto_base64)
    fajlnev = mentes(html, adatok.get("nev", "portfolio"))
    return {"adatok": adatok, "szovegek": szovegek,
            "html_utvonal": fajlnev, "html_tartalom": html}