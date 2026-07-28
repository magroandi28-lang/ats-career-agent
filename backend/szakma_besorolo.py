# -*- coding: utf-8 -*-
"""Hirdetéscím -> szakma, az ESCO-nevek alapján.

MIÉRT KELL: eddig a szakma a KERESÉS paramétere volt -- 96 kulcsszóra
kérdeztünk rá, tehát csak azt találtuk meg, amire rákérdeztünk. Így a piaci
körkép sosem lehet teljes.

Megfordítva: begyűjtünk mindent, és a szakmát UTÓLAG állapítjuk meg a
hirdetés címéből. Az ESCO 3 039 magyar foglalkozásneve és azok alternatív
nevei adják a szótárat. A szakmák száma ezzel nem döntés többé, hanem
eredmény.

Nulla modellhívás: névillesztés, mindig ugyanaz az eredmény.
"""

import re
import unicodedata
from typing import Final, NamedTuple


MIN_SZO: Final = 4

# A magyar toldalékok miatt nem lehet teljes szóegyezést kérni: a címben
# "targoncavezetőt keresünk" áll, az ESCO-ban "targonca vezetője". A hat
# betűs előtag mindkettőben ugyanaz ("targon", "vezeto"), és elég hosszú
# ahhoz, hogy ne fogjon meg akármit.
ELOTAG: Final = 6

# ISCO főcsoport -> kategória. A most felfedezett szakmák így kapnak
# besorolást emberi döntés nélkül.
ISCO_KATEGORIA: Final = {
    "1": "Vezető",
    "2": "Felsőfokú képzettséget igénylő",
    "3": "Középfokú képzettséget igénylő",
    "4": "Irodai és ügyviteli",
    "5": "Kereskedelem és szolgáltatás",
    "6": "Mezőgazdaság",
    "7": "Ipar és építőipar",
    "8": "Gépkezelő, összeszerelő, járművezető",
    "9": "Szakképzettséget nem igénylő",
}


class Talalat(NamedTuple):
    szakma_id: int | None
    szakma_nev: str
    esco_uri: str | None
    isco_kod: str | None
    kategoria: str
    # A címke, ami illeszkedett -- ezzel a besorolás megmagyarázható és
    # ellenőrizhető, nem fekete doboz.
    cimke: str


def normalizal(szoveg: str) -> str:
    """Kisbetűsítés és írásjel-eltávolítás -- de az ÉKEZETEK MARADNAK.

    Az ékezetek levágása után az "operátor" (gépkezelő) és az "operatőr"
    (kameraman) betűre azonos lesz, és a gyári operátorokat kamerásnak
    sorolná be a rendszer. Ugyanez fenyeget a "kerület"/"kerékpár",
    "író"/"iró" párokkal. A magyar álláshirdetések ékezetesen íródnak,
    tehát az ékezet több információ, mint zaj.
    """
    t = unicodedata.normalize("NFC", (szoveg or "").lower())
    return re.sub(r"[^0-9a-záéíóöőúüű ]", " ", t)


def _szavak(cimke: str) -> list[str]:
    return [sz for sz in normalizal(cimke).split() if len(sz) >= MIN_SZO]


def _feltetelek(cimke: str) -> list[tuple[str, bool]]:
    """Amit a címnek tartalmaznia kell, hogy erre a címkére illeszkedjen.

    A rövid tagokat (AOI, DTP, ÉRC, LC-MS) NEM szabad eldobni: éppen azok
    különböztetik meg a címkét. Ha az "AOI-operátor"-ból csak az "operátor"
    maradna, minden operátoros hirdetést magához vonzana.

    A hosszú szavaknál előtagra illesztünk (magyar toldalékok miatt), a
    rövideknél viszont önálló szót követelünk -- egy háromvetűs darab
    véletlenül bárhol előfordulhatna egy szó belsejében.
    """
    ki: list[tuple[str, bool]] = []
    for sz in normalizal(cimke).split():
        if len(sz) >= MIN_SZO:
            ki.append((sz[:ELOTAG], False))
        elif len(sz) >= 2:
            ki.append((sz, True))
    return ki


def _suly(cimke: str) -> int:
    """A címke ereje: a jelentést hordozó szavainak együttes hossza.

    NEM a teljes név hossza. Az "AOI-operátor" névből az "AOI" kiesik
    (három betű), tehát csak az "operátor" marad -- ha a teljes névhosszal
    rangsorolnánk, ez a címke MINDEN "operátor" szót tartalmazó hirdetést
    magához vonzana, pusztán mert hosszabb a neve. Így viszont az
    "AOI-operátor" és a puszta "operátor" azonos súlyú, a "gyári operátor"
    pedig erősebb mindkettőnél -- ahogy kell.
    """
    return sum(len(sz) for sz in _szavak(cimke))


class Besorolo:
    """Egyszer felépül, utána minden címre gyorsan válaszol."""

    def __init__(self, foglalkozasok: list[dict], szakmak: list[dict],
                 parok: list[dict]):
        # foglalkozas_uri -> szakma_id (ha már van hozzárendelt szakma)
        self.uri_szakma: dict[str, int] = {
            p["foglalkozas_uri"]: p["szakma_id"] for p in parok
        }
        self.szakma_nev: dict[int, str] = {s["id"]: s["nev"] for s in szakmak}

        # (előtaglista, súly, uri, isco, megjelenített név)
        self.cimkek: list[tuple[list[str], int, str | None, str | None, str]] = []

        for f in foglalkozasok:
            nevek = [f["nev"]] + list(f.get("alt_nevek") or [])
            for nev in nevek:
                elo = _feltetelek(nev)
                if elo:
                    self.cimkek.append(
                        (elo, _suly(nev), f["uri"], f.get("isco_kod"), nev))

        # A saját szakmaneveink is címkék. Ezek a kézzel gondozott nevek,
        # ezért azonos súlynál ezek nyernek -- a +1 ezt fejezi ki.
        for s in szakmak:
            elo = _feltetelek(s["nev"])
            if elo:
                self.cimkek.append(
                    (elo, _suly(s["nev"]) + 1, None, None, s["nev"]))
        self.sajat: dict[str, int] = {s["nev"]: s["id"] for s in szakmak}

    def besorol(self, cim: str) -> Talalat | None:
        """A címre illeszkedő LEGERŐSEBB címke nyer.

        A legerősebb a legspecifikusabb: a "targoncavezető raktáros" címre
        a "targoncavezető" pontosabb válasz, mint a "raktáros".
        """
        norm = normalizal(cim)
        if not norm:
            return None
        szavak = set(norm.split())

        legjobb = None
        legjobb_suly = 0
        for elo, suly, uri, isco, nev in self.cimkek:
            if suly <= legjobb_suly:
                continue
            if all((e in szavak) if onallo else (e in norm) for e, onallo in elo):
                legjobb, legjobb_suly = (elo, suly, uri, isco, nev), suly

        if legjobb is None:
            return None

        _elo, _suly, uri, isco, nev = legjobb
        if uri is None:
            # Saját szakmanévre illeszkedett.
            return Talalat(self.sajat.get(nev), nev, None, None, "", nev)

        szakma_id = self.uri_szakma.get(uri)
        kategoria = ISCO_KATEGORIA.get((isco or "")[:1], "Egyéb")
        return Talalat(
            szakma_id,
            self.szakma_nev.get(szakma_id) if szakma_id else nev,
            uri, isco, kategoria, nev,
        )
