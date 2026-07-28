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
from collections import Counter, defaultdict
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


def _elotag(szo: str) -> str:
    """A szóból az az eleje, aminek egyeznie kell.

    Nem fix hat betű: a magyar összetett szavak hosszúak, és egy rögzített
    rövid előtag túl sokat fog meg. A „vezetőasszisztens" hat betűs előtagja
    „vezeto", ami benne van a „targoncavezető"-ben is -- emiatt egy
    targoncás hirdetés vezetőasszisztensnek minősült.

    A szó végéből csak a toldaléknyi rész marad le (három betű), a többi
    egyezzen. Így a „targoncavezeto" -> „targoncavez" nem téveszthető össze
    a „vezetoasszisztens" -> „vezetoasszisz" alakkal, viszont a
    „fejleszto"/„fejlesztők" pár még mindig összeér.
    """
    return szo[:max(ELOTAG, len(szo) - 3)]


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
            ki.append((_elotag(sz), False))
        else:
            # Az egybetűs darabokat sem szabad eldobni. Az "M&A specialist"
            # normalizálva "m a specialist" -- ha csak a "specialist" maradna,
            # a címke MINDEN specialistát magához vonzana, és a
            # "B2B Sales Specialist" M&A elemzőnek minősülne.
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

    A súly a TÉNYLEGESEN ILLESZTETT részekből számol, nem a teljes szavakból:
    ha csak az előtag egyezik, akkor csak az számítson. Különben egy hosszú
    összetett szó akkor is nyerne, ha csak a rövid eleje illeszkedett.
    """
    return sum(len(e) for e, _onallo in _feltetelek(cimke))


class Besorolo:
    """Egyszer felépül, utána minden címre gyorsan válaszol."""

    def __init__(self, foglalkozasok: list[dict], szakmak: list[dict],
                 parok: list[dict]):
        # foglalkozas_uri -> szakma_id.
        #
        # Egy foglalkozáshoz több szakma is tartozhat: a "raktáros"
        # ESCO-foglalkozás a "raktáros" ÉS a "Raktári kisegítő" szakmához is
        # hozzá van kötve. Ilyenkor nem szabad a véletlenre bízni, melyik
        # nyer -- a hirdetés különben rossz szakmához kerülne.
        #
        # A szabály: az a szakma nyer, aminek a NEVE megegyezik a foglalkozás
        # nevével; ha egyik sem ilyen, akkor a legrégebbi (legkisebb azonosító),
        # hogy a besorolás futásról futásra ugyanaz maradjon.
        foglalkozas_nev = {f["uri"]: normalizal(f.get("nev") or "")
                           for f in foglalkozasok}
        szakma_nevek = {s["id"]: normalizal(s["nev"]) for s in szakmak}
        jeloltek: dict[str, list[int]] = defaultdict(list)
        for p in parok:
            jeloltek[p["foglalkozas_uri"]].append(p["szakma_id"])

        self.uri_szakma: dict[str, int] = {}
        for uri, idk in jeloltek.items():
            cel = foglalkozas_nev.get(uri, "")
            self.uri_szakma[uri] = min(
                idk, key=lambda i: (szakma_nevek.get(i, "") != cel, i))
        self.szakma_nev: dict[int, str] = {s["id"]: s["nev"] for s in szakmak}
        # A foglalkozás MAGYAR neve, URI szerint. A találat jöhet angol
        # címkéről is ("carpenter"), de a szakma neve akkor is a magyar
        # legyen ("ács") -- különben angol nevű szakmák keletkeznének az
        # adatbázisban. A `cimke` mező őrzi meg, mi illeszkedett valójában.
        self.magyar_nev: dict[str, str] = {
            f["uri"]: f["nev"] for f in foglalkozasok if f.get("nev")
        }

        # (előtaglista, súly, uri, isco, megjelenített név)
        self.cimkek: list[tuple[list[str], int, str | None, str | None, str]] = []

        # A hivatalos (preferált) nevek erősebbek az alternatíváknál. A
        # "carpenter" az "ács" ANGOL HIVATALOS neve, ugyanakkor a
        # "díszletépítő" egyik alternatívája is -- azonos súlynál a hivatalos
        # nyerjen, különben a találgatás dönt.
        PREFERALT_TOBBLET = 1
        for f in foglalkozasok:
            hivatalos = [f["nev"]] + ([f["nev_en"]] if f.get("nev_en") else [])
            for nev in hivatalos:
                elo = _feltetelek(nev)
                if elo:
                    self.cimkek.append(
                        (elo, _suly(nev) + PREFERALT_TOBBLET,
                         f["uri"], f.get("isco_kod"), nev))
            for nev in list(f.get("alt_nevek") or []):
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
        self._index_epit()

    def _index_epit(self) -> None:
        """Fordított index: melyik feltétel-darab melyik címkékben szerepel.

        Enélkül minden hirdetéscímhez végig kellene próbálni mind a ~48 ezer
        címkét (magyar + angol), ami egy teljes söprésnél százmilliós
        nagyságrendű összehasonlítás.

        Minden címkét a LEGRITKÁBB feltétele alá jegyzünk be. Így egy címke
        egyszer szerepel az indexben, és a jelöltlista kicsi marad: a
        „targoncavezető" cím a „targon" kulcson át pár tucat címkét hoz elő,
        nem negyvennyolcezret.
        """
        gyakorisag: Counter = Counter()
        for elo, _s, _u, _i, _n in self.cimkek:
            for e, _onallo in elo:
                gyakorisag[e] += 1

        self.index: dict[str, list[int]] = defaultdict(list)
        for i, (elo, _s, _u, _i2, _n) in enumerate(self.cimkek):
            if not elo:
                continue
            ritka = min(elo, key=lambda p: gyakorisag[p[0]])
            self.index[ritka[0]].append(i)

    def besorol(self, cim: str) -> Talalat | None:
        """A címre illeszkedő LEGERŐSEBB címke nyer.

        A legerősebb a legspecifikusabb: a "targoncavezető raktáros" címre
        a "targoncavezető" pontosabb válasz, mint a "raktáros".
        """
        norm = normalizal(cim)
        if not norm:
            return None
        szavak = set(norm.split())

        # Csak azok a címkék jöhetnek szóba, amiknek a ritka feltétele
        # egyáltalán előfordul a címben.
        #
        # A feltétel BÁRHOL illeszkedhet, nem csak szó elején: a „vezeto"
        # benne van a „targoncavezeto"-ben. Ezért a cím minden szavából
        # minden 4-6 hosszú részletet megnézünk -- ez pontosan az a
        # halmaz, amiből a `_feltetelek` előtagjai származhatnak.
        jeloltek: set[int] = set()
        for sz in szavak:
            if len(sz) >= 2:
                jeloltek.update(self.index.get(sz, ()))
            # A feltétel a címke szavának előtagja, tetszőleges hosszú, és
            # a címben bárhol állhat -- ezért a cím minden elég hosszú
            # részletét megnézzük. Szótári keresés, tehát olcsó.
            for hossz in range(MIN_SZO, len(sz) + 1):
                for k in range(0, len(sz) - hossz + 1):
                    jeloltek.update(self.index.get(sz[k:k + hossz], ()))

        legjobb = None
        legjobb_suly = 0
        for i in jeloltek:
            elo, suly, uri, isco, nev = self.cimkek[i]
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
            self.szakma_nev.get(szakma_id) if szakma_id
            else self.magyar_nev.get(uri, nev),
            uri, isco, kategoria, nev,
        )
