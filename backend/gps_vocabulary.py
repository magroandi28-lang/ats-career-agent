"""A Career GPS napló zárt szókincse, egyetlen forrásból.

A `career_gps_events.esemeny_tipus` és a `career_gps_snapshots.terulet` /
`allapot` oszlopokon adatbázis-szintű CHECK van (lásd
supabase/migrations/20260724072136_flow_career_gps_foundation.sql és
20260724150000_career_workflow_state.sql). Ha a kód a listán kívüli értéket
ír, a beszúrás elhasal -- és mivel a GPS-írás szándékosan hibatűrő, ez
csendben, csak egy naplósorral történik meg.

Ez a modul ezért Python-oldalon is kimondja ugyanazt a szókincset, hogy az
eltérés a hívás helyén, hangosan derüljön ki, ne az adatbázisban, némán.
"""

from typing import Final


class GpsSzokincsHiba(ValueError):
    """A napló zárt listáján kívüli érték."""


ESEMENY_TIPUSOK: Final[frozenset[str]] = frozenset({
    "profile_draft_created",
    "profile_fact_confirmed",
    "career_goal_selected",
    "career_intent_confirmed",
    "market_snapshot_ready",
    "job_shortlist_created",
    "application_package_approved",
    "transition_path_selected",
    "training_selected",
    "foreign_shortlist_created",
    "portfolio_preview_ready",
    "portfolio_published",
})

# Területenként külön szókincs: a tábla CHECK-je egyetlen közös listát enged,
# de az értékek területenként mást jelentenek, és a keveredés félrevezető
# GPS-panelt eredményezne.
TERULET_ALLAPOTOK: Final[dict[str, frozenset[str]]] = {
    "profil": frozenset({"nincs", "vazlat", "ellenorzendo", "megerositett"}),
    "karriercel": frozenset({"nincs", "nyitott", "kivalasztott", "validalt"}),
    "piaci_kep": frozenset({"nincs", "betoltve", "elavult"}),
    "felkeszultseg": frozenset({"nincs", "hianyok", "terv", "folyamatban", "megfelelo"}),
    "palyazas": frozenset({
        "nincs", "nincs_shortlist", "shortlist", "anyag_kesz", "beadas_kovetese",
    }),
    "portfolio": frozenset({"nincs", "tartalom_keszul", "elonezet", "publikalt"}),
    "specialis_ut": frozenset({"nincs", "aktiv", "inaktiv"}),
}


def ellenorzott_esemeny(esemeny_tipus: str) -> str:
    if esemeny_tipus not in ESEMENY_TIPUSOK:
        raise GpsSzokincsHiba(
            f"Ismeretlen GPS-eseménytípus: {esemeny_tipus!r}"
        )
    return esemeny_tipus


def ellenorzott_snapshot(terulet: str, allapot: str) -> tuple[str, str]:
    engedett = TERULET_ALLAPOTOK.get(terulet)
    if engedett is None:
        raise GpsSzokincsHiba(f"Ismeretlen GPS-terület: {terulet!r}")
    if allapot not in engedett:
        raise GpsSzokincsHiba(
            f"A(z) {terulet!r} területen nem értelmezett állapot: {allapot!r}"
        )
    return terulet, allapot
