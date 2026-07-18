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
    layout="wide"
)

st.markdown("""
<style>
.stApp { background-color: #0a0e1a !important; }
.block-container { padding: 2rem 3rem; max-width: 1100px; margin: 0 auto; }
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
        return f"""<div style="display:flex; justify-content:center; padding:12px 0;">{_kor(before, "ATS-ILLESZKEDÉS")}</div>"""

    nyil = '<div style="font-size:34px; color:#D4A843; align-self:center; padding:0 8px;">&#10142;</div>'
    return f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:8px;
                background:#0d1117; border:1px solid rgba(212,168,67,0.25); border-radius:12px; padding:18px; margin:12px 0;">
      {_kor(before, "EREDETI CV", nagy=False)}
      {nyil}
      {_kor(after, "ROBOTBARÁT CV", nagy=False)}
    </div>"""


# ── GDPR ──────────────────────────────────────────────────────
if "gdpr_elfogadva" not in st.session_state:
    st.session_state.gdpr_elfogadva = False

if not st.session_state.gdpr_elfogadva:
    st.markdown("""
    <div style="max-width:700px; margin:80px auto; text-align:center;">
        <div style="font-size:64px; margin-bottom:24px;">🕵️</div>
        <h1 style="font-size:36px; font-weight:800; color:#D4A843; margin-bottom:12px;">
            Karrier-Ügynökség
        </h1>
        <p style="color:#94a3b8; font-size:16px; line-height:1.8; margin-bottom:40px;">
            MI-alapú személyes álláskeresési asszisztens.
        </p>
        <div style="background:#111827; border:1px solid rgba(212,168,67,0.3);
                    border-radius:12px; padding:28px; text-align:left; margin-bottom:32px;">
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:12px;">
                🔒 Adatkezelési nyilatkozat
            </div>
            <p style="color:#94a3b8; font-size:13px; line-height:1.8; margin:0;">
                A feltöltött CV-d és személyes adataid az álláskereső elemzés céljából
                az <strong style="color:#f1f5f9;">Anthropic Claude API</strong>-ra kerülnek továbbításra.
                <strong style="color:#f1f5f9;">A feldolgozott adatok nem tárolódnak.</strong>
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
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
st.markdown("""
<div style="background:linear-gradient(135deg,#1C2540 0%,#0A1628 100%);
            padding:24px 32px; border-radius:12px; margin-bottom:24px;
            border-bottom:3px solid #D4A843;">
    <div style="display:flex; align-items:center; gap:16px;">
        <span style="font-size:40px;">🕵️</span>
        <div>
            <div style="font-size:26px; font-weight:800; color:#D4A843;">Karrier-Ügynökség</div>
            <div style="font-size:13px; color:#94a3b8; margin-top:4px;">
                Claude API · ATS optimalizálás · Személyre szabott dokumentumok
            </div>
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
tab_ugynok, tab_portfolio, tab_kepzes, tab_kulfoldi = st.tabs([
    "🕵️ Karrier Ügynök",
    "🌟 Portfólió Generátor",
    "📚 Képzések",
    "✈️ Külföldi Lehetőségek"
])

# ══════════════════════════════════════════════════════════════
# TAB 1: KARRIER ÜGYNÖK
# ══════════════════════════════════════════════════════════════
with tab_ugynok:

    st.markdown("""
    <div style="text-align:center; padding:28px 0 16px;">
        <div style="font-family:'Georgia',serif; font-size:26px;
                    color:#D4A843; font-weight:700; margin-bottom:8px;">
            Más CV-k elvesznek a robotszűrőn.
        </div>
        <div style="font-family:'Georgia',serif; font-size:26px;
                    color:#e2e8f4; font-weight:400; font-style:italic;">
            A tiéd nem fog.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "belepo_mod" not in st.session_state:
        st.session_state.belepo_mod = None

    def _valt_mod(uj_mod):
        st.session_state.belepo_mod = uj_mod
        st.session_state.mutasd_allasok = False

    van_cv = bool(st.session_state.get("cv_szoveg_global", "").strip())

    # ── HÁROM BELÉPŐ KÁRTYA ───────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div style="background:#111827; border:1px solid rgba(212,168,67,0.3);
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">🔍</div>
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:6px;">Van CV-m — nézd át</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Átmegy a robotszűrőn (ATS)? Megmondjuk, mi a baj. Nem írjuk át.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔍 Átvizsgálom", key="mod_elemez", use_container_width=True):
            _valt_mod("elemez")
    with c2:
        st.markdown("""
        <div style="background:#111827; border:1px solid rgba(212,168,67,0.3);
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">✨</div>
            <div style="color:#D4A843; font-weight:700; font-size:15px; margin-bottom:6px;">Van CV-m — írd át</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Robotbarát CV + akár 5 állásra szabott CV és motivációs levél.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✨ Átírom és pályázom", key="mod_atir", use_container_width=True):
            _valt_mod("atir")
    with c3:
        st.markdown("""
        <div style="background:#111827; border:1px solid rgba(212,168,67,0.15);
                    border-radius:12px; padding:18px; text-align:center; min-height:140px;">
            <div style="font-size:28px; margin-bottom:6px;">✍️</div>
            <div style="color:#e2e8f4; font-weight:700; font-size:15px; margin-bottom:6px;">Nincs CV-m</div>
            <div style="color:#94a3b8; font-size:12px; min-height:54px;">Pár adatból robotbarát CV-t készítünk neked.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✍️ Készíttetek egyet", key="mod_keszit", use_container_width=True):
            _valt_mod("keszit")

    mod = st.session_state.get("belepo_mod")
    if van_cv:
        st.caption("✅ A CV-d betöltve – bármelyik kártyánál ezzel dolgozhatsz tovább, nem kell újra feltölteni.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # K1 — VAN CV-M, NÉZD ÁT (csak elemzés, nem ír át)
    # ════════════════════════════════════════════════════════
    if mod == "elemez":
        st.markdown("---")
        st.info("📄 Megnézzük, **átmegy-e a robotszűrőn (ATS)**, és mi miatt szűrne ki. A CV-det **nem** írjuk át.")

        cv_kell = not van_cv or st.session_state.get("csere_elemez", False)
        cv_file = None
        if cv_kell:
            cv_file = st.file_uploader("CV feltöltése (PDF)", type=["pdf"], key="cv_up_elemez", label_visibility="collapsed")
        else:
            cc1, cc2 = st.columns([3, 1])
            with cc1:
                st.success("A korábban feltöltött CV-det használjuk.")
            with cc2:
                if st.button("🔄 Másikat töltök fel", key="csere_elemez_gomb", use_container_width=True):
                    st.session_state.csere_elemez = True
                    st.rerun()

        indit = st.button("🔍 Nézd át a CV-met", type="primary", key="akcio_elemez",
                          disabled=(cv_kell and cv_file is None), use_container_width=True)
        if indit:
            if cv_file is not None:
                with pdfplumber.open(cv_file) as pdf:
                    st.session_state.cv_szoveg_global = "".join([p.extract_text() or "" for p in pdf.pages])
                st.session_state.csere_elemez = False
            with st.spinner("🔍 Robotszűrő-elemzés..."):
                from agents.karrier_ugynok import run as ugynok_run
                st.session_state.tab1_eredmeny = ugynok_run(
                    cv_szoveg=st.session_state.get("cv_szoveg_global", ""),
                    szakma_megadva="", helyszin="Budapest")
                st.session_state.belepo_mod_aktiv = "elemez"

        if st.session_state.get("tab1_eredmeny") and st.session_state.get("belepo_mod_aktiv") == "elemez":
            er = st.session_state.tab1_eredmeny
            if "hiba" in er:
                st.error(f"❌ {er['hiba']}")
            else:
                _diag = er.get("diagnozis", {})
                _szi = er.get("szakma_info", {})
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
                st.markdown("""<div style="background:linear-gradient(135deg,#1a1500,#0a0e1a);border:1px solid rgba(212,168,67,0.5);border-radius:12px;padding:24px;text-align:center;margin-top:16px;"><div style="color:#D4A843;font-weight:800;font-size:17px;margin-bottom:6px;">Szeretnéd, hogy átjusson a szűrőn?</div><div style="color:#e2e8f4;font-size:14px;">Válaszd fent a <strong>„✨ Van CV-m — írd át”</strong> kártyát – elkészítjük a robotbarát CV-det, és akár 5 állásra szabott jelentkezést is. A CV-det már nem kell újra feltöltened.</div></div>""", unsafe_allow_html=True)
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
            cv_file = st.file_uploader("CV feltöltése (PDF)", type=["pdf"], key="cv_up_atir", label_visibility="collapsed")
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

        indit = st.button("🔎 Keresés indítása (állások + ATS-elemzés)", type="primary", key="akcio_atir",
                          disabled=(cv_kell and cv_file is None), use_container_width=True)
        if indit:
            if cv_file is not None:
                with pdfplumber.open(cv_file) as pdf:
                    st.session_state.cv_szoveg_global = "".join([p.extract_text() or "" for p in pdf.pages])
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
    st.caption("Piacképes, valós képzések – a szakmádhoz válogatva.")
    _er = st.session_state.get("tab1_eredmeny")
    _kepz = _er.get("kepzesek", []) if _er else []
    if not _kepz:
        st.info("Előbb a **Karrier Ügynök** fülön vizsgáltasd át vagy készíttesd el a CV-det – utána itt a szakmádhoz illő képzéseket ajánlunk.")
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
