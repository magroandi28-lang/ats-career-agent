# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import pdfplumber
import os
import re
import base64
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Karrier-Ügynökség",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="collapsed",  # a Kísérő alapból csukva — nem nyomja össze az oldalt
)

st.markdown("""
<style>
.stApp { background-color: #0a0e1a !important; }
.block-container { padding: 1.2rem 3rem; max-width: 1500px; margin: 0 auto; }
.stMarkdown, .stMarkdown p, .stMarkdown li { color: #e2e8f4 !important; }
label, .stRadio label, .stCheckbox label, .stSelectbox label,
.stTextInput label, .stTextArea label, .stFileUploader label {
    color: #e2e8f4 !important; font-size: 14px !important;
}
.stTextInput > div > div > input {
    background: #1e2d45 !important; color: #ffffff !important;
    border: 1px solid #2e5080 !important; border-radius: 6px !important;
}
.stTextArea > div > div > textarea {
    background: #1e2d45 !important; color: #ffffff !important;
    border: 1px solid #2e5080 !important; border-radius: 6px !important;
}
.stSelectbox > div > div {
    background: #1e2d45 !important; color: #ffffff !important;
    border: 1px solid #2e5080 !important;
}
[data-baseweb="select"] > div {
    background: #1e2d45 !important; color: #ffffff !important;
    border: 1px solid #2e5080 !important;
}
[data-baseweb="popover"] ul { background: #111827 !important; }
[data-baseweb="popover"] li { background: #111827 !important; color: #e2e8f4 !important; }
[data-baseweb="popover"] li:hover { background: #1e3a5f !important; color: #D4A843 !important; }
[data-testid="stFileUploader"] {
    background: #1e2d45 !important; border: 1px solid #2e5080 !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploader"] section { background: #1e2d45 !important; border: none !important; }
[data-testid="stFileUploader"] button {
    background: #D4A843 !important; color: #000 !important;
    border: none !important; font-weight: 700 !important;
}
[data-testid="stFileUploadDropzone"] {
    background: #1e2d45 !important; border: 1px dashed #2e5080 !important;
}
[data-testid="stFileUploadDropzone"] * { color: #e2e8f4 !important; }
.stExpander {
    border: 1px solid #1e3a5f !important; border-radius: 8px !important;
    background: #111827 !important;
}
.stExpander summary { color: #e2e8f4 !important; font-weight: 600 !important; }
.stButton > button {
    background: linear-gradient(135deg, #D4A843, #F0C060) !important;
    color: #000 !important; border: none !important;
    border-radius: 8px !important; font-weight: 700 !important;
    padding: 10px 28px !important;
}
.stButton > button:disabled { background: #1e3a5f !important; color: #94a3b8 !important; }
.stTabs [data-baseweb="tab"] { color: #94a3b8 !important; font-size: 14px !important; }
.stTabs [aria-selected="true"] { color: #D4A843 !important; border-bottom: 2px solid #D4A843 !important; }
.chat-uzenet-felhasznalo {
    background: #1e2d45; border-radius: 12px 12px 4px 12px;
    padding: 10px 14px; margin: 6px 0; max-width: 80%;
    margin-left: auto; color: #e2e8f4; font-size: 13px;
}
.chat-uzenet-ugynok {
    background: #111827; border: 1px solid rgba(212,168,67,0.2);
    border-radius: 12px 12px 12px 4px;
    padding: 10px 14px; margin: 6px 0; max-width: 80%;
    color: #e2e8f4; font-size: 13px;
}
footer { display: none !important; }
header { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ── SEGÉD: ELÉRHETŐSÉG KINYERÉSE A CV-BŐL ─────────────────────
def elerhetoseg_kinyeres(cv_szoveg: str) -> dict:
    """Név, email, telefon és város kinyerése a CV szövegéből a PDF fejléchez."""
    nev = "Allaskereso"
    email = ""
    telefon = ""
    varos = ""

    if not cv_szoveg:
        return {"nev": nev, "email": email, "telefon": telefon, "varos": varos}

    em = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', cv_szoveg)
    if em:
        email = em.group(0).strip()

    tel = re.search(
        r'(?:\+?36|06)[\s\-/]?\d{1,2}[\s\-/]?\d{3}[\s\-/]?\d{3,4}',
        cv_szoveg
    )
    if tel:
        telefon = tel.group(0).strip()

    # Város: "Lakcím:" / "Lakhely:" / "Cím:" / "Város:" után az első településnév
    var = re.search(
        r'(?:Lakc[ií]m|Lakhely|C[ií]m|Város)\s*:?\s*([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+)',
        cv_szoveg
    )
    if var:
        varos = var.group(1).strip()

    for sor in cv_szoveg.strip().split('\n')[:6]:
        s = sor.strip().replace('#', '').replace('*', '').strip()
        if (s and 3 < len(s) < 50 and ' ' in s
                and '@' not in s
                and not any(c.isdigit() for c in s)):
            nev = s
            break

    return {"nev": nev, "email": email, "telefon": telefon, "varos": varos}


# ── SEGÉD: A "NINCS CV-M" ŰRLAPBÓL NYERS CV-SZÖVEG ────────────
def osszeallit_cv_urlapbol() -> str:
    """A 'Nincs CV-m' űrlap mezőiből összeállít egy nyers CV-szöveget,
    amit a rendszer ugyanúgy használ, mint egy feltöltött CV-t."""
    nev = st.session_state.get("u_nev", "").strip()
    tel = st.session_state.get("u_tel", "").strip()
    email = st.session_state.get("u_email", "").strip()
    varos = st.session_state.get("u_varos", "").strip()
    tap = st.session_state.get("u_tap", "").strip()
    vegz = st.session_state.get("u_vegz", "").strip()

    sorok = []
    if nev:
        sorok.append(nev)
    if tel:
        sorok.append(f"Telefon: {tel}")
    if email:
        sorok.append(f"Email: {email}")
    if varos:
        sorok.append(f"Lakcím: {varos}")
    if tap:
        sorok.append("\nMUNKATAPASZTALAT:\n" + tap)
    if vegz:
        sorok.append("\nVÉGZETTSÉG:\n" + vegz)
    return "\n".join(sorok)


# ── SEGÉD: ATS-PONT VIZUÁLIS KIJELZŐ (before / after) ─────────
def ats_gauge_html(before: int, after: int = None) -> str:
    """Látványos ATS-illeszkedés kijelző. Ha 'after' is van, before → after formában."""
    def _tomorit(h):
        # A soreleji behúzásokat kiszedjük, különben a Markdown KÓDKÉNT
        # jelenítené meg a HTML-t (4+ szóközzel kezdődő sor = kódblokk!)
        return re.sub(r"\n\s*", " ", h).strip()

    def _szin(p):
        if p >= 75:
            return "#4ade80"   # zöld
        if p >= 50:
            return "#D4A843"   # arany
        return "#ef4444"       # piros

    def _kor(p, felirat, nagy=True):
        szin = _szin(p)
        meret = 132 if nagy else 110
        sug = 56 if nagy else 46
        kerulet = 2 * 3.14159 * sug
        kit = kerulet * (1 - p / 100)
        return f"""
        <div style="text-align:center;">
          <svg width="{meret}" height="{meret}" viewBox="0 0 {meret} {meret}">
            <circle cx="{meret/2}" cy="{meret/2}" r="{sug}" fill="none" stroke="#1e3a5f" stroke-width="10"/>
            <circle cx="{meret/2}" cy="{meret/2}" r="{sug}" fill="none" stroke="{szin}" stroke-width="10"
                    stroke-linecap="round" stroke-dasharray="{kerulet:.1f}" stroke-dashoffset="{kit:.1f}"
                    transform="rotate(-90 {meret/2} {meret/2})"/>
            <text x="50%" y="50%" text-anchor="middle" dy="0.35em"
                  font-size="{28 if nagy else 24}" font-weight="800" fill="{szin}"
                  font-family="Arial">{p}%</text>
          </svg>
          <div style="color:#94a3b8; font-size:12px; letter-spacing:1px; margin-top:4px;">{felirat}</div>
        </div>"""

    if after is None:
        return _tomorit(f"""<div style="display:flex; justify-content:center; padding:12px 0;">{_kor(before, "ATS-ILLESZKEDÉS")}</div>""")

    nyil = '<div style="font-size:34px; color:#D4A843; align-self:center; padding:0 8px;">&#10142;</div>'
    return _tomorit(f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:8px;
                background:#0d1117; border:1px solid rgba(212,168,67,0.25); border-radius:12px; padding:18px; margin:12px 0;">
      {_kor(before, "EREDETI CV", nagy=False)}
      {nyil}
      {_kor(after, "ROBOTBARÁT CV", nagy=False)}
    </div>""")


# ── SEGÉD: LOGÓ BETÖLTÉSE (logo.png / logo.jpg a projektmappából) ──
def logo_base64():
    mappa = os.path.dirname(os.path.abspath(__file__))
    for ln, lm in [("logo.png", "png"), ("logo.jpg", "jpeg"), ("logo.jpeg", "jpeg")]:
        ut = os.path.join(mappa, ln)
        if os.path.exists(ut):
            with open(ut, "rb") as f:
                return lm, base64.b64encode(f.read()).decode()
    return None, None


# ── GDPR ──────────────────────────────────────────────────────
if "gdpr_elfogadva" not in st.session_state:
    st.session_state.gdpr_elfogadva = False

if not st.session_state.gdpr_elfogadva:
    # Ha van logo.png / logo.jpg a projektmappában, azt mutatjuk — különben a régi fejléc
    _mappa = os.path.dirname(os.path.abspath(__file__))
    _logo_ut, _logo_mime = None, "png"
    for _ln, _lm in [("logo.png", "png"), ("logo.jpg", "jpeg"), ("logo.jpeg", "jpeg")]:
        if os.path.exists(os.path.join(_mappa, _ln)):
            _logo_ut, _logo_mime = os.path.join(_mappa, _ln), _lm
            break
    if _logo_ut:
        with open(_logo_ut, "rb") as _lf:
            _logo64 = base64.b64encode(_lf.read()).decode()
        _fejlec = ('<img src="data:image/' + _logo_mime + ';base64,' + _logo64 + '" '
                   'style="width:400px; max-width:92%; margin-top:-14px;" alt="Karrier-Ügynökség"/>'
                   '<div style="color:#94a3b8; font-size:13px; letter-spacing:5px; '
                   'margin:14px 0 34px;">&mdash;&nbsp; AI-ASSZISZTÁLT KARRIERFEJLESZTÉS '
                   '&nbsp;&mdash;</div>')
    else:
        _fejlec = """<div style="font-size:48px; margin-bottom:6px;">🕵️</div>
        <h1 style="font-size:36px; font-weight:800; color:#D4A843; margin-bottom:12px;">
            Karrier-Ügynökség
        </h1>"""

    st.markdown(f"""
    <div style="max-width:1050px; margin:12px auto; text-align:center;">
        {_fejlec}
        <div style="font-family:'Georgia',serif; font-size:27px; margin-bottom:10px;">
            <span style="color:#D4A843; font-weight:700;">Más CV-k elvesznek a robotszűrőn.</span>
            <em style="color:#e2e8f4;"> A tiéd nem fog.</em>
        </div>
        <p style="color:#94a3b8; font-size:16px; margin-bottom:18px;">
            ✓ ATS-ellenőrzés &nbsp;·&nbsp; ✓ állásra szabott CV és motivációs levél
            &nbsp;·&nbsp; ✓ több ezer valódi hirdetés adataiból
        </p>
        <div style="background:#111827; border:1px solid rgba(212,168,67,0.3);
                    border-radius:12px; padding:20px 26px; text-align:left;">
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:8px;">
                🔒 Adatkezelési nyilatkozat
            </div>
            <p style="color:#94a3b8; font-size:14px; line-height:1.7; margin:0;">
                A feltöltött CV-d elemzés céljából az
                <strong style="color:#f1f5f9;">Anthropic Claude API</strong>-ra kerül továbbításra —
                <strong style="color:#f1f5f9;">a CV-d és személyes adataid nem tárolódnak.</strong>
                A szolgáltatás fejlesztéséhez anonim álláspiaci adatokat (nyilvános hirdetések
                szövegét) gyűjtünk és tárolunk; ezek feldolgozásában a
                <strong style="color:#f1f5f9;">Google Gemini API</strong> is részt vesz.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        gdpr = st.checkbox("Elolvastam és elfogadom az adatkezelési nyilatkozatot", key="gdpr_checkbox")
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if gdpr:
            if st.button("🚀 Belépés a Karrier-Ügynökségbe", use_container_width=True):
                st.session_state.gdpr_elfogadva = True
                st.rerun()
        else:
            st.button("🚀 Belépés a Karrier-Ügynökségbe", use_container_width=True, disabled=True)
    st.stop()

# ── FŐ ALKALMAZÁS ─────────────────────────────────────────────
_vcol, _ = st.columns([1.4, 8])
with _vcol:
    if st.button("← Kezdőoldal", key="vissza_kezdo"):
        st.session_state.gdpr_elfogadva = False
        st.rerun()

_flm, _fl64 = logo_base64()
if _fl64:
    _fej_logo = ('<img src="data:image/' + _flm + ';base64,' + _fl64 + '" '
                 'style="height:96px;" alt="Karrier-Ügynökség"/>')
else:
    _fej_logo = """<span style="font-size:40px;">🕵️</span>
        <div style="font-size:26px; font-weight:800; color:#D4A843;">Karrier-Ügynökség</div>"""

st.markdown(f"""
<div style="background:linear-gradient(135deg,#1C2540 0%,#0A1628 100%);
            padding:16px 32px; border-radius:12px; margin-bottom:24px;
            border-bottom:3px solid #D4A843;">
    <div style="display:flex; align-items:center; gap:18px;">
        {_fej_logo}
        <div style="font-size:13px; color:#94a3b8;">
            Claude API · ATS optimalizálás · Személyre szabott dokumentumok
        </div>
        <div style="margin-left:auto;">
            <span style="background:rgba(212,168,67,0.1); border:1px solid rgba(212,168,67,0.3);
                        color:#D4A843; padding:4px 12px; border-radius:20px; font-size:12px;">
                ✅ Adatkezelés elfogadva
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
# ══ 🫶 KÍSÉRŐ — felugró ablakban, az oldal elrendezéséhez nem nyúl ══
from utils.profil import profil_osszefoglalo


@st.dialog("🫶 Flow — munkapszichológiai kísérőd")
def _dlg_kisero():
    st.caption("✨ Személyre szabott támogatás, amikor elakadsz.")
    st.markdown("**Szia! Flow vagyok, munka- és szervezetpszichológiai kísérőd.** "
                "Abban segítek, hogy tisztábban lásd, hol tartasz most, mi hajt "
                "igazán, és merre érdemes továbbmenned — valós piaci tényekre és "
                "munkapszichológiára építve. **Te döntesz. Én kísérlek.**")
    _profil_szoveg = profil_osszefoglalo()
    if _profil_szoveg:
        st.markdown("#### Amit eddig látok rólad")
        st.markdown(_profil_szoveg)
        from utils.profil import profil as _profil_leker
        _p = _profil_leker()
        _hianyzik = []
        if not _p.get("szakma"):
            _hianyzik.append("egy **CV-elemzés** (Karrier Ügynök fül → 🔍 Átvizsgálom)")
        if not _p.get("holland_tipus"):
            _hianyzik.append("az **5 perces tesztem** — a Karrier Tanácsadó fül "
                             "tetején, a „🫶 Ismerd meg magad” blokkban vár")
        if _hianyzik:
            st.info("🧭 A teljes képhez még kérlek pótold: " +
                    " és ".join(_hianyzik) + ". Minél többet látok, annál "
                    "pontosabban tudok segíteni.")
        else:
            st.success("✅ Megvan a teljes kép: a szakmai profilod ÉS a teszted. "
                       "A részletes kiértékelésem hamarosan itt olvashatod.")
    else:
        st.info("Még nem ismerlek — de ha végigjárod velem az utat, a végére "
                "teljes kép áll össze rólad, és teljes körűen tudok segíteni:  \n\n"
                "1️⃣ **Kezdd a Karrier Ügynök fülön:** töltsd fel a CV-d — akár "
                "kézzel írtad egy papírra: fotózd le, és a képet is beolvassuk! "
                "Átvizsgáljuk, vagy rögtön robotbaráttá írjuk.  \n"
                "2️⃣ **Nézz körül a Karrier Tanácsadóban:** mit kér most a piac "
                "a szakmádban, mennyit fizet, merre tart.  \n"
                "3️⃣ **Zárd az 5 perces tesztemmel** (a Tanácsadó fül tetején) — "
                "ekkor áll össze a teljes profilod, és megkapod a személyre "
                "szabott kiértékelésem.  \n\n"
                "Minél többet látok, annál pontosabban tudok segíteni — akár "
                "váltást is mutatok, ha kiderül, hogy másban lennél boldogabb.")
    # ── 💬 CHAT: kérdezz Flow-tól (profil + tudásbázis + app-ismeret) ──
    st.markdown("---")
    st.markdown("##### 💬 Kérdezz tőlem")
    for _u in st.session_state.get("flow_chat", []):
        with st.chat_message("user" if _u["szerep"] == "user" else "assistant",
                             avatar="🙂" if _u["szerep"] == "user" else "🫶"):
            st.markdown(_u["szoveg"])

    def _flow_kerdez(_szoveg: str):
        """Kérdés elküldése Flow-nak (gépelt vagy hangból átírt)."""
        if "app_ismeret" not in st.session_state:
            try:
                _ai_ut = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "docs", "flow_app_ismeret.md")
                with open(_ai_ut, encoding="utf-8") as _f:
                    st.session_state.app_ismeret = _f.read()
            except Exception:
                st.session_state.app_ismeret = ""
        _elozmeny = st.session_state.setdefault("flow_chat", [])
        with st.spinner("Flow gondolkodik…"):
            from utils.flow_agy import flow_valasz
            from utils.profil import profil as _prof_chat
            _valasz = flow_valasz(_szoveg, _prof_chat(),
                                  st.session_state.app_ismeret, _elozmeny)
        _elozmeny.append({"szerep": "user", "szoveg": _szoveg})
        _elozmeny.append({"szerep": "flow", "szoveg": _valasz or
                          "Most nem érlek el rendesen (talán elfogyott a napi "
                          "AI-keret) — próbáld meg kicsit később újra."})
        st.rerun(scope="fragment")

    with st.form("flow_chat_form", clear_on_submit=True):
        _kerdes = st.text_area("Kérdésed", label_visibility="collapsed",
                               height=90,
                               placeholder="Írd ide a kérdésed — pl.: Mi az a "
                                           "karrierhorgony? Hol tudom átíratni "
                                           "a CV-m?")
        _kuld = st.form_submit_button("➤ Küldés", use_container_width=True)
    if _kuld and _kerdes.strip():
        _flow_kerdez(_kerdes.strip())

    # 🎤 Hangalapú kérdezés: felvétel → Gemini-átirat → ugyanaz az út
    _hang = st.audio_input("🎤 Vagy mondd el hangban:", key="flow_hang")
    if _hang is not None:
        _hang_bytes = _hang.getvalue()
        _hang_jel = hash(_hang_bytes)
        if st.session_state.get("flow_hang_utolso") != _hang_jel:
            st.session_state.flow_hang_utolso = _hang_jel
            with st.spinner("🎤 Hallgatlak — átírom a kérdésed…"):
                from utils.flow_agy import hang_atiras
                _atirat = hang_atiras(_hang_bytes)
            if _atirat.strip():
                _flow_kerdez(_atirat.strip())
            else:
                st.warning("Nem sikerült érteni a felvételt — próbáld újra, "
                           "vagy írd be gépelve.")

    st.caption("Tájékozódást segítő eszköz, nem helyettesíti a szakembert.")


# Belépéskor EGYSZER magától előugrik, hogy a felhasználó tudjon Flow-ról
if not st.session_state.get("kisero_bemutatva"):
    st.session_state.kisero_bemutatva = True
    _dlg_kisero()

# ── 🫶 FLOW LEBEGŐ KARIKA — a fülsor jobb végén, az üres sávban ──
st.markdown("""<style>
@keyframes flow-lebeges{
    0%,100%{ transform:translateY(0); }
    50%{ transform:translateY(-5px); }
}
.st-key-kisero_gomb{
    position:static !important; height:0 !important; min-height:0 !important;
    margin:0 !important; padding:0 !important; z-index:100 !important;
    overflow:visible !important;
}
.st-key-kisero_gomb button::after{
    content:"✨ Személyre szabott támogatás, amikor elakadsz.";
    position:absolute; right:calc(100% + 14px); top:50%;
    transform:translateY(-50%);
    background:rgba(10,14,26,0.96); color:#e2e8f4;
    border:1px solid rgba(212,168,67,0.4);
    padding:7px 14px; border-radius:10px; font-size:13px;
    white-space:nowrap; opacity:0; pointer-events:none;
    transition:opacity .25s;
}
.st-key-kisero_gomb button:hover::after{ opacity:1; }
.st-key-kisero_gomb button{
    position:absolute !important; right:4.5rem !important; margin-top:-16px !important;
    width:74px !important; height:74px !important; border-radius:50% !important;
    padding:0 !important;
    background:#111827 !important;
    border:2px solid rgba(212,168,67,0.85) !important;
    box-shadow:0 0 14px rgba(212,168,67,0.35) !important;
    animation:flow-lebeges 3s ease-in-out infinite !important;
}
.st-key-kisero_gomb button:hover{
    box-shadow:0 0 24px rgba(212,168,67,0.65) !important;
}
.st-key-kisero_gomb button p{ margin:0 !important; line-height:1.1 !important; }
.st-key-kisero_gomb button p:first-child{ font-size:18px !important; }
.st-key-kisero_gomb button p:last-child{
    font-size:10px !important; color:#D4A843 !important; font-weight:600 !important;
}
</style>""", unsafe_allow_html=True)
if st.button("🫶\n\nFlow", key="kisero_gomb"):
    _dlg_kisero()

tab_ugynok, tab_tanacsado, tab_korkep, tab_portfolio, tab_kepzes, tab_kulfoldi = st.tabs([
    "🕵️ Karrier Ügynök",
    "🧭 Karrier Tanácsadó",
    "📊 Piaci Körkép",
    "🌟 Portfólió Generátor",
    "📚 Képzések",
    "✈️ Külföldi Lehetőségek"
])

# ══════════════════════════════════════════════════════════════
# TAB: 📊 PIACI KÖRKÉP — élő kereslet-mutató a saját gyűjtésből
# ══════════════════════════════════════════════════════════════
with tab_korkep:
    st.markdown("### 📊 Piaci Körkép — élő kereslet-mutató")
    st.caption("Saját, naponta frissülő álláshirdetés-gyűjtésünkből számolva — "
               "nem évekkel ezelőtti kiadványokból. A KERESLET oldalát mutatjuk: "
               "mennyire keresik az egyes szakmákat MOST.")

    if st.button("🔄 Körkép frissítése", key="korkep_frissit") or \
            "korkep_adat" not in st.session_state:
        with st.spinner("Számoljuk a friss keresletet…"):
            from utils.adatbazis import kereslet_korkep
            st.session_state.korkep_adat = kereslet_korkep()

    _kk = st.session_state.get("korkep_adat", [])
    if not _kk:
        st.info("Még nincs elég adat a körképhez — a napi gyűjtés töltögeti, "
                "nézz vissza pár nap múlva.")
    else:
        # ── HÁROM TOPLISTA ──
        _t1, _t2, _t3 = st.columns(3)
        _novekvok = [e for e in _kk if e["trend"] is not None and e["trend"] >= 25
                     and e["friss_30"] >= 5]
        _csokkenok = [e for e in _kk if e["trend"] is not None and e["trend"] <= -25
                      and (e["friss_30"] + e["elozo_30"]) >= 8]
        with _t1:
            st.markdown("#### 🔥 Most legkeresettebb")
            for e in _kk[:5]:
                st.markdown(f"**{e['szakma']}** — {e['friss_30']} friss hirdetés, "
                            f"{e['cegek_30']} cég")
        with _t2:
            st.markdown("#### 📈 Növekvő kereslet")
            if _novekvok:
                for e in sorted(_novekvok, key=lambda x: -(x["trend"] or 0))[:5]:
                    st.markdown(f"**{e['szakma']}** — +{e['trend']}% egy hónap alatt")
            else:
                st.caption("Ehhez még kevés a trend-adat — pár hét gyűjtés kell.")
        with _t3:
            st.markdown("#### 📉 Csökkenő kereslet")
            if _csokkenok:
                for e in sorted(_csokkenok, key=lambda x: (x["trend"] or 0))[:5]:
                    st.markdown(f"**{e['szakma']}** — {e['trend']}% egy hónap alatt")
            else:
                st.caption("Jelenleg nincs megbízhatóan csökkenő szakma az adatban.")

        # ── TELJES TÁBLÁZAT ──
        st.markdown("---")
        st.markdown("#### Minden követett szakma")
        import pandas as _pd
        _df = _pd.DataFrame([{
            "Szakma": e["szakma"],
            "Kereslet": e["kategoria"],
            "Friss hirdetés (30 nap)": e["friss_30"],
            "Kereső cégek": e["cegek_30"],
            "Trend": (f"{'+' if e['trend'] > 0 else ''}{e['trend']}%"
                      if e["trend"] is not None else "—"),
        } for e in _kk])
        st.dataframe(_df, use_container_width=True, hide_index=True)
        st.caption("⚖️ Tisztesség: a túljelentkezést (hány ember pályázik egy "
                   "helyre) hivatalos friss adat híján nem tudjuk mérni — "
                   "amit itt látsz, az a hirdetői KERESLET, élőben.")

# ══════════════════════════════════════════════════════════════
# TAB 1: KARRIER ÜGYNÖK
# ══════════════════════════════════════════════════════════════
with tab_ugynok:

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if "belepo_mod" not in st.session_state:
        st.session_state.belepo_mod = None

    def _valt_mod(uj_mod):
        st.session_state.belepo_mod = uj_mod
        st.session_state.mutasd_allasok = False
        st.rerun()

    # ── FELUGRÓ ABLAK: CV-átvizsgálás (feltöltés + indítás + élő állapot) ──
    def _cv_beolvas(feltoltott) -> str:
        """CV-szöveg kinyerése: PDF-ből közvetlenül, képből (pl. kézzel írt
        önéletrajz fotója) Gemini-átirattal."""
        if feltoltott is None:
            return ""
        _nev = (feltoltott.name or "").lower()
        if _nev.endswith(".pdf"):
            with pdfplumber.open(feltoltott) as pdf:
                return "".join([p.extract_text() or "" for p in pdf.pages])
        from utils.flow_agy import kep_atiras
        _mime = "image/png" if _nev.endswith(".png") else "image/jpeg"
        return kep_atiras(feltoltott.getvalue(), _mime)

    @st.dialog("🔍 CV-átvizsgálás — robotszűrő (ATS)")
    def _dlg_elemez():
        st.caption("Megnézzük, átmegy-e a robotszűrőn, és mi miatt szűrne ki. "
                   "A CV-det nem írjuk át. Kézzel írt önéletrajz fotóját is "
                   "beolvassuk!")
        _van = bool(st.session_state.get("cv_szoveg_global", "").strip())
        cv_file = None
        if _van:
            st.success("A korábban feltöltött CV-det használjuk.")
            if st.checkbox("Másik CV-t töltök fel", key="dlg_csere_elemez"):
                cv_file = st.file_uploader("CV (PDF vagy fotó)",
                                           type=["pdf", "png", "jpg", "jpeg"],
                                           key="dlg_cv_elemez")
                _van = cv_file is not None
        else:
            cv_file = st.file_uploader("CV (PDF vagy fotó)",
                                       type=["pdf", "png", "jpg", "jpeg"],
                                       key="dlg_cv_elemez")
            _van = cv_file is not None
        if st.button("🔍 Indítás", type="primary", use_container_width=True,
                     disabled=not _van, key="dlg_indit_elemez"):
            with st.status("🔍 Elemzés folyamatban…", expanded=True) as _a:
                if cv_file is not None:
                    if not cv_file.name.lower().endswith(".pdf"):
                        st.write("✍️ Kézírás/kép beolvasása szöveggé…")
                    _szoveg = _cv_beolvas(cv_file)
                    if not _szoveg.strip():
                        _a.update(label="❌ Nem sikerült kiolvasni a CV-t",
                                  state="error")
                        st.error("Nem tudtam szöveget kinyerni a fájlból. "
                                 "Próbáld élesebb fotóval vagy PDF-ben.")
                        st.stop()
                    st.session_state.cv_szoveg_global = _szoveg
                st.write("📄 CV beolvasva.")
                st.write("🔎 Friss hirdetések keresése és összevetés — 1-2 perc, ne zárd be.")
                from agents.karrier_ugynok import run as ugynok_run
                st.session_state.tab1_eredmeny = ugynok_run(
                    cv_szoveg=st.session_state.get("cv_szoveg_global", ""),
                    szakma_megadva="", helyszin="Budapest")
                st.session_state.belepo_mod = "elemez"
                st.session_state.belepo_mod_aktiv = "elemez"
                st.session_state.tan_kovesse_cv = True
                st.session_state.pop("tan_gap_eredmeny", None)
                # ── PROFIL-ÉPÍTÉS: a kísérő innen tudja, kivel beszél ──
                from utils.profil import profil_frissit
                _er = st.session_state.tab1_eredmeny or {}
                _szi_p = _er.get("szakma_info", {}) or {}
                _diag_p = _er.get("diagnozis", {}) or {}
                profil_frissit(
                    szakma=_szi_p.get("szakma"),
                    keszsegek=_diag_p.get("meglevo_kulcsszavak"),
                    ats_illeszkedes=_diag_p.get("illeszkedes_szazalek"),
                )
                _a.update(label="✅ Kész!", state="complete")
            st.session_state.ugorj_eredmenyre = True
            st.rerun()  # az ablak becsukódik, az eredmény az oldalon jelenik meg

    van_cv = bool(st.session_state.get("cv_szoveg_global", "").strip())

    mod = st.session_state.get("belepo_mod")

    # ── HÁROM BELÉPŐ KÁRTYA — MINDIG láthatóak. A kiválasztott arany
    #    kerettel kiemelve, a többi halványítva. Nincs eltűnés, nincs ugrálás,
    #    bármikor át lehet kattintani a másikra. ──
    def _kartya_stilus(sajat):
        if mod == sajat:
            return "border:2px solid #D4A843; box-shadow:0 0 16px rgba(212,168,67,0.35); opacity:1;"
        if mod:
            return "border:1px solid rgba(212,168,67,0.12); opacity:0.45;"
        return "border:1px solid rgba(212,168,67,0.3); opacity:1;"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background:#111827; {_kartya_stilus('elemez')}
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">🔍</div>
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:6px;">Van CV-m — nézd át</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Átmegy a robotszűrőn (ATS)? Megmondjuk, mi a baj. Nem írjuk át.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔍 Átvizsgálom", key="mod_elemez", use_container_width=True):
            _dlg_elemez()  # felugró ablak nyílik
    with c2:
        st.markdown(f"""
        <div style="background:#111827; {_kartya_stilus('atir')}
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">✨</div>
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:6px;">Van CV-m — írd át</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Robotbarát CV + akár 5 állásra szabott CV és motivációs levél.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✨ Átírom és pályázom", key="mod_atir", use_container_width=True):
            _valt_mod("atir")
    with c3:
        st.markdown(f"""
        <div style="background:#111827; {_kartya_stilus('keszit')}
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">✍️</div>
            <div style="color:#e2e8f4; font-weight:700; font-size:15px; margin-bottom:6px;">Nincs CV-m</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Pár adatból robotbarát CV-t készítünk neked.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✍️ Készíttetek egyet", key="mod_keszit", use_container_width=True):
            _valt_mod("keszit")

    if van_cv:
        st.caption("✅ A CV-d betöltve – bármelyik kártyánál ezzel dolgozhatsz tovább, nem kell újra feltölteni.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # K1 — VAN CV-M, NÉZD ÁT (csak elemzés, nem ír át)
    # ════════════════════════════════════════════════════════
    if mod == "elemez":
        # A feltöltés + indítás a felugró ablakban történik (_dlg_elemez),
        # itt már csak az eredmény jelenik meg.
        if st.session_state.get("tab1_eredmeny") and st.session_state.get("belepo_mod_aktiv") == "elemez":
            er = st.session_state.tab1_eredmeny
            if "hiba" in er:
                st.error(f"❌ {er['hiba']}")
            else:
                _diag = er.get("diagnozis", {})
                _szi = er.get("szakma_info", {})
                st.markdown("<div id='elemzes-eredmeny'></div>", unsafe_allow_html=True)
                if st.session_state.pop("ugorj_eredmenyre", False):
                    components.html("""<script>setTimeout(function(){
                        var el = window.parent.document.getElementById('elemzes-eredmeny');
                        if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
                    }, 300);</script>""", height=0)
                st.markdown("---")
                st.markdown(f"### 🔍 Azonosított szakma: `{_szi.get('szakma','')}`")
                if _diag:
                    ill = _diag.get("illeszkedes_szazalek", 0)
                    st.markdown(ats_gauge_html(ill), unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:center; color:#e2e8f4; font-weight:700; margin-bottom:8px;'>Robotszűrő (ATS) illeszkedés: {ill}%</div>", unsafe_allow_html=True)
                    _hi = _diag.get("hianyzo_kulcsszavak", [])
                    if _hi:
                        h_html = "".join([f"<div style='color:#94a3b8;font-size:13px;padding:4px 0;'>\u2022 Hiányzik: <strong style='color:#e2e8f4;'>{h.get('szo','')}</strong> \u2014 {h.get('hirdetesek_szama',0)} hirdetésből</div>" for h in _hi[:5]])
                        st.markdown(f"""<div style="background:#1a0a0a;border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:16px;margin:12px 0;"><div style="color:#ef4444;font-weight:700;margin-bottom:8px;">\u274c Ezért sz\u0171rne ki a robot:</div>{h_html}</div>""", unsafe_allow_html=True)
                    _me = _diag.get("meglevo_kulcsszavak", [])
                    if _me:
                        m_html = "".join([f"<div style='color:#94a3b8;font-size:13px;padding:4px 0;'>\u2713 <strong style='color:#4ade80;'>{k}</strong></div>" for k in _me[:5]])
                        st.markdown(f"""<div style="background:#0a1a0a;border:1px solid rgba(74,222,128,0.3);border-radius:8px;padding:16px;margin:12px 0;"><div style="color:#4ade80;font-weight:700;margin-bottom:8px;">\u2705 Ezek m\u00e1r szerepelnek a CV-dben:</div>{m_html}</div>""", unsafe_allow_html=True)
                components.html("""
<div style="font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1500,#0a0e1a);border:1px solid rgba(212,168,67,0.5);border-radius:12px;padding:24px;text-align:center;">
<div style="color:#D4A843;font-weight:800;font-size:17px;margin-bottom:6px;">Szeretnéd, hogy átjusson a szűrőn?</div>
<div style="color:#e2e8f4;font-size:14px;">Válaszd fent a <a style="color:#D4A843;font-weight:700;text-decoration:underline;cursor:pointer;" onclick="gomb('Átírom és pályázom')">„✨ Van CV-m — írd át”</a> kártyát – elkészítjük a robotbarát CV-det, és akár 5 állásra szabott jelentkezést is. A CV-det már nem kell újra feltöltened.</div>
<div style="color:#e2e8f4;font-size:14px;margin-top:12px;border-top:1px solid rgba(212,168,67,0.25);padding-top:12px;">🧭 <strong>Vagy előbb tanács kellene?</strong> A felső <a style="color:#D4A843;font-weight:700;text-decoration:underline;cursor:pointer;" onclick="ful('Tanácsadó')">„🧭 Karrier Tanácsadó”</a> fülön megmutatjuk, mit kér most a piac a szakmádban, mennyit fizet, és a CV-d alapján személyre szabott tervet is kapsz — merre érdemes fejlődnöd vagy akár <a style="color:#D4A843;font-weight:700;text-decoration:underline;cursor:pointer;" onclick="ful('Képzések')">átképzened magad</a>.</div>
</div>
<script>
function ful(nev){
  var t = Array.from(window.parent.document.querySelectorAll('button[role=tab]'))
               .find(function(x){return x.innerText.indexOf(nev) !== -1;});
  if (t) { t.click(); window.parent.scrollTo({top:0, behavior:'smooth'}); }
}
function gomb(nev){
  var b = Array.from(window.parent.document.querySelectorAll('button'))
               .find(function(x){return x.innerText.indexOf(nev) !== -1;});
  if (b) { b.click(); window.parent.scrollTo({top:0, behavior:'smooth'}); }
}
</script>""", height=250)
                st.caption("📚 Tipp: a felső „Képzések” fülön piacképes képzéseket ajánlunk, amivel erősebb lehetsz.")

    # ════════════════════════════════════════════════════════
    # K2 — VAN CV-M, ÍRD ÁT  (robotbarát CV + pályázás)
    # ════════════════════════════════════════════════════════
    elif mod == "atir":
        st.markdown("---")
        st.info("✨ Robotbarát (ATS-optimalizált) CV-t készítünk, és megkeressük neked a legjobban illő (max 5) állást – mindegyikre tudunk testreszabott CV-t és motivációs levelet írni.")

        cv_kell = not van_cv or st.session_state.get("csere_atir", False)
        cv_file = None
        if cv_kell:
            cv_file = st.file_uploader("CV feltöltése (PDF vagy fotó — kézzel írt CV-t is beolvasunk)",
                                       type=["pdf", "png", "jpg", "jpeg"],
                                       key="cv_up_atir", label_visibility="collapsed")
        else:
            cc1, cc2 = st.columns([3, 1])
            with cc1:
                st.success("A korábban betöltött CV-det használjuk.")
            with cc2:
                if st.button("🔄 Másikat töltök fel", key="csere_atir_gomb", use_container_width=True):
                    st.session_state.csere_atir = True
                    st.rerun()
        with st.expander("📷 Profilfotó hozzáadása (opcionális)"):
            foto_file = st.file_uploader("Profilfotó", type=["jpg", "jpeg", "png"], key="foto_atir", label_visibility="collapsed")
        if foto_file:
            st.session_state.foto_base64 = base64.b64encode(foto_file.read()).decode("utf-8")

        indit = st.button("✨ Írd át a CV-met és mutasd a rám illő állásokat",
                          type="primary", key="akcio_atir",
                          disabled=(cv_kell and cv_file is None), use_container_width=True)
        if indit:
            if cv_file is not None:
                if not cv_file.name.lower().endswith(".pdf"):
                    st.info("✍️ Kézírás/kép beolvasása szöveggé…")
                _szoveg_a = _cv_beolvas(cv_file)
                if not _szoveg_a.strip():
                    st.error("Nem tudtam szöveget kinyerni a fájlból. "
                             "Próbáld élesebb fotóval vagy PDF-ben.")
                    st.stop()
                st.session_state.cv_szoveg_global = _szoveg_a
                st.session_state.csere_atir = False
            st.session_state.tab1_chat = {}
            st.session_state.tab1_dokumentumok = {}
            st.session_state.tab1_ceginfo = {}
            st.session_state.mutasd_allasok = False
            st.session_state.pop("tab1_general_cv", None)
            with st.spinner("✨ Robotbarát CV és állások keresése..."):
                from agents.karrier_ugynok import run as ugynok_run
                st.session_state.tab1_eredmeny = ugynok_run(
                    cv_szoveg=st.session_state.get("cv_szoveg_global", ""),
                    szakma_megadva="", helyszin="Budapest")
                st.session_state.belepo_mod_aktiv = "atir"
                st.session_state.tan_kovesse_cv = True
                st.session_state.pop("tan_gap_eredmeny", None)

    # ════════════════════════════════════════════════════════
    # K3 — NINCS CV-M  (csak űrlap, nincs feltöltő)
    # ════════════════════════════════════════════════════════
    elif mod == "keszit":
        st.markdown("---")
        st.markdown("#### ✍️ Add meg az adataidat – ebből készítjük el a CV-det")
        st.caption("Nyugodtan a saját szavaiddal írj – a rendszer szakmai nyelvre fordítja.")
        st.text_input("Teljes neved", key="u_nev", placeholder="pl. Németh Éva")
        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            st.text_input("Telefonszám", key="u_tel", placeholder="06 20 555 1234")
        with uc2:
            st.text_input("Email cím", key="u_email", placeholder="nev@email.com")
        with uc3:
            st.text_input("Város", key="u_varos", placeholder="pl. Pécs")
        st.text_area("Munkatapasztalat – hol, mettől meddig, mit csináltál (a saját szavaiddal)",
                     key="u_tap", height=140,
                     placeholder="pl. Penny Market, Pécs, 2015 óta: pénztáros voltam, árut töltöttem fel, vevőkkel foglalkoztam...")
        st.text_input("Végzettség", key="u_vegz", placeholder="pl. Kereskedelmi szakközépiskola, 2010")
        with st.expander("📷 Profilfotó hozzáadása (opcionális)"):
            foto_file = st.file_uploader("Profilfotó", type=["jpg", "jpeg", "png"], key="foto_keszit", label_visibility="collapsed")
        if foto_file:
            st.session_state.foto_base64 = base64.b64encode(foto_file.read()).decode("utf-8")
        _van = bool(st.session_state.get("u_nev") or st.session_state.get("u_tap"))
        if st.button("✍️ Készítsd el a CV-met", type="primary", key="akcio_keszit",
                     disabled=not _van, use_container_width=True):
            st.session_state.cv_szoveg_global = osszeallit_cv_urlapbol()
            st.session_state.pop("tab1_general_cv", None)
            st.session_state.pop("tab1_eredmeny", None)
            with st.spinner("✨ Robotbarát CV készítése..."):
                from agents.karrier_ugynok import szakma_felismeres, cv_atiras
                szi = szakma_felismeres(st.session_state.cv_szoveg_global, "")
                st.session_state.keszit_szakma_info = szi
                st.session_state.tab1_general_cv = cv_atiras(
                    st.session_state.cv_szoveg_global, {}, szi, {}, {}, "")
            st.session_state.keszit_kesz = True
            st.rerun()

        # ── A KÉSZ CV HELYBEN (nem dobjuk át a pályáztató nézetbe) ──
        if st.session_state.get("keszit_kesz") and st.session_state.get("tab1_general_cv"):
            from agents.karrier_ugynok import ekezet_nelkul
            from utils.pdf_sablonok import szinek_listaja, szin_ajanlat, cv_pdf_general
            szi = st.session_state.get("keszit_szakma_info", {})
            st.markdown("---")
            st.success("✅ Elkészült a robotbarát CV-d! Nézd át, töltsd le – és ha szeretnél, pályázz is vele.")
            st.markdown("**🎨 Válassz színt a CV-hez:**")
            szinek = szinek_listaja()
            aj = szin_ajanlat(szi.get("szakma_kategoria", ""))
            aj_idx = next((j for j, s in enumerate(szinek) if s["kulcs"] == aj), 1)
            kvidx = st.radio("Stílus", options=range(len(szinek)),
                             format_func=lambda x: f"{szinek[x]['nev']} – {szinek[x]['leiras']}", index=aj_idx,
                             key="keszit_szin", horizontal=True, label_visibility="collapsed")
            kszin = szinek[kvidx]["kulcs"]
            st.markdown("**📄 A robotbarát CV-d (szerkeszthető):**")
            kszerk = st.text_area("CV", value=st.session_state.tab1_general_cv, height=320,
                                  key="keszit_cv_szerk", label_visibility="collapsed")
            st.session_state.tab1_general_cv = kszerk
            kfej = elerhetoseg_kinyeres(st.session_state.get("cv_szoveg_global", ""))
            kpdf_adatok = {"nev": kfej["nev"], "pozicio": szi.get("szakma", ""),
                           "email": kfej["email"], "telefon": kfej["telefon"], "varos": kfej["varos"],
                           "foto_base64": st.session_state.get("foto_base64", "")}
            kcv_pdf = cv_pdf_general(st.session_state.tab1_general_cv, kpdf_adatok, kszin)
            st.download_button("⬇️ CV letöltése (PDF)", data=kcv_pdf,
                               file_name=f"{ekezet_nelkul(kfej['nev'])}_CV.pdf",
                               mime="application/pdf", key="keszit_cv_letolt", use_container_width=True)
            if st.button("🎯 Szeretnék pályázni is – keressünk állást!", key="keszit_palyazom", use_container_width=True):
                st.session_state.belepo_mod = "atir"
                st.session_state.keszit_kesz = False
                st.rerun()

    # ════════════════════════════════════════════════════════
    # K2 EREDMÉNY: robotbarát CV + álláskeresés (belső füleken)
    # ════════════════════════════════════════════════════════
    if (st.session_state.get("belepo_mod_aktiv") == "atir"
            and st.session_state.get("tab1_eredmeny")
            and st.session_state.belepo_mod == "atir"):
        eredmeny = st.session_state.tab1_eredmeny
        if "hiba" in eredmeny:
            st.error(f"❌ {eredmeny['hiba']}")
        else:
            szakma_info = eredmeny.get("szakma_info", {})
            diagnozis   = eredmeny.get("diagnozis", {})
            csomagok    = eredmeny.get("csomagok", [])
            kepzesek    = eredmeny.get("kepzesek", [])

            st.markdown("---")
            st.markdown(f"### 🎯 `{szakma_info.get('szakma','')}` — {len(csomagok)} hozzád illő állást találtam")
            st.caption("A „🎯 Pályázás állásokra” fülön választhatsz állást. A robotbarát (ATS) CV elkészítése külön, opcionális lépés a „📄 A robotbarát CV-d” fülön.")

            belso = st.tabs(["📄 A robotbarát CV-d", "🎯 Pályázás állásokra"])

            # ── BELSŐ FÜL 1: AZ ÁLTALÁNOS ROBOTBARÁT CV ──────
            with belso[0]:
                st.caption("Itt készítheted el az ATS-optimalizált CV-det – opcionális. Ha jó a meglévő CV-d, ezt kihagyhatod, és mehetsz egyből a „Pályázás állásokra” fülre.")
                from agents.karrier_ugynok import cv_atiras, ekezet_nelkul
                from utils.pdf_sablonok import szinek_listaja, szin_ajanlat, cv_pdf_general

                if "tab1_general_cv" not in st.session_state:
                    if st.button("✨ Készítsd el a robotbarát CV-met", key="gen_cv_gomb", use_container_width=True):
                        with st.spinner("✨ Robotbarát CV készítése..."):
                            cv_alap = st.session_state.get("cv_szoveg_global", "")
                            st.session_state.tab1_general_cv = cv_atiras(cv_alap, {}, szakma_info, diagnozis, {}, "")
                            # ÚJRA-PONTOZÁS: az átírt CV ATS-illeszkedése ("after")
                            try:
                                from agents.karrier_ugynok import ats_diagnozis
                                _uj = ats_diagnozis(st.session_state.tab1_general_cv,
                                                    eredmeny.get("allasok", []), szakma_info)
                                st.session_state.tab1_ats_after = _uj.get("illeszkedes_szazalek")
                            except Exception:
                                st.session_state.tab1_ats_after = None
                        st.rerun()
                    else:
                        st.info("👆 Kattints, ha szeretnél egy robotbarát (ATS-optimalizált) változatot a CV-dből.")

                if "tab1_general_cv" in st.session_state:
                    # BEFORE → AFTER ATS-illeszkedés (ha van mindkét szám)
                    _before = diagnozis.get("illeszkedes_szazalek") if diagnozis else None
                    _after = st.session_state.get("tab1_ats_after")
                    if _before is not None and _after is not None:
                        st.markdown(ats_gauge_html(int(_before), int(_after)), unsafe_allow_html=True)
                        if _after > _before:
                            st.markdown(f"<div style='text-align:center; color:#4ade80; font-weight:700;'>📈 +{int(_after)-int(_before)} százalékpont — sokkal jobb esély a robotszűrőn!</div>", unsafe_allow_html=True)
                    elif _before is not None:
                        st.markdown(ats_gauge_html(int(_before)), unsafe_allow_html=True)
                    st.markdown("**🎨 Válassz színt a CV-hez:**")
                    szinek = szinek_listaja()
                    aj = szin_ajanlat(szakma_info.get("szakma_kategoria", ""))
                    aj_idx = next((j for j, s in enumerate(szinek) if s["kulcs"] == aj), 1)
                    vidx = st.radio("Stílus", options=range(len(szinek)),
                                    format_func=lambda x: f"{szinek[x]['nev']} – {szinek[x]['leiras']}", index=aj_idx,
                                    key="gen_szin", horizontal=True, label_visibility="collapsed")
                    gen_szin = szinek[vidx]["kulcs"]
                    st.markdown("**📄 A robotbarát CV-d (szerkeszthető):**")
                    gen_szerk = st.text_area("CV", value=st.session_state.tab1_general_cv, height=320,
                                             key="gen_cv_szerk", label_visibility="collapsed")
                    st.session_state.tab1_general_cv = gen_szerk
                    cv_alap = st.session_state.get("cv_szoveg_global", "")
                    fej = elerhetoseg_kinyeres(cv_alap)
                    pdf_adatok = {"nev": fej["nev"], "pozicio": szakma_info.get("szakma", ""),
                                  "email": fej["email"], "telefon": fej["telefon"], "varos": fej["varos"],
                                  "foto_base64": st.session_state.get("foto_base64", "")}
                    cv_pdf_b = cv_pdf_general(st.session_state.tab1_general_cv, pdf_adatok, gen_szin)
                    st.download_button("⬇️ CV letöltése (PDF)", data=cv_pdf_b,
                                       file_name=f"{ekezet_nelkul(fej['nev'])}_CV.pdf",
                                       mime="application/pdf", key="gen_cv_letolt", use_container_width=True)

            # ── BELSŐ FÜL 2: ÁLLÁSKERESÉS ────────────────────
            with belso[1]:
                st.markdown("Jelöld be, melyik álláso(k)ra kérsz **testreszabott CV-t és motivációs levelet** – csak azokat készítjük el.")
                email_kereses = st.text_input("📧 Email cím (ide küldjük majd a jelentkezési csomagot)",
                                              key="tab1_email", placeholder="nev@email.com")
                st.session_state.tab1_email_ertek = email_kereses
                # ── PÁLYÁZATI NAPLÓ (mindig látható, az állások fölött) ──
                _naplo = st.session_state.get("palyazat_naplo", [])
                if _naplo:
                    with st.expander(f"📋 A pályázataid: {len(_naplo)} — kattints a megtekintéshez", expanded=False):
                        st.caption("Ezekre az állásokra készítettél jelentkezési anyagot. A linken adhatod be.")
                        for _n in _naplo:
                            st.markdown(
                                f"- **{_n.get('ceg','')}** — {_n.get('cim','')}  ·  "
                                f"🔗 [jelentkezés]({_n.get('link','')})  ·  🕒 {_n.get('datum','')}"
                            )

                st.markdown(f"### 🏢 A {len(csomagok)} legjobban illő állás (illeszkedés szerint sorba rendezve)")

                if "tab1_chat" not in st.session_state:
                    st.session_state.tab1_chat = {}
                if "tab1_dokumentumok" not in st.session_state:
                    st.session_state.tab1_dokumentumok = {}
                if "tab1_ceginfo" not in st.session_state:
                    st.session_state.tab1_ceginfo = {}

                for i, csomag in enumerate(csomagok):
                    ceg = csomag.get("ceg", "")
                    cim = csomag.get("cim", "")
                    link = csomag.get("link", "")
                    ceginfo_key = f"ceginfo_{i}"

                    with st.expander(f"🏢 {i+1}. {ceg} — {cim}", expanded=True):

                        # ── FORRÁS-JELZÉS: honnan jött ez az ajánlat ──
                        _fnev = {"portal": "állásportál", "ceges": "céges karrieroldal",
                                 "jooble": "Jooble"}.get(csomag.get("forras_tipus", ""), "")
                        _fdom = ""
                        if link:
                            _fm = re.search(r"https?://(?:www\.)?([^/]+)", link)
                            _fdom = _fm.group(1) if _fm else ""
                        _freszek = [r for r in [_fdom, _fnev] if r]
                        if csomag.get("adatbazisbol"):
                            _freszek.append("a saját adatbázisunkból ✅")
                        if _freszek:
                            st.caption("📌 Forrás: " + " · ".join(_freszek))

                        if ceginfo_key not in st.session_state.tab1_ceginfo:
                            if st.button("🔎 Mutasd a cégadatokat", key=f"ceginfo_gomb_{i}"):
                                with st.spinner("Cégadatok lekérése..."):
                                    from agents.karrier_ugynok import ceginfo_kereses
                                    st.session_state.tab1_ceginfo[ceginfo_key] = ceginfo_kereses(ceg)
                                st.rerun()

                        ceginfo = st.session_state.tab1_ceginfo.get(ceginfo_key, {})

                        if ceginfo:
                            figyelmeztetes = ceginfo.get('figyelmeztetes')
                            st.markdown(f"""
                            <div style="background:#0d1117; border:1px solid rgba(212,168,67,0.2);
                                        border-radius:8px; padding:16px; margin-bottom:16px;">
                                <div style="color:#e2e8f4; font-size:13px; margin-bottom:6px;">
                                    💰 <strong>Bérsáv:</strong> {ceginfo.get('bersav', 'Nincs megerősített adat')}
                                </div>
                                <div style="color:#e2e8f4; font-size:13px; margin-bottom:6px;">
                                    📊 <strong>Fluktuáció:</strong> {ceginfo.get('fluktuacio', 'Nincs megerősített adat')}
                                </div>
                                <div style="color:#94a3b8; font-size:13px;">
                                    ⭐ {ceginfo.get('velemenyek', '')}
                                </div>
                                {f'<div style="color:#ef4444; font-size:13px; margin-top:8px;">⚠️ {figyelmeztetes}</div>' if figyelmeztetes else ''}
                            </div>
                            """, unsafe_allow_html=True)

                        if link:
                            st.link_button("🔗 Megnézem az állást", url=link)

                        megpalyazom = st.checkbox(
                            "Ezt szeretném megpályázni",
                            key=f"megpalyaz_{i}"
                        )

                        if megpalyazom:

                            st.markdown("---")
                            st.markdown("**💬 Kérdezz a cégről vagy az állásról:**")

                            chat_key = f"chat_{i}"
                            if chat_key not in st.session_state.tab1_chat:
                                st.session_state.tab1_chat[chat_key] = []

                            for uzenet in st.session_state.tab1_chat[chat_key]:
                                if uzenet["szerep"] == "felhasznalo":
                                    st.markdown(
                                        f'<div class="chat-uzenet-felhasznalo">{uzenet["szoveg"]}</div>',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.markdown(
                                        f'<div class="chat-uzenet-ugynok">🕵️ {uzenet["szoveg"]}</div>',
                                        unsafe_allow_html=True
                                    )

                            kerdes = st.chat_input("Kérdezz...", key=f"chat_input_{i}")

                            if kerdes:
                                st.session_state.tab1_chat[chat_key].append({
                                    "szerep": "felhasznalo", "szoveg": kerdes
                                })

                                import anthropic as anth
                                chat_client = anth.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                                cv_kontextus = st.session_state.get("cv_szoveg_global", "")

                                chat_prompt = f"""Te egy tapasztalt karrier tanácsadó vagy.

Cég: {ceg}
Pozíció: {cim}
Céginfó: {ceginfo if ceginfo else "Még nincs lekérve"}
Jelölt CV-je: {cv_kontextus[:1000] if cv_kontextus else "Nincs CV"}

A jelölt kérdése: {kerdes}

Válaszolj röviden, őszintén, személyre szabottan. Maximum 3-4 mondat."""

                                valasz = chat_client.messages.create(
                                    model="claude-haiku-4-5",
                                    max_tokens=300,
                                    messages=[{"role": "user", "content": chat_prompt}]
                                )
                                st.session_state.tab1_chat[chat_key].append({
                                    "szerep": "ugynok",
                                    "szoveg": valasz.content[0].text
                                })
                                st.rerun()

                            st.markdown("---")
                            st.markdown("**🎨 Válassz stílust a dokumentumokhoz:**")

                            from utils.pdf_sablonok import szinek_listaja, szin_ajanlat
                            szinek = szinek_listaja()
                            ajanlott = szin_ajanlat(szakma_info.get("szakma_kategoria", ""))
                            szin_nevek = [s["nev"] + f" ({s['leiras']})" for s in szinek]
                            ajanlott_idx = next((j for j, s in enumerate(szinek) if s["kulcs"] == ajanlott), 1)

                            kivalasztott_idx = st.radio(
                                f"Claude ajánlata: **{szinek[ajanlott_idx]['nev']}**",
                                options=range(len(szinek)),
                                format_func=lambda x: szin_nevek[x],
                                index=ajanlott_idx,
                                key=f"szin_{i}",
                                horizontal=True
                            )
                            kivalasztott_szin = szinek[kivalasztott_idx]["kulcs"]

                            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                            dok_key = f"dok_{i}"

                            kiegeszites = st.text_area(
                                "✍️ Szeretnél valamit kiemelni? (pl. nyelvtudás, műszakvállalás, eredmény) – opcionális",
                                key=f"kieg_{i}",
                                height=80,
                                placeholder="pl. Középfokú angol nyelvtudás, bármilyen műszakot vállalok, 2023-ban hónap dolgozója voltam..."
                            )

                            mit_ker = st.radio(
                                "Mit készítsünk ehhez az álláshoz?",
                                options=["csak_level", "cv_es_level"],
                                format_func=lambda x: "✉️ Csak motivációs levél (a meglévő CV-mmel pályázom)"
                                    if x == "csak_level" else "📄 Állásra szabott CV + ✉️ motivációs levél",
                                key=f"mit_ker_{i}"
                            )

                            if st.button("✉️ Készítsd el!",
                                         key=f"dok_gomb_{i}", use_container_width=True):
                                with st.spinner("Készítés..."):
                                    from agents.karrier_ugynok import motivacios_level
                                    cv_alap = st.session_state.get("cv_szoveg_global", "")
                                    allasok = eredmeny.get("allasok", [])
                                    allas = allasok[i] if i < len(allasok) else csomag

                                    # CV-t CSAK akkor írunk át, ha kérte (különben a meglévővel pályázik)
                                    if mit_ker == "cv_es_level":
                                        from agents.karrier_ugynok import cv_atiras
                                        uj_cv = cv_atiras(cv_alap, allas, szakma_info, diagnozis, ceginfo, kiegeszites)
                                    else:
                                        uj_cv = st.session_state.get("tab1_general_cv", "")  # meglévő robotbarát CV, ha van

                                    uj_level = motivacios_level(cv_alap, allas, szakma_info, ceginfo, kiegeszites)

                                    # ── PROFIL: aktívan pályázik — hova ──
                                    from utils.profil import erdeklodes_jelzes as _ej2
                                    _ej2(f"aktív pályázás: {allas.get('cim', '')} ({ceg})")

                                    st.session_state.tab1_dokumentumok[dok_key] = {
                                        "cv": uj_cv, "level": uj_level,
                                        "szin": kivalasztott_szin,
                                        "ceg": ceg, "cim": cim, "link": link,
                                        "csak_level": (mit_ker == "csak_level"),
                                        "jovahagyva": False
                                    }
                                    # Napló: amire dokumentumot készíttetett
                                    naplo = st.session_state.setdefault("palyazat_naplo", [])
                                    import datetime as _dt
                                    if not any(n.get("link") == link and n.get("ceg") == ceg for n in naplo):
                                        naplo.append({"ceg": ceg, "cim": cim, "link": link,
                                                      "datum": _dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
                                st.rerun()

                            if dok_key in st.session_state.tab1_dokumentumok:
                                dok = st.session_state.tab1_dokumentumok[dok_key]
                                csak_level = dok.get("csak_level", False)

                                if csak_level:
                                    st.markdown("**✉️ Motivációs levél (a meglévő CV-ddel pályázol):**")
                                    uj_level_szerk = st.text_area(
                                        "", value=dok["level"], height=300,
                                        key=f"level_szerk_{i}", label_visibility="collapsed"
                                    )
                                    st.session_state.tab1_dokumentumok[dok_key]["level"] = uj_level_szerk
                                else:
                                    col_cv, col_level = st.columns(2)
                                    with col_cv:
                                        st.markdown("**📄 Állásra szabott CV:**")
                                        uj_cv_szerk = st.text_area(
                                            "", value=dok["cv"], height=300,
                                            key=f"cv_szerk_{i}", label_visibility="collapsed"
                                        )
                                        st.session_state.tab1_dokumentumok[dok_key]["cv"] = uj_cv_szerk
                                    with col_level:
                                        st.markdown("**✉️ Motivációs levél:**")
                                        uj_level_szerk = st.text_area(
                                            "", value=dok["level"], height=300,
                                            key=f"level_szerk_{i}", label_visibility="collapsed"
                                        )
                                        st.session_state.tab1_dokumentumok[dok_key]["level"] = uj_level_szerk

                                from utils.pdf_sablonok import cv_pdf_general, level_pdf_general
                                from agents.karrier_ugynok import ekezet_nelkul

                                cv_glob = st.session_state.get("cv_szoveg_global", "")
                                fej = elerhetoseg_kinyeres(cv_glob)
                                pdf_adatok = {
                                    "nev": fej["nev"],
                                    "pozicio": dok.get("cim", ""),
                                    "email": fej["email"],
                                    "telefon": fej["telefon"],
                                    "varos": fej["varos"],
                                    "foto_base64": st.session_state.get("foto_base64", ""),
                                }
                                szin_pdf = dok.get("szin", "arany")
                                level_pdf_b = level_pdf_general(
                                    st.session_state.tab1_dokumentumok[dok_key]["level"], pdf_adatok, szin_pdf)
                                # CV PDF: szabott esetben az átírt, "csak levél" esetben a meglévő robotbarát CV (ha van)
                                cv_forras = st.session_state.tab1_dokumentumok[dok_key]["cv"]
                                cv_pdf_b = cv_pdf_general(cv_forras, pdf_adatok, szin_pdf) if cv_forras else None
                                nevt = ekezet_nelkul(fej["nev"])
                                cegt = ekezet_nelkul(dok.get("ceg", "Ceg"))

                                st.markdown("**⬇️ Jelentkezési csomag letöltése:**")
                                col_d1, col_d2 = st.columns(2)
                                with col_d1:
                                    if cv_pdf_b:
                                        st.download_button(
                                            "⬇️ CV (PDF)",
                                            data=cv_pdf_b,
                                            file_name=f"{nevt}_CV_{cegt}.pdf",
                                            mime="application/pdf",
                                            key=f"cv_pdf_letolt_{i}",
                                            use_container_width=True
                                        )
                                    else:
                                        st.caption("ℹ️ A CV-det a „📄 A robotbarát CV-d” fülön töltheted le.")
                                with col_d2:
                                    st.download_button(
                                        "⬇️ Motivációs levél (PDF)",
                                        data=level_pdf_b,
                                        file_name=f"{nevt}_MotivaciosLevel_{cegt}.pdf",
                                        mime="application/pdf",
                                        key=f"level_pdf_letolt_{i}",
                                        use_container_width=True
                                    )
                                if link:
                                    st.link_button("🔗 Megnézem az állást és beadom a pályázatom", url=link, use_container_width=True)
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    jovahagyva = st.checkbox(
                                        "✅ Jóváhagyom", key=f"jovahagyva_{i}",
                                        value=dok.get("jovahagyva", False)
                                    )
                                    st.session_state.tab1_dokumentumok[dok_key]["jovahagyva"] = jovahagyva
                                with col_b:
                                    if st.button("🔄 Írja újra!", key=f"ujra_{i}"):
                                        with st.spinner("Újraírás..."):
                                            from agents.karrier_ugynok import motivacios_level
                                            cv_alap = st.session_state.get("cv_szoveg_global", "")
                                            allasok = eredmeny.get("allasok", [])
                                            allas = allasok[i] if i < len(allasok) else csomag
                                            uj_level2 = motivacios_level(cv_alap, allas, szakma_info, ceginfo, st.session_state.get(f"kieg_{i}", ""))
                                            st.session_state.tab1_dokumentumok[dok_key]["level"] = uj_level2
                                            # CV-t csak akkor írjuk újra, ha állásra szabottat kért
                                            if not st.session_state.tab1_dokumentumok[dok_key].get("csak_level", False):
                                                from agents.karrier_ugynok import cv_atiras
                                                uj_cv2 = cv_atiras(cv_alap, allas, szakma_info, diagnozis, ceginfo, st.session_state.get(f"kieg_{i}", ""))
                                                st.session_state.tab1_dokumentumok[dok_key]["cv"] = uj_cv2
                                            st.session_state.tab1_dokumentumok[dok_key]["jovahagyva"] = False
                                        st.rerun()

                st.markdown("---")
                jovahagyott_dok = {
                    k: v for k, v in st.session_state.get("tab1_dokumentumok", {}).items()
                    if v.get("jovahagyva")
                }

                if jovahagyott_dok:
                    st.success(f"✅ {len(jovahagyott_dok)} dokumentum jóváhagyva!")
                    email_cim = st.session_state.get("tab1_email_ertek", "")

                    if email_cim:
                        if st.button(f"📧 Küldd el → {email_cim}", type="primary",
                                     key="email_kuldes", use_container_width=True):
                            with st.spinner("PDF-ek készítése és küldése..."):
                                from utils.pdf_sablonok import cv_pdf_general, level_pdf_general
                                from agents.karrier_ugynok import ekezet_nelkul
                                import sendgrid
                                from sendgrid.helpers.mail import (
                                    Mail, Attachment, FileContent,
                                    FileName, FileType, Disposition
                                )

                                cv_global = st.session_state.get("cv_szoveg_global", "")
                                fej = elerhetoseg_kinyeres(cv_global)
                                nev = fej["nev"]
                                nev_tiszta = ekezet_nelkul(nev)

                                html_reszek = [f"""
                                <h2 style="color:#D4A843;">Karrier Ugynokseg — Allasjelentkezesi csomag</h2>
                                <p>Szia!</p>
                                <p>Elkeszitettuk a szemelyre szabott jelentkezesi csomagodat.</p>
                                <hr/>
                                """]

                                csatolmanyok = []

                                for dok_k, dok_v in jovahagyott_dok.items():
                                    ceg_tiszta = ekezet_nelkul(dok_v.get("ceg", "Ceg"))
                                    cv_fajlnev = f"{nev_tiszta}_CV_{ceg_tiszta}.pdf"
                                    level_fajlnev = f"{nev_tiszta}_MotivaciosLevel_{ceg_tiszta}.pdf"

                                    adatok = {
                                        "nev": nev,
                                        "pozicio": dok_v.get("cim", ""),
                                        "email": fej["email"],
                                        "telefon": fej["telefon"],
                                        "varos": fej["varos"]
                                    }
                                    szin = dok_v.get("szin", "arany")

                                    cv_pdf = cv_pdf_general(dok_v["cv"], adatok, szin)
                                    level_pdf = level_pdf_general(dok_v["level"], adatok, szin)

                                    csatolmanyok.append((cv_fajlnev, cv_pdf, "application/pdf"))
                                    csatolmanyok.append((level_fajlnev, level_pdf, "application/pdf"))

                                    html_reszek.append(f"""
                                    <div style="border:1px solid #D4A843; border-radius:8px;
                                                padding:16px; margin:12px 0;">
                                        <h3 style="color:#D4A843; margin:0 0 8px;">
                                            {dok_v.get('ceg','')} — {dok_v.get('cim','')}
                                        </h3>
                                        <p>📄 <strong>{cv_fajlnev}</strong> (csatolva)</p>
                                        <p>✉️ <strong>{level_fajlnev}</strong> (csatolva)</p>
                                        <p>🔗 <a href="{dok_v.get('link','')}">Jelentkezes az allasra</a></p>
                                    </div>
                                    """)

                                html_reszek.append("<p>Sok sikert! — Karrier Ugynokseg</p>")

                                try:
                                    sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
                                    message = Mail(
                                        from_email="magroandi28@gmail.com",
                                        to_emails=email_cim,
                                        subject="Karrier Ugynokseg — A dokumentumaid keszen vannak!",
                                        html_content="".join(html_reszek)
                                    )
                                    mellekletek = []
                                    for fajlnev, pdf_adat, mime in csatolmanyok:
                                        mellekletek.append(Attachment(
                                            FileContent(base64.b64encode(pdf_adat).decode()),
                                            FileName(fajlnev),
                                            FileType(mime),
                                            Disposition("attachment")
                                        ))
                                    message.attachment = mellekletek

                                    sg.send(message)
                                    st.success(f"🎉 Elküldtük! Nézd meg: {email_cim}")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"Email hiba: {e}")
                    else:
                        # 3. JAVÍTÁS: ha a folyamat végén derül ki, hogy nincs email,
                        # itt HELYBEN meg lehet adni — nem kell a fül tetejére görgetni.
                        st.warning("⚠️ Még nincs megadva email cím — itt helyben megadhatod:")
                        helyi_email = st.text_input(
                            "📧 Email cím", key="tab1_email_helyben",
                            placeholder="nev@email.com", label_visibility="collapsed"
                        )
                        if helyi_email:
                            st.session_state.tab1_email_ertek = helyi_email
                            st.rerun()
                else:
                    st.info("👆 Hagyd jóvá a dokumentumot az elküldéshez!")

                if eredmeny.get("portfilio_ajanlott"):
                    st.markdown("---")
                    st.markdown("""
                    <div style="background:linear-gradient(135deg,#1a1500,#0a0e1a);
                                border:1px solid rgba(212,168,67,0.5);
                                border-radius:12px; padding:32px; text-align:center;">
                        <div style="font-size:28px; margin-bottom:12px;">⭐</div>
                        <div style="color:#D4A843; font-weight:800; font-size:20px; margin-bottom:8px;">
                            PRÉMIUM AJÁNLAT
                        </div>
                        <div style="color:#e2e8f4; font-size:16px; margin-bottom:8px;">
                            A tapasztalatod arany — csak senki nem tudja még.
                        </div>
                        <div style="color:#94a3b8; font-size:13px;">
                            Készítsünk egy profi portfólió oldalt ami előtt meghajol minden recruiter.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col_igen, col_nem = st.columns(2)
                    with col_igen:
                        if st.button("⭐ Igen, kérem!", use_container_width=True, key="portfolio_igen"):
                            st.info("👆 Kattints a **Portfólió Generátor** tabra!")
                    with col_nem:
                        if st.button("Most nem", use_container_width=True, key="portfolio_nem"):
                            pass

    # ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
# KÉPZÉSEK FÜL
# ══════════════════════════════════════════════════════════════
with tab_kepzes:
    st.markdown("### 📚 Képzések, amivel erősebb leszel a piacon")
    st.caption("Piacképes, valós képzések – a szakmádhoz válogatva. Nem kell hozzá CV!")

    # Ha már volt keresés, a felismert szakmát ajánljuk fel alapnak
    _er = st.session_state.get("tab1_eredmeny")
    _alap_szakma = (_er.get("szakma_info", {}) or {}).get("szakma", "") if _er else ""

    kp_szakma = st.text_input(
        "Melyik szakmához keresel képzést?",
        value=_alap_szakma, key="kepzes_szakma_input",
        placeholder="pl. bolti eladó, szoftvertesztelő, ápoló"
    )

    _kepz = []
    if kp_szakma.strip():
        from agents.kepzes_db import terulet_felismeres, kepzesek_szakmahoz
        from utils.adatbazis import kepzesek_lekerdez

        _fo_terulet = terulet_felismeres(kp_szakma)
        _sorrend = ([_fo_terulet] if _fo_terulet else []) + ["nyelvi", "altalanos"]

        # 1) Adatbázisból (Supabase 'kepzesek' tábla — Table Editorban bővítheted)
        _sorok = kepzesek_lekerdez(_sorrend)
        _latott = set()
        for _ter in _sorrend:
            for _s in _sorok:
                if _s.get("terulet") == _ter and _s.get("nev") not in _latott:
                    _latott.add(_s.get("nev"))
                    _kepz.append({
                        "nev": _s.get("nev", ""), "szolgaltato": _s.get("szolgaltato", ""),
                        "link": _s.get("link", ""), "idotartam": _s.get("idotartam", ""),
                        "ar": _s.get("ar", ""), "miert_fontos": _s.get("miert_jo", ""),
                    })
                if len(_kepz) >= 6:
                    break
            if len(_kepz) >= 6:
                break

        # 2) Ha az adatbázis üres/elérhetetlen: beépített kurált lista
        if not _kepz:
            for _k in kepzesek_szakmahoz(kp_szakma, "", max_db=6):
                _kepz.append({
                    "nev": _k.get("nev", ""), "szolgaltato": _k.get("szolgaltato", ""),
                    "link": _k.get("link", ""), "idotartam": _k.get("idotartam", ""),
                    "ar": _k.get("ar", ""), "miert_fontos": _k.get("miert_jo", ""),
                })

    if not kp_szakma.strip():
        st.info("👆 Írd be a szakmád (vagy amire váltanál), és listázzuk a képzéseket.")
    elif not _kepz:
        st.warning("Ehhez a szakmához most nem találtunk képzést — nézd meg az általánosakat: írd be pl. „általános”.")
    else:
        for kp in _kepz:
            with st.expander(f"📖 {kp.get('nev','')} — {kp.get('ar','')}"):
                st.markdown(f"**Szolgáltató:** {kp.get('szolgaltato','')}")
                st.markdown(f"**Időtartam:** {kp.get('idotartam','')}")
                st.markdown(f"**Miért hasznos:** {kp.get('miert_fontos','')}")
                if kp.get("link"):
                    st.link_button("🔗 Megnézem", url=kp.get("link"), use_container_width=True)

# TAB 2: PORTFÓLIÓ GENERÁTOR
# ══════════════════════════════════════════════════════════════
with tab_portfolio:
    st.markdown("### 🌟 Portfólió Generátor")

    cv_betoltve = "cv_szoveg_global" in st.session_state
    if not cv_betoltve:
        st.warning("⚠️ Először töltsd fel a CV-det a **Karrier Ügynök** tabon!")
    else:
        st.success("✅ CV betöltve!")

        # Felül CSAK a két általános link (GitHub / LinkedIn).
        # A "Projekt demo link" + "Demo neve" páros KIKERÜLT, mert duplikálta a
        # projektenkénti "Projekt link" mezőt. Most minden projekt a SAJÁT linkjét viszi.
        col1, col2 = st.columns(2)
        with col1:
            github_link   = st.text_input("GitHub link", key="pf_github")
        with col2:
            linkedin_link = st.text_input("LinkedIn link", key="pf_linkedin")

        # ── A "munkáid" (projektek). A CÍMKÉT a generátor szakma szerint átírja. ──
        st.caption("A munkáid / projektjeid — a portfólió a szakmádhoz igazítva címkézi ezt a szekciót.")
        projektek = []
        proj_szam = st.selectbox("Hány munkát/projektet szeretnél bemutatni?", [0, 1, 2, 3], key="pf_proj_szam")
        for i in range(proj_szam):
            with st.expander(f"📁 {i+1}. munka / projekt", expanded=True):
                pc1, pc2 = st.columns(2)
                with pc1:
                    proj_cim    = st.text_input("Munka / projekt neve", key=f"pf_pcim_{i}")
                    proj_leiras = st.text_area("Rövid leírás", key=f"pf_pleiras_{i}", height=80)
                    proj_tagek  = st.text_input("Technológiák / kulcsszavak (vesszővel)", key=f"pf_ptagek_{i}")
                with pc2:
                    proj_ikon   = st.text_input("Ikon (egy emoji, opcionális)", key=f"pf_pikon_{i}", placeholder="pl. ⚡")
                    proj_cimke  = st.text_input("Címke (opcionális)", key=f"pf_pcimke_{i}", placeholder="pl. Diplomamunka")
                st.markdown("**Linkek (opcionális, max 3):**")
                lc1, lc2, lc3 = st.columns(3)
                with lc1:
                    proj_demo   = st.text_input("Élő demó link", key=f"pf_pdemo_{i}")
                with lc2:
                    proj_github = st.text_input("GitHub link", key=f"pf_pgit_{i}")
                with lc3:
                    proj_egyeb  = st.text_input("Egyéb link", key=f"pf_pegyeb_{i}")
                proj_egyeb_nev = st.text_input("Egyéb link neve (pl. Rendszerterv)", key=f"pf_pegyebnev_{i}",
                                               placeholder="pl. Rendszerterv") if proj_egyeb else ""
                if proj_cim:
                    projektek.append({
                        "cim": proj_cim, "leiras": proj_leiras,
                        "tagek": [t.strip() for t in proj_tagek.split(",") if t.strip()],
                        "ikon": proj_ikon, "cimke": proj_cimke,
                        "demo_link": proj_demo, "github_link": proj_github,
                        "egyeb_link": proj_egyeb, "egyeb_nev": proj_egyeb_nev,
                    })

        # ── KÉRDÉS: Eredmények számokban (a CV-ből gyakran hiányzik, ez teszi hitelessé) ──
        eredmenyek = st.text_area(
            "🏆 Eredmények számokban (opcionális) – a saját szavaiddal",
            key="pf_eredmenyek", height=80,
            placeholder="pl. 30%-kal csökkentettem a feldolgozási időt · 200 ügyfelet kezeltem · 12 fős csapatot vezettem"
        )

        # ── KÉRDÉS: „Próbálj ki!” kihívás (Andi saját ötlete – opcionális szekció) ──
        probald_ki = st.text_area(
            "🎯 „Próbálj ki!” kihívás (opcionális) – egy feladat, amin a recruiter tesztelhet",
            key="pf_probald_ki", height=80,
            placeholder="pl. Adj egy adathalmazt, és 24 órán belül építek rá egy előrejelző modellt."
        )

        foto_file = st.file_uploader("Profilfotó (opcionális)", type=["jpg","jpeg","png"], key="pf_foto")
        foto_base64 = None
        if foto_file:
            foto_base64 = base64.b64encode(foto_file.read()).decode("utf-8")

        # ── 7. JAVÍTÁS: letölthető dokumentumok beágyazása a portfólió HTML-jébe ──
        # Opcionális: a felhasználó dönti el, akar-e CV-t / motivációs levelet a portfólióba.
        # Ha nem kér, a szekció meg sem jelenik a HTML-ben (nincs üres hely).
        dok_lista = []
        with st.expander("📎 Letölthető dokumentumok a portfólióba (opcionális)"):
            dok_kell = st.checkbox("Szeretnék letölthető CV-t / motivációs levelet a portfólióba", key="pf_dok_kell")
            if dok_kell:
                from utils.pdf_sablonok import cv_pdf_general, level_pdf_general
                from agents.karrier_ugynok import ekezet_nelkul
                _fej = elerhetoseg_kinyeres(st.session_state.get("cv_szoveg_global", ""))
                _pdf_adatok = {
                    "nev": _fej["nev"], "pozicio": "",
                    "email": _fej["email"], "telefon": _fej["telefon"], "varos": _fej["varos"],
                    "foto_base64": foto_base64 or st.session_state.get("foto_base64", ""),
                }
                # CV: a robotbarát változat, ha van; különben a feltöltött CV szövege
                cv_forras = st.session_state.get("tab1_general_cv") or st.session_state.get("cv_szoveg_global", "")
                if st.checkbox("📄 Önéletrajz csatolása", key="pf_dok_cv", value=True) and cv_forras:
                    try:
                        cv_pdf = cv_pdf_general(cv_forras, _pdf_adatok, "arany")
                        dok_lista.append({
                            "nev": "Önéletrajz",
                            "fajlnev": f"{ekezet_nelkul(_fej['nev'])}_CV.pdf",
                            "b64": base64.b64encode(cv_pdf).decode("utf-8"),
                        })
                    except Exception as e:
                        st.caption(f"ℹ️ A CV most nem ágyazható be: {e}")

                # Motivációs levél: a Karrier Ügynökben már elkészültek közül lehet választani.
                # Mivel egy konkrét céghez adod be a portfóliót, a cégre szabott levél ide illik.
                _dok = st.session_state.get("tab1_dokumentumok", {})
                level_opciok = {
                    f"{v.get('ceg','')} — {v.get('cim','')}": v
                    for v in _dok.values() if v.get("level")
                }
                if level_opciok:
                    valasztott = st.selectbox(
                        "✉️ Melyik cég motivációs levele kerüljön be?",
                        options=["(nincs levél)"] + list(level_opciok.keys()),
                        key="pf_dok_level_valaszt"
                    )
                    if valasztott != "(nincs levél)":
                        lv = level_opciok[valasztott]
                        try:
                            level_pdf = level_pdf_general(lv["level"], _pdf_adatok, lv.get("szin", "arany"))
                            dok_lista.append({
                                "nev": f"Motivációs levél — {lv.get('ceg','')}",
                                "fajlnev": f"{ekezet_nelkul(_fej['nev'])}_Level_{ekezet_nelkul(lv.get('ceg','Ceg'))}.pdf",
                                "b64": base64.b64encode(level_pdf).decode("utf-8"),
                            })
                        except Exception as e:
                            st.caption(f"ℹ️ A levél most nem ágyazható be: {e}")
                else:
                    st.caption("ℹ️ Motivációs levél a Karrier Ügynök fülön készül – ha ott csinálsz egyet, itt kiválaszthatod.")

        if st.button("🚀 Portfólió elkészítése!", type="primary", key="pf_general"):
            extra_info = {
                "github": github_link, "linkedin": linkedin_link,
                "demo_link": "", "demo_nev": "", "projektek": projektek,
                "eredmenyek": eredmenyek,        # beleszövi a szövegekbe (Sonnet)
                "probald_ki": probald_ki,        # opcionális „Próbálj ki!” szekció
                "dokumentumok": dok_lista,       # opcionális letölthető CV/levél
            }
            with st.spinner("Portfólió generálása..."):
                from agents.portfolio_generator import run as portfolio_gen
                eredmeny_pf = portfolio_gen(
                    cv_szoveg=st.session_state.cv_szoveg_global,
                    extra_info=extra_info, foto_base64=foto_base64
                )
            if "hiba" in eredmeny_pf:
                st.error(f"❌ {eredmeny_pf['hiba']}")
            else:
                # Az állapotot ELTÁROLJUK, hogy a chat utólag tudja csiszolni (rerun-biztos)
                st.session_state.pf_adatok = eredmeny_pf.get("adatok", {})
                st.session_state.pf_szovegek = eredmeny_pf.get("szovegek", {})
                st.session_state.pf_extra = extra_info
                st.session_state.pf_foto = foto_base64
                st.session_state.pf_html = eredmeny_pf.get("html_tartalom", "")
                st.session_state.pf_chat = []
                st.session_state.pf_just_generated = True
                st.rerun()

        # ── PORTFÓLIÓ MEGJELENÍTÉSE + CHAT (a gombon KÍVÜL, hogy rerun után is megmaradjon) ──
        if st.session_state.get("pf_html"):
            # 5. JAVÍTÁS: csak frissen generálva ugrunk a tetejére (chat közben nem)
            if st.session_state.pop("pf_just_generated", False):
                components.html(
                    "<script>window.parent.document.querySelector('section.main')"
                    "?.scrollTo({top:0,behavior:'smooth'});</script>", height=0
                )
            st.success("🎉 Portfólió kész — lent a chattel tovább csiszolhatod!")
            _nev = st.session_state.pf_adatok.get("nev", "portfolio").replace(" ", "_")
            st.download_button(
                "⬇️ Portfólió letöltése (.html)",
                data=st.session_state.pf_html.encode("utf-8"),
                file_name=f"portfolio_{_nev}.html",
                mime="text/html", key="pf_letoltes"
            )

            with st.expander("🌐 Tedd online INGYEN — megosztható link (LinkedIn-re is)"):
                st.markdown("""
**A leggyorsabb út — Netlify Drop (nem kell se fiók, se telepítés):**
1. Töltsd le fent a portfóliót (`.html`).
2. Nyisd meg: **https://app.netlify.com/drop**
3. **Húzd rá** a böngészőben a letöltött `.html` fájlt a jelölt területre.
4. Pár másodperc, és kapsz egy **élő linket** (pl. `https://valami-nev.netlify.app`).
5. Ezt a linket beteheted a **LinkedIn**-edre, az e-mail-aláírásodba, a pályázataidba.

*Tipp:* ha ingyenes fiókot is csinálsz a Netlify-on, a link **véglegesen megmarad** és átnevezheted; fiók nélkül is működik, csak ideiglenesebb.

**Alternatíva (ha sajátabb cím kell):** GitHub Pages — feltöltöd a fájlt egy repóba, és a Settings → Pages alatt kapsz egy `…github.io` linket. Ez kicsit több lépés, de teljesen ingyenes és tartós.
                """)

            # ── PORTFÓLIÓ-CHAT (Powered by Claude) ──
            st.markdown("---")
            st.markdown(
                "#### ✍️ Csiszold a portfóliót — "
                "<span style='color:#D4A843; font-weight:700;'>🤖 Powered by Claude</span>",
                unsafe_allow_html=True
            )
            st.caption("Írd le, mit változtatnál (pl. „tedd rövidebbé a bemutatkozást”, "
                       "„adj hozzá egy projektet: …”, „vedd ki a Próbálj ki szekciót”). "
                       "Csak a portfólión dolgozom — minden üzenet egy gombnyomás (Enter).")

            if "pf_chat" not in st.session_state:
                st.session_state.pf_chat = []
            for _u in st.session_state.pf_chat:
                if _u["szerep"] == "felhasznalo":
                    st.markdown(f'<div class="chat-uzenet-felhasznalo">{_u["szoveg"]}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-uzenet-ugynok">🤖 Claude: {_u["szoveg"]}</div>',
                                unsafe_allow_html=True)

            pf_kerdes = st.chat_input("Mit csiszoljunk a portfólión?", key="pf_chat_input")
            if pf_kerdes:
                st.session_state.pf_chat.append({"szerep": "felhasznalo", "szoveg": pf_kerdes})
                from agents.portfolio_generator import (
                    portfolio_chat, chat_muvelet_alkalmazasa, html_generalas as _pf_htmlgen
                )
                allapot = {
                    "adatok": st.session_state.pf_adatok,
                    "szovegek": st.session_state.pf_szovegek,
                    "extra_info": st.session_state.pf_extra,
                }
                with st.spinner("🤖 Claude dolgozik a portfólión..."):
                    _muvelet = portfolio_chat(allapot, pf_kerdes)
                    allapot = chat_muvelet_alkalmazasa(allapot, _muvelet)
                    st.session_state.pf_adatok = allapot["adatok"]
                    st.session_state.pf_szovegek = allapot["szovegek"]
                    st.session_state.pf_extra = allapot["extra_info"]
                    st.session_state.pf_html = _pf_htmlgen(
                        st.session_state.pf_adatok, st.session_state.pf_szovegek,
                        st.session_state.pf_extra, st.session_state.get("pf_foto")
                    )
                st.session_state.pf_chat.append(
                    {"szerep": "ugynok", "szoveg": _muvelet.get("uzenet", "Kész.")}
                )
                st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 3: KÜLFÖLDI LEHETŐSÉGEK
# ══════════════════════════════════════════════════════════════
with tab_kulfoldi:
    st.markdown("### ✈️ Külföldi Lehetőségek")
    st.markdown("""
    <div style="background:#111827; border:1px solid rgba(212,168,67,0.2);
                border-radius:12px; padding:32px; text-align:center; margin-top:24px;">
        <div style="font-size:48px; margin-bottom:16px;">✈️</div>
        <div style="color:#D4A843; font-weight:700; font-size:20px; margin-bottom:12px;">
            Hamarosan elérhető!
        </div>
        <div style="color:#94a3b8; font-size:14px; line-height:2;">
            🇩🇪 Német Lebenslauf formátum<br>
            🇦🇹 Osztrák munkaerőpiac<br>
            🇬🇧 Angol CV és motivációs levél
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB: KARRIER TANÁCSADÓ — a saját adatbázisunk piaci adataiból
# ══════════════════════════════════════════════════════════════
with tab_tanacsado:
    st.markdown("### 🧭 Karrier Tanácsadó")
    st.caption("Valódi, általunk gyűjtött álláshirdetések adataiból — nem általánosságok.")

    # ══ MUNKAPSZICHOLÓGIAI TESZT (Flow) — lenyitható, nem tolakszik ══
    from utils.teszt import (HOLLAND_KERDESEK, HOLLAND_SKALA, HORGONY_OPCIOK,
                             ENERGIA_SKALA, STRESSZ_SKALA, VALTAS_OKOK,
                             holland_tipus, jollet_jelzes)
    from utils.profil import profil_frissit

    with st.expander("🫶 Ismerd meg magad — 5 perces munkapszichológiai teszt (Flow)",
                     expanded=False):
        st.caption("A válaszaidból Flow teljes képet készít rólad: mi hajt, "
                   "miben vagy erős, és merre érdemes menned. Tudományos alapokon, "
                   "címkézés nélkül.")
        _gdpr_t = st.checkbox(
            "Elfogadom, hogy a válaszaimat a személyre szabott tanácshoz "
            "felhasználjátok. A válaszok csak ebben a munkamenetben élnek, "
            "nem tárolódnak el.", key="teszt_gdpr")

        if _gdpr_t:
            st.markdown("**1️⃣ Mennyire jellemzőek rád az alábbiak?**")
            _h_pontok = {}
            for _kod, _szoveg in HOLLAND_KERDESEK:
                _valasz = st.radio(_szoveg, HOLLAND_SKALA, index=None,
                                   horizontal=True, key=f"teszt_h_{_kod}")
                _h_pontok[_kod] = HOLLAND_SKALA.index(_valasz) + 1 if _valasz else 0

            st.markdown("**2️⃣ Mi a legfontosabb neked a munkában?**")
            _horgony1 = st.radio("Válaszd ki az EGY legfontosabbat:",
                                 HORGONY_OPCIOK, index=None, key="teszt_horgony1")
            _horgony2 = st.selectbox("És a második legfontosabb?",
                                     ["— válassz —"] + [o for o in HORGONY_OPCIOK
                                                        if o != _horgony1],
                                     key="teszt_horgony2")

            st.markdown("**3️⃣ Hogy vagy mostanában?**")
            _energia = st.radio("Egy átlagos nap végén hogyan érzed magad?",
                                ENERGIA_SKALA, index=None, horizontal=True,
                                key="teszt_energia")
            _stressz = st.radio("Mennyire érzed magad feszültnek, nyomás alatt "
                                "a munkád vagy az álláskeresésed miatt?",
                                STRESSZ_SKALA, index=None, horizontal=True,
                                key="teszt_stressz")
            _valtas_ok = st.radio("Mi visz most leginkább az álláskeresés / "
                                  "váltás felé?", VALTAS_OKOK, index=None,
                                  key="teszt_valtasok")
            _mas_ok = ""
            if _valtas_ok == "Más okból":
                _mas_ok = st.text_input("Írd le röviden, mi az:",
                                        key="teszt_masok")
                _valtas_ok = f"Más okból: {_mas_ok}" if _mas_ok.strip() else _valtas_ok

            _hianyzo_t = []
            _ures_hollandok = [i + 1 for i, (_k, _sz) in enumerate(HOLLAND_KERDESEK)
                               if _h_pontok.get(_k, 0) == 0]
            if _ures_hollandok:
                _hianyzo_t.append(f"1️⃣ blokk: {len(_ures_hollandok)} állítás")
            if not _horgony1:
                _hianyzo_t.append("2️⃣ legfontosabb érték")
            if not _energia:
                _hianyzo_t.append("3️⃣ energia-kérdés")
            if not _stressz:
                _hianyzo_t.append("3️⃣ stressz-kérdés")
            if not _valtas_ok:
                _hianyzo_t.append("3️⃣ váltás oka")
            elif _valtas_ok == "Más okból" and not _mas_ok.strip():
                _hianyzo_t.append("3️⃣ írd be, mi a más ok")
            _kitoltve = not _hianyzo_t
            if not _kitoltve:
                st.caption("👆 Még hiányzik: " + " · ".join(_hianyzo_t))
            if st.button("🫶 Kész vagyok — Flow, mit látsz?", type="primary",
                         disabled=not _kitoltve, use_container_width=True,
                         key="teszt_kesz"):
                _tipus = holland_tipus(_h_pontok)
                _jollet = jollet_jelzes(ENERGIA_SKALA.index(_energia),
                                        STRESSZ_SKALA.index(_stressz), _valtas_ok)
                _horgony_szoveg = _horgony1 + (
                    f" · {_horgony2}" if _horgony2 and "válassz" not in _horgony2 else "")
                profil_frissit(holland_tipus=_tipus,
                               karrierhorgony=_horgony_szoveg,
                               jollet_jelzes=_jollet["cimke"],
                               valtas_oka=_valtas_ok)
                st.session_state.teszt_eredmeny = {
                    "tipus": _tipus, "horgony": _horgony_szoveg, "jollet": _jollet}

        _te = st.session_state.get("teszt_eredmeny")
        if _te:
            st.markdown("---")
            st.markdown(f"**🧩 Érdeklődés-típusod:** {_te['tipus']}")
            st.markdown(f"**⚓ Ami a legfontosabb neked:** {_te['horgony']}")
            if _te["jollet"]["figyelem"]:
                st.warning(f"💛 {_te['jollet']['tamogato_uzenet']}")

            # ── ③ FLOW RÉSZLETES KIÉRTÉKELÉSE (tudásbázisból) ──
            if st.button("🫶 Kérem Flow részletes kiértékelését",
                         use_container_width=True, key="flow_kiert_gomb"):
                with st.spinner("Flow a tudásbázisban keres és fogalmaz…"):
                    from utils.flow_agy import flow_kiertekeles
                    from utils.profil import profil as _prof_leker
                    st.session_state.flow_kiertekeles = flow_kiertekeles(_prof_leker())
            _fk = st.session_state.get("flow_kiertekeles")
            if _fk:
                st.markdown(f"""<div style="background:#111827;
                    border:1px solid rgba(212,168,67,0.4); border-radius:12px;
                    padding:18px 22px; color:#e2e8f4; font-size:14px;
                    line-height:1.8;">{_fk.replace(chr(10), "<br>")}</div>""",
                    unsafe_allow_html=True)
                # Kiégés/bántalmazás + ismert szakma → konkrét váltás-kapu
                from utils.profil import profil as _prof_v
                if (_te["jollet"]["figyelem"] and _prof_v().get("szakma")):
                    st.info(f"🔀 **Ha váltáson gondolkodsz:** lejjebb válaszd ki "
                            f"a szakmád ({_prof_v()['szakma']}), és a "
                            f"„🔀 Igen, mutasd az átjárási lehetőségeket” gombbal "
                            f"megnézzük, hova vihetnéd át a tudásod — bérrel és "
                            f"hiányzó készségekkel együtt. Te döntesz.")
                # Frissítés: ha azóta bővült a profil (pl. utólag jött CV)
                if st.button("🔄 Kiértékelés frissítése az új adataimmal",
                             key="flow_kiert_frissit", use_container_width=True):
                    with st.spinner("Flow újraolvassa a teljes profilod…"):
                        from utils.flow_agy import flow_kiertekeles as _fkier
                        st.session_state.flow_kiertekeles = _fkier(_prof_v())
                    st.rerun()
            elif st.session_state.get("flow_kiert_gomb"):
                st.warning("Flow most nem érhető el (valószínűleg elfogyott a napi "
                           "AI-kvóta). A profilod megvan — próbáld újra később.")

    from utils.adatbazis import szakmak_lista, szakma_statisztika

    _szl = szakmak_lista()
    if not _szl:
        st.info("Még nincs elég adat az adatbázisban — futtasd a gyűjtőt, vagy nézz vissza később.")
    else:
        _nevek = [s["szakma"] for s in _szl]
        _er_t = st.session_state.get("tab1_eredmeny")
        _felismert = (_er_t.get("szakma_info", {}) or {}).get("szakma", "") if _er_t else ""

        def _szakma_talalat(felismert, nevek):
            """A felismert szakmához legjobban illő név a listából — szavak
            egyezése alapján ('Python backend fejlesztő' -> 'Python fejlesztő')."""
            if not felismert:
                return None
            import re as _re
            fsz = set(_re.findall(r"\w+", felismert.lower()))
            legjobb, pont = None, 0.0
            for n in nevek:
                nsz = set(_re.findall(r"\w+", n.lower()))
                if not nsz:
                    continue
                kozos = len(fsz & nsz)
                if not kozos:
                    continue
                p = kozos / len(nsz) + (0.5 if n.lower() == felismert.lower() else 0.0)
                if p > pont:
                    pont, legjobb = p, n
            return legjobb

        # FRISS CV-elemzés után automatikusan a felismert szakmára ugrunk,
        # felülírva a korábban kiválasztottat
        if st.session_state.pop("tan_kovesse_cv", False):
            _talalt = _szakma_talalat(_felismert, _nevek)
            if _talalt:
                st.session_state["tan_szakma"] = _talalt

        # Üres alapértelmezés: elemzés CSAK akkor indul, ha a felhasználó választott.
        # (A CV-elemzés utáni automatikus átugrás maradt — azt a felhasználó indította.)
        _URES = "— válassz szakmát —"
        _opciok = [_URES] + _nevek

        _valasztott = st.selectbox("Melyik szakma érdekel?", _opciok, index=0, key="tan_szakma")
        _stat = szakma_statisztika(_valasztott) if _valasztott != _URES else None

        if _valasztott == _URES:
            st.info("👆 Válassz egy szakmát a listából — addig nem indítunk elemzést.")
        elif not _stat or not _stat.get("keszsegek"):
            st.warning("Ehhez a szakmához még kevés az adat — pár nap gyűjtés után térj vissza.")
        else:
            st.markdown(f"#### {_valasztott} — {_stat.get('hirdetesek_szama', 0)} valódi hirdetés elemzése alapján")
            # ── PROFIL: viselkedési jel — ennek a szakmának a piacát nézi ──
            from utils.profil import erdeklodes_jelzes as _ej3
            _ej3(f"{_valasztott} piaci adatai")

            # ── A TANÁCSADÓ VÉLEMÉNYE — kizárólag a saját adatbázisunk számaiból írva ──
            _tkulcs = f"tan_velemeny_{_valasztott}"
            if _tkulcs not in st.session_state:
                with st.spinner("A tanácsadó összegzi a piaci adatokat..."):
                    from agents.karrier_ugynok import tanacsado_velemeny
                    st.session_state[_tkulcs] = tanacsado_velemeny(_valasztott, _stat)
            if not st.session_state.get(_tkulcs):
                # TARTALÉK: ha az AI most nem elérhető, a nyers számokból írunk körképet
                _top3 = ", ".join([k.get("keszseg", "") for k in _stat["keszsegek"][:3]
                                   if k.get("keszseg")])
                st.session_state[_tkulcs] = (
                    f"A(z) {_valasztott} szakmában {_stat.get('hirdetesek_szama', 0)} valódi "
                    f"hirdetést elemeztünk. A leggyakrabban kért készségek: {_top3}. "
                    f"A béradatokat lejjebb, a piaci részleteknél találod."
                )
                st.session_state[_tkulcs + "_ai_nelkul"] = True
            if st.session_state.get(_tkulcs):
                _tszoveg = st.session_state[_tkulcs].replace("\n", "<br>")
                st.markdown(f"""<div style="background:#111827; border:1px solid rgba(212,168,67,0.4);
                    border-radius:12px; padding:18px 22px; margin:8px 0 18px; color:#e2e8f4;
                    font-size:14px; line-height:1.8;">
                    <span style="color:#D4A843; font-weight:700;">🧭 Mit mond a piac?</span><br><br>
                    {_tszoveg}</div>""", unsafe_allow_html=True)
                if st.session_state.get(_tkulcs + "_ai_nelkul"):
                    st.caption("ℹ️ Gyors összefoglaló a nyers számokból — a részletes elemzés "
                               "a napi AI-keret visszatöltődése után (holnap) automatikusan elérhető.")

            # ── PIACI RÉSZLETEK — a kincsesbánya, jól láthatóan ──
            st.markdown("### 📊 Mit kérnek a hirdetések?")
            _blokkok = [
                ("eszkoz", "🛠 Eszközök, technológiák"),
                ("feladat", "📋 Tipikus feladatok"),
                ("elvaras", "🎓 Elvárások"),
                ("iparag", "🏭 Iparágak, ahol keresik"),
                ("soft", "🤝 Emberi készségek"),
            ]
            for _tip, _cim in _blokkok:
                _elemek = [k for k in _stat["keszsegek"]
                           if k.get("tipus") == _tip and (k.get("elofordulas") or 0) >= 2][:8]
                if not _elemek:
                    continue
                st.markdown(f"**{_cim}**")
                _chips = " ".join([
                    f"<span style='display:inline-block; background:#1e2d45; border:1px solid #2e5080; "
                    f"border-radius:16px; padding:4px 12px; margin:3px 4px 3px 0; font-size:13px; "
                    f"color:#e2e8f4;'>{k.get('keszseg', '')} "
                    f"<span style='color:#D4A843; font-weight:700;'>{k.get('hirdetesek_szazaleka', 0)}%</span></span>"
                    for k in _elemek
                ])
                st.markdown(_chips, unsafe_allow_html=True)

            # ── BÉREK: egységesen havi bruttó forintra átszámítva ──
            _berek = _stat.get("bersavok", [])
            _havi = []
            for _b in _berek:
                _bs = str(_b)
                _szamok = [int(x.replace(" ", "").replace("\xa0", ""))
                           for x in re.findall(r"\d[\d \xa0]{3,}\d|\d{4,}", _bs)]
                _euro = "€" in _bs or "eur" in _bs.lower()
                _eves = "év" in _bs.lower() and "hó" not in _bs.lower()
                for _x in _szamok:
                    if _euro:
                        _x = _x * 400          # hozzávetőleges árfolyam
                    if _eves or _x > 6_000_000:
                        _x = _x // 12
                    if 150_000 <= _x <= 5_000_000:
                        _havi.append(_x)
            if _havi:
                _also = f"{min(_havi):,}".replace(",", " ")
                _felso = f"{max(_havi):,}".replace(",", " ")
                st.markdown(f"**💰 Bérek a hirdetésekben:** jellemzően "
                            f"**{_also} – {_felso} Ft/hó** (bruttó)")
                st.caption(f"{len([b for b in _berek if b])} hirdetés béradata alapján; "
                           "az éves és eurós béreket havi forintra számítottuk át.")

            # ── HIVATALOS KSH-ÁTLAG + összevetés a hirdetésekkel ──
            from utils.adatbazis import ksh_kereset
            _ksh = ksh_kereset(_valasztott)
            if _ksh and _ksh.get("ertek"):
                _kv = f"{int(_ksh['ertek']):,}".replace(",", " ")
                st.markdown(f"**🏛 Hivatalos átlagkereset (KSH, {_ksh.get('idoszak', '')}):** "
                            f"**{_kv} Ft/hó** (bruttó) — a legközelebbi KSH-foglalkozás: "
                            f"„{_ksh.get('megnevezes', '')}”")
                if _havi:
                    import statistics as _stx
                    _med = _stx.median(_havi)
                    if _med > int(_ksh["ertek"]) * 1.1:
                        st.caption("📈 A hirdetések a hivatalos átlag FELETT ígérnek — "
                                   "keresett a szakma, jó az alkupozíciód.")
                    elif _med < int(_ksh["ertek"]) * 0.9:
                        st.caption("📉 A hirdetések a hivatalos átlag ALATT ígérnek — "
                                   "bértárgyalásnál hivatkozz a KSH-átlagra.")
                    else:
                        st.caption("⚖️ A hirdetések nagyjából a hivatalos átlagnak "
                                   "megfelelő bért ígérnek.")

            st.markdown("---")
            _cv_t = st.session_state.get("cv_szoveg_global", "")
            if not _cv_t:
                st.info("💡 Ha a Karrier Ügynök fülön betöltöd a CV-det, itt megmutatjuk, "
                        "MELY piaci elvárások hiányoznak belőle — és mivel pótolhatod.")
            else:
                if st.button("🧭 Vessük össze a CV-mmel!", key="tan_gap_gomb", use_container_width=True):
                    with st.spinner("Összevetés a piaci elvárásokkal..."):
                        from agents.karrier_ugynok import skill_gap_elemzes
                        _ksz = [_k.get("keszseg", "") for _k in _stat["keszsegek"][:15]]
                        st.session_state.tan_gap_eredmeny = skill_gap_elemzes(_cv_t, _ksz)
                        st.session_state.tan_gap_szakma = _valasztott
                    if not st.session_state.get("tan_gap_eredmeny"):
                        st.error("Az összevetés most nem sikerült (a Gemini nem válaszolt "
                                 "— valószínűleg perc-limit). Várj fél percet, és nyomd meg újra.")

                _gap = st.session_state.get("tan_gap_eredmeny")
                if _gap and st.session_state.get("tan_gap_szakma") == _valasztott:
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        st.markdown("**✅ Ez már megvan benned:**")
                        for _m in _gap.get("megvan", []):
                            st.markdown(f"<div style='color:#4ade80; font-size:13px; "
                                        f"padding:2px 0;'>✓ {_m}</div>", unsafe_allow_html=True)
                    with _c2:
                        st.markdown("**❌ Ez hiányzik a CV-dből:**")
                        for _h in _gap.get("hianyzik", []):
                            st.markdown(f"<div style='color:#ef4444; font-size:13px; "
                                        f"padding:2px 0;'>✗ {_h}</div>", unsafe_allow_html=True)
                    if _gap.get("hianyzik"):
                        st.caption("📚 Ha a tudás megvan, csak a CV-dből hiányzik: a Karrier Ügynök "
                                   "fülön az „✨ Írd át” beépíti. Ha tanulni kell: a Képzések fülön "
                                   "találsz hozzá minőségi képzést.")

            # ── ÁTJÁRÁSI TÉRKÉP — CSAK KÉRÉSRE (váltást nem tukmálunk!) ──
            st.markdown("---")
            st.markdown("### 🔀 Gondolkodsz szakmaváltáson?")
            st.caption("Ha igen, megmutatjuk, hova vihető át a tudásod — a piac valós adatai alapján.")
            if st.button("🔀 Igen, mutasd az átjárási lehetőségeket", key="atjaras_gomb"):
                st.session_state["atjaras_szakma"] = _valasztott
            _atj = []
            if st.session_state.get("atjaras_szakma") == _valasztott:
                from utils.adatbazis import szakma_atjaras
                _atj = szakma_atjaras(_valasztott)
                # ── PROFIL: váltáson gondolkodik + a céljai ──
                from utils.profil import profil_frissit as _pf, erdeklodes_jelzes as _ej
                _ej(f"szakmaváltás ({_valasztott} → máshova)")
                if _atj:
                    _pf(atjaras_celok=[a["szakma"] for a in _atj[:3]])
            if st.session_state.get("atjaras_szakma") == _valasztott and not _atj:
                st.info("🔧 A megbízható számításhoz még érik az adatbázis — "
                        "amint elég közös adat gyűlik össze, itt jelennek meg a rokon szakmák.")
            if _atj:
                for _a in _atj:
                    _szin = ("#4ade80" if _a["atfedes"] >= 60
                             else "#D4A843" if _a["atfedes"] >= 35 else "#94a3b8")
                    _hi = ", ".join(_a["hianyzo"]) if _a["hianyzo"] else "nincs jelentős hiány"
                    st.markdown(f"""<div style="background:#111827; border:1px solid #1e3a5f;
                        border-radius:10px; padding:12px 16px; margin:8px 0;">
                        <div style="display:flex; justify-content:space-between;">
                          <span style="color:#e2e8f4; font-weight:700;">{_a['szakma']}</span>
                          <span style="color:{_szin}; font-weight:800;">{_a['atfedes']}% átfedés</span>
                        </div>
                        <div style="color:#94a3b8; font-size:13px; margin-top:4px;">
                          {_a['kozos']} közös készség · amit pótolni kellene:
                          <span style="color:#e2e8f4;">{_hi}</span>
                        </div></div>""", unsafe_allow_html=True)

            # ── AKCIÓTERV — 3 konkrét lépés ──
            st.markdown("### ✅ Akcióterv")
            _lepesek = []
            _gap2 = (st.session_state.get("tan_gap_eredmeny")
                     if st.session_state.get("tan_gap_szakma") == _valasztott else None)
            if _gap2 and _gap2.get("hianyzik"):
                _lepesek.append("Tanuld meg / pótold: <strong>"
                                + ", ".join(_gap2["hianyzik"][:2])
                                + "</strong> → a 📚 Képzések fülön találsz hozzá minőségi képzést")
                _lepesek.append("Ami megvan, de a CV-d nem mutatja: a 🕵️ Karrier Ügynök fülön "
                                "az „✨ Írd át” beépíti")
            else:
                _top2 = [k.get("keszseg") for k in _stat["keszsegek"][:2] if k.get("keszseg")]
                _lepesek.append("A piac két legkeresettebb készsége: <strong>"
                                + ", ".join(_top2)
                                + "</strong> — ha megvannak, emeld ki a CV-dben; ha nincsenek, "
                                  "a 📚 Képzések fülön indulj")
                _lepesek.append("Tölts fel CV-t a 🕵️ Karrier Ügynök fülön — utána itt személyre "
                                "szabott hiánylistát és tervet kapsz")
            if _atj:
                _lepesek.append(f"Rokon szakma {_atj[0]['atfedes']}% átfedéssel: "
                                f"<strong>{_atj[0]['szakma']}</strong> — érdemes arra is nézelődnöd")
            _lep_html = "".join([
                f"<div style='margin:7px 0;'><span style='color:#D4A843; "
                f"font-weight:800;'>{_ix+1}.</span> {_l}</div>"
                for _ix, _l in enumerate(_lepesek)
            ])
            st.markdown(f"""<div style="background:linear-gradient(135deg,#1a1500,#0a0e1a);
                border:1px solid rgba(212,168,67,0.5); border-radius:12px;
                padding:16px 20px; color:#e2e8f4; font-size:14px;">{_lep_html}</div>""",
                unsafe_allow_html=True)

