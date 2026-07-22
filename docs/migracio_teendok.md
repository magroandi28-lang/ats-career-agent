# MIGRÁCIÓS TEENDŐK — Streamlit → React/Next.js + FastAPI

Ez a fájl gyűjti azokat a dolgokat, amikre csak AKKOR kerül sor, amikor a
Streamlit app-ot (`app.py`) lecseréljük a React/Next.js frontendre és a
FastAPI backend lesz az egyetlen belépési pont. Addig ezek szándékosan
ÉRINTETLENÜL maradnak a kódban — a cél, hogy a mai Streamlit app egy
pillanatra se törjön el a fejlesztés közben.

## 1. Régi, AI-alapú `allasok_rangsorolasa()` törlése
- Hely: `agents/karrier_ugynok.py`
- Miért maradt eddig: a Streamlit `run()` függvénye ezt hívja közvetlenül.
- Mit vált ki: `allasok_rangsorolasa_determinisztikus()` (2026-07-22-én épült,
  halmaz-egyezés, AI-hívás nélkül, bizonyítottan determinisztikus).
- Teendő a migrációkor: ha a Streamlit `run()` már nem fut (mindenki a FastAPI
  `/allasok` végponton megy át), a régi `allasok_rangsorolasa()` függvény
  törölhető — semmi más nem fogja hívni.

## 2. Régi, AI-alapú `ats_diagnozis()` törlése
- Hely: `agents/karrier_ugynok.py`
- Miért maradt eddig: az `app.py` (Streamlit) közvetlenül hívja (kb. 915. sor,
  ATS-fül) ÉS a `run()` is hívja a régi Karrier Ügynök folyamatban.
- Mit vált ki: `ats_diagnozis_determinisztikus()` (2026-07-22-én épült). A
  `v_szakma_keszsegek` nézetből (valós, tárolt gyakoriság-adatok) dolgozik —
  a hiányzó kulcsszavak darabszáma és a % innentől KÓD számolja, nem AI-becslés.
  AI csak egy szűk, zárt feladatra marad: eldönteni, hogy egy FIX, 20 elemű
  listáról melyik készség van meg a CV-ben (pongyola megfogalmazás miatt kell).
  Ez jelentősen csökkenti, de technikailag nem zárja ki 100%-ban a
  változékonyságot (az AI-osztályozás maga továbbra sem tökéletesen
  reprodukálható) — ellentétben az állás-rangsorolással, ami már 0% AI.
- Teendő a migrációkor: ha sem az `app.py`, sem a `run()` nem hívja többé
  közvetlenül a régit, törölhető.

## Általános szabály további hasonló esetekre
Amikor egy régi, Streamlit-nek dolgozó függvényt egy új, FastAPI-nak dolgozó
verzió vált ki: NEM töröljük a régit azonnal. Ide felírjuk, hogy mikor
törölhető (= amikor a Streamlit-ág megszűnik), és csak a frontend-váltás
UTOLSÓ lépéseként takarítunk.
