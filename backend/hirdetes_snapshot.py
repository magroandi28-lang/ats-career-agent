"""Hiteles, változatlan álláshirdetés-snapshotok előállítása.

A gyűjtők által kapott forráselemet és az elemzésre kijelölt eredeti
szövegmezőt változtatás nélkül őrizzük meg. A normalizált ``hirdetesek``
tábla ettől külön, származtatott listázási réteg.

A minőségkapu determinisztikus és fail-closed:

* snippet listázható, de elemzésre soha nem alkalmas;
* ATS- és karrierút-számításba csak validált, teljes szöveg kerülhet;
* a hibás rekord is megmarad, de karantén állapotban.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import json
import os
import re
import uuid
from typing import Any, Final


SZABALYVERZIO: Final = "hirdetes-snapshot-v2"
ERVENYES_FORRASOK: Final = frozenset(
    {"portal", "ceges", "jooble", "eures", "egyeb"}
)
ERVENYES_MINOSEGEK: Final = frozenset(
    {"teljes", "reszleges", "snippet", "ismeretlen"}
)


def sha256_szoveg(szoveg: str) -> str:
    """Egy UTF-8 szöveg kisbetűs SHA-256 lenyomata."""

    return hashlib.sha256(szoveg.encode("utf-8")).hexdigest()


def kanonikus_json(payload: Any) -> str:
    """Stabil JSON-alak a forráselem tartalmi lenyomatához.

    A tárolt ``raw_payload`` az eredeti Python/JSON objektum marad. Csak a
    hash számításához használunk rendezett, whitespace-mentes alakot, hogy a
    kulcssorrend ne hozzon létre hamis új verziót.
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def gyujtesi_futas_azonosito(forras: str) -> str:
    """Egy futáson belül újrahasználható audit-azonosító."""

    github_run = (os.getenv("GITHUB_RUN_ID") or "").strip()
    if github_run:
        kiserlet = (os.getenv("GITHUB_RUN_ATTEMPT") or "1").strip()
        return f"github:{github_run}:{kiserlet}:{forras}"
    return f"local:{forras}:{uuid.uuid4()}"


def gyujto_verzio(forras: str) -> str:
    """A gyűjtő és – Actionsben – a futó commit azonosítója."""

    commit = (os.getenv("GITHUB_SHA") or "dev").strip()
    return f"{forras}-v2:{commit[:12]}"


def nyelv_megallapitasa(szoveg: str, jelzes: str | None = None) -> str:
    """Forrásjelzésből, majd óvatos magyar nyelvi heurisztikából dolgozik."""

    jelolt = (jelzes or "").strip().lower().replace("_", "-")
    if 2 <= len(jelolt) <= 32:
        return jelolt

    kisbetus = f" {(szoveg or '').lower()} "
    magyar_jelek = ("á", "é", "í", "ó", "ö", "ő", "ú", "ü", "ű")
    magyar_szavak = (
        " és ",
        " vagy ",
        " munkavégzés ",
        " feladat",
        " elvár",
        " jelentkez",
    )
    if any(jel in kisbetus for jel in magyar_jelek) or any(
        szo in kisbetus for szo in magyar_szavak
    ):
        return "hu"
    return "ismeretlen"


def elemzesi_szoveg(raw_szoveg: str) -> str:
    """A teljes nyers szöveg determinisztikus, származtatott tisztítása."""

    return _elemzesi_szoveg_poziciokkal(raw_szoveg)[0]


def _elemzesi_szoveg_poziciokkal(
    raw_szoveg: str,
) -> tuple[str, list[int], list[int]]:
    """Tisztított szöveg és karakterenkénti nyers forráspozíciók.

    A pozíciótérkép teszi lehetővé, hogy egy kinyert tételhez ne csak a
    snapshotot, hanem a nyers forrásból vett pontos, változatlan részletet
    és annak fél-nyílt ``[kezdet, vég)`` tartományát is eltároljuk.
    """

    nyers = raw_szoveg if isinstance(raw_szoveg, str) else ""
    karakterek: list[tuple[str, int, int]] = []
    index = 0
    while index < len(nyers):
        if nyers[index] == "<":
            tag_vege = nyers.find(">", index + 1)
            if tag_vege >= 0:
                karakterek.append((" ", index, tag_vege + 1))
                index = tag_vege + 1
                continue
        if nyers[index] == "&":
            entitas_vege = nyers.find(";", index + 1, index + 16)
            if entitas_vege >= 0:
                entitas = nyers[index : entitas_vege + 1]
                feloldott = html.unescape(entitas)
                if feloldott != entitas:
                    karakterek.extend(
                        (karakter, index, entitas_vege + 1)
                        for karakter in feloldott
                    )
                    index = entitas_vege + 1
                    continue
        karakterek.append((nyers[index], index, index + 1))
        index += 1

    eredmeny: list[str] = []
    kezdetek: list[int] = []
    vegek: list[int] = []
    whitespace_kezdet: int | None = None
    whitespace_veg: int | None = None
    for karakter, nyers_kezdet, nyers_veg in karakterek:
        if karakter.isspace():
            if whitespace_kezdet is None:
                whitespace_kezdet = nyers_kezdet
            whitespace_veg = nyers_veg
            continue
        if eredmeny and whitespace_kezdet is not None:
            eredmeny.append(" ")
            kezdetek.append(whitespace_kezdet)
            vegek.append(whitespace_veg or whitespace_kezdet)
        whitespace_kezdet = None
        whitespace_veg = None
        eredmeny.append(karakter)
        kezdetek.append(nyers_kezdet)
        vegek.append(nyers_veg)
    return "".join(eredmeny), kezdetek, vegek


def forrasbizonyitek_keresese(
    raw_szoveg: str,
    kinyert_szoveg: str,
) -> dict | None:
    """Pontos, nyers forrásrészlet egy kinyert szöveghez.

    Ha a kinyert szöveg nem vezethető vissza egyértelműen a snapshot
    szövegére, ``None`` tér vissza. Ilyen tételt a V2 feldolgozó nem ment.
    """

    keresett = " ".join((kinyert_szoveg or "").split())
    if not keresett:
        return None
    tisztitott, kezdetek, vegek = _elemzesi_szoveg_poziciokkal(raw_szoveg)
    pozicio = tisztitott.find(keresett)
    if pozicio < 0:
        pozicio = tisztitott.lower().find(keresett.lower())
    if pozicio < 0:
        return None
    utolso = pozicio + len(keresett) - 1
    if utolso >= len(vegek):
        return None
    nyers_kezdet = kezdetek[pozicio]
    nyers_veg = vegek[utolso]
    return {
        "forras_bizonyitek": raw_szoveg[nyers_kezdet:nyers_veg],
        "forras_bizonyitek_kezdete": nyers_kezdet,
        "forras_bizonyitek_vege": nyers_veg,
    }


def _eures_teljes_validacios_hibak(
    *,
    raw_payload: Any,
    raw_szoveg: str,
    forras_azonosito: str,
    forras_szoveg_mezo: str,
) -> list[str]:
    """Az EURES ``teljes`` minősítés forrásséma- és egyezéskapuja."""

    if not isinstance(raw_payload, dict):
        return ["eures_forrassema_ervenytelen"]

    azonosito = raw_payload.get("id")
    cim = raw_payload.get("title")
    leiras = raw_payload.get("description")
    kotelezo_helyes = (
        isinstance(azonosito, (str, int))
        and bool(str(azonosito).strip())
        and isinstance(cim, str)
        and bool(cim.strip())
        and isinstance(leiras, str)
        and bool(leiras.strip())
    )
    opcionalis_tipusok = (
        ("employer", dict),
        ("locationMap", dict),
        ("availableLanguages", list),
        ("positionScheduleCodes", list),
    )
    opcionalis_helyes = all(
        kulcs not in raw_payload or isinstance(raw_payload[kulcs], tipus)
        for kulcs, tipus in opcionalis_tipusok
    )

    hibak: list[str] = []
    if not kotelezo_helyes or not opcionalis_helyes:
        hibak.append("eures_forrassema_ervenytelen")
    if forras_szoveg_mezo != "description":
        hibak.append("eures_szovegmezo_nem_description")
    if isinstance(leiras, str) and raw_szoveg != leiras:
        hibak.append("eures_raw_szoveg_nem_egyezik")
    if azonosito is not None and forras_azonosito != str(azonosito):
        hibak.append("eures_forras_azonosito_nem_egyezik")
    return hibak


def forras_specifikus_validacios_hibak(snapshot: dict) -> list[str]:
    """A tárolt snapshot forrásspecifikus kapujának újraellenőrzése."""

    if (
        snapshot.get("forras_tipus") == "eures"
        and snapshot.get("szoveg_minoseg") == "teljes"
    ):
        return _eures_teljes_validacios_hibak(
            raw_payload=snapshot.get("raw_payload"),
            raw_szoveg=snapshot.get("raw_szoveg", ""),
            forras_azonosito=snapshot.get("forras_azonosito", ""),
            forras_szoveg_mezo=snapshot.get("forras_szoveg_mezo", ""),
        )
    return []


def snapshot_keszitese(
    *,
    forras_tipus: str,
    forras_azonosito: str,
    forras_url: str | None,
    keresesi_kulcsszo: str | None,
    forras_szoveg_mezo: str,
    raw_payload: Any,
    raw_szoveg: str,
    szoveg_minoseg: str,
    cim: str,
    nyelv: str | None,
    gyujto: str,
    gyujtesi_futas: str,
    begyujtve: datetime.datetime | None = None,
) -> dict:
    """Snapshot-sor és determinisztikus minőségkapu előállítása.

    A ``raw_payload`` és ``raw_szoveg`` értékét nem tisztítjuk, nem vágjuk
    és nem egészítjük ki. Az ellenőrzés külön változókon fut.
    """

    hibak: list[str] = []
    figyelmeztetesek: list[str] = []

    forras = (forras_tipus or "").strip().lower()
    azonosito = (forras_azonosito or "").strip()
    szoveg_mezo = (forras_szoveg_mezo or "").strip()
    minoseg = (szoveg_minoseg or "").strip().lower()
    eredeti_szoveg = raw_szoveg if isinstance(raw_szoveg, str) else ""

    if forras not in ERVENYES_FORRASOK:
        hibak.append("ervenytelen_forras")
        forras = "egyeb"
    if not azonosito:
        hibak.append("hianyzo_forras_azonosito")
        azonosito = "ismeretlen"
    if not szoveg_mezo:
        hibak.append("hianyzo_forras_szoveg_mezo")
        szoveg_mezo = "ismeretlen"
    if not isinstance(raw_payload, dict):
        hibak.append("raw_payload_nem_objektum")
    if not (cim or "").strip():
        hibak.append("hianyzo_cim")
    if not eredeti_szoveg.strip():
        hibak.append("hianyzo_raw_szoveg")
    if minoseg not in ERVENYES_MINOSEGEK:
        hibak.append("ervenytelen_szoveg_minoseg")
        minoseg = "ismeretlen"
    if forras == "eures" and minoseg == "teljes":
        hibak.extend(
            _eures_teljes_validacios_hibak(
                raw_payload=raw_payload,
                raw_szoveg=eredeti_szoveg,
                forras_azonosito=azonosito,
                forras_szoveg_mezo=szoveg_mezo,
            )
        )
    if not (forras_url or "").strip():
        figyelmeztetesek.append("hianyzo_forras_url")
    if minoseg == "snippet":
        figyelmeztetesek.append("snippet_nem_hasznalhato_elemzesre")
    elif minoseg != "teljes":
        figyelmeztetesek.append("nem_teljes_szoveg")

    try:
        payload_hash_alap = kanonikus_json(raw_payload)
        tarolhato_payload = raw_payload
    except (TypeError, ValueError):
        hibak.append("raw_payload_nem_json")
        payload_hash_alap = "null"
        tarolhato_payload = None

    allapot = "karanten" if hibak else "elfogadott"
    listazhato = allapot == "elfogadott"
    elemezheto = listazhato and minoseg == "teljes"
    idopont = begyujtve or datetime.datetime.now(datetime.timezone.utc)
    if idopont.tzinfo is None:
        idopont = idopont.replace(tzinfo=datetime.timezone.utc)

    return {
        "forras_tipus": forras,
        "forras_azonosito": azonosito,
        "forras_url": forras_url,
        "keresesi_kulcsszo": keresesi_kulcsszo,
        "forras_szoveg_mezo": szoveg_mezo,
        "raw_payload": tarolhato_payload,
        "raw_szoveg": eredeti_szoveg,
        "raw_payload_sha256": sha256_szoveg(payload_hash_alap),
        "raw_szoveg_sha256": sha256_szoveg(eredeti_szoveg),
        "nyelv": nyelv_megallapitasa(eredeti_szoveg, nyelv),
        "szoveg_minoseg": minoseg,
        "validacios_allapot": allapot,
        "listazasra_alkalmas": listazhato,
        "elemzesre_alkalmas": elemezheto,
        "validacios_hibak": hibak,
        "figyelmeztetesek": figyelmeztetesek,
        "gyujto_verzio": (gyujto or "ismeretlen").strip() or "ismeretlen",
        "gyujtesi_futas": (
            (gyujtesi_futas or "ismeretlen").strip() or "ismeretlen"
        ),
        "szabalyverzio": SZABALYVERZIO,
        "begyujtve": idopont.isoformat(),
    }
