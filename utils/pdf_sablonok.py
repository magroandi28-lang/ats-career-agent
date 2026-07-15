# -*- coding: utf-8 -*-
# PDF Sablon Generátor - utils/pdf_sablonok.py
# Elegáns, ATS-barát CV + motivációs levél, vektoros ikonokkal

import os
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, Polygon, PolyLine
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── FONT REGISZTRÁCIÓ (ő/ű miatt) ────────────────────────────
FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

_KONYVTARAK = [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"),
    os.path.join(os.getcwd(), "fonts"),
]


def _elso_letezo(fajlnev, konyvtarak):
    for k in konyvtarak:
        ut = os.path.join(k, fajlnev)
        if os.path.exists(ut):
            return ut
    return None


def _font_regisztracio():
    global FONT_NORMAL, FONT_BOLD, FONT_ITALIC
    dv_n = _elso_letezo("DejaVuSans.ttf", _KONYVTARAK)
    dv_b = _elso_letezo("DejaVuSans-Bold.ttf", _KONYVTARAK)
    dv_i = _elso_letezo("DejaVuSans-Oblique.ttf", _KONYVTARAK)
    win_n = r"C:\Windows\Fonts\arial.ttf"
    win_b = r"C:\Windows\Fonts\arialbd.ttf"
    win_i = r"C:\Windows\Fonts\ariali.ttf"

    jeloltek = []
    if dv_n:
        jeloltek.append(("CVFont", dv_n, dv_b, dv_i))
    if os.path.exists(win_n):
        jeloltek.append(("CVFont", win_n, win_b, win_i))

    for nev, n, b, i in jeloltek:
        try:
            pdfmetrics.registerFont(TTFont(nev, n))
            FONT_NORMAL = nev
            if b and os.path.exists(b):
                pdfmetrics.registerFont(TTFont(nev + "-Bold", b))
                FONT_BOLD = nev + "-Bold"
            else:
                FONT_BOLD = nev
            if i and os.path.exists(i):
                pdfmetrics.registerFont(TTFont(nev + "-Italic", i))
                FONT_ITALIC = nev + "-Italic"
            else:
                FONT_ITALIC = nev
            return
        except Exception:
            continue


_font_regisztracio()


# ── SZÍNPALETTA ──────────────────────────────────────────────
SZINEK = {
    "kek":     {"fo": colors.HexColor('#1a3a5c'), "akcent": colors.HexColor('#2563eb'), "nev": "Kék"},
    "arany":   {"fo": colors.HexColor('#1a1a2e'), "akcent": colors.HexColor('#b8860b'), "nev": "Arany"},
    "zold":    {"fo": colors.HexColor('#14321e'), "akcent": colors.HexColor('#16a34a'), "nev": "Zöld"},
    "bordó":   {"fo": colors.HexColor('#3a1620'), "akcent": colors.HexColor('#be123c'), "nev": "Bordó"},
    "antracit":{"fo": colors.HexColor('#1f2937'), "akcent": colors.HexColor('#475569'), "nev": "Antracit"},
}

SOTET    = colors.HexColor('#111827')
FEKETE   = colors.HexColor('#1f2937')
SZURKE   = colors.HexColor('#6b7280')
PROFIL_SZ= colors.HexColor('#374151')
HAIRLINE = colors.HexColor('#d8dee9')


# ── SZÍN AJÁNLÁS ─────────────────────────────────────────────

def szin_ajanlat(szakma_kategoria: str) -> str:
    if not szakma_kategoria:
        return "arany"
    kat = szakma_kategoria.lower()
    if any(s in kat for s in ["it", "informatika", "programozó", "fejlesztő", "mérnök"]):
        return "kek"
    if any(s in kat for s in ["egészség", "ápoló", "orvos"]):
        return "zold"
    if any(s in kat for s in ["jog", "pénzügy", "könyvelő"]):
        return "bordó"
    if any(s in kat for s in ["marketing", "kreatív"]):
        return "antracit"
    return "arany"


def sablon_valasztas(szakma_kategoria: str) -> str:
    return szin_ajanlat(szakma_kategoria)


def szinek_listaja() -> list:
    return [
        {"kulcs": "kek",      "nev": "Kék",      "leiras": "IT, tech"},
        {"kulcs": "arany",    "nev": "Arany",    "leiras": "Üzleti, elegáns"},
        {"kulcs": "zold",     "nev": "Zöld",     "leiras": "Egészségügy, szakma"},
        {"kulcs": "bordó",    "nev": "Bordó",    "leiras": "Jog, pénzügy"},
        {"kulcs": "antracit", "nev": "Antracit", "leiras": "Modern, semleges"},
    ]


# ── VEKTOROS IKONOK (font-független, minden gépen látszik) ───

def _ikon_telefon(szin):
    d = Drawing(11, 11)
    d.add(Rect(2.5, 0.5, 6, 10, rx=1.3, ry=1.3,
               strokeColor=szin, strokeWidth=1, fillColor=None))
    d.add(Line(4.5, 1.7, 6.5, 1.7, strokeColor=szin, strokeWidth=1))
    return d


def _ikon_email(szin):
    d = Drawing(12, 11)
    d.add(Rect(0.5, 1.5, 11, 8, rx=0.8, ry=0.8,
               strokeColor=szin, strokeWidth=1, fillColor=None))
    d.add(PolyLine([0.8, 9, 6, 5, 11.2, 9], strokeColor=szin, strokeWidth=1, fillColor=None))
    return d


def _ikon_hely(szin):
    d = Drawing(11, 11)
    d.add(Polygon([5.5, 0.5, 2, 6.5, 9, 6.5],
                  strokeColor=szin, strokeWidth=0, fillColor=szin))
    d.add(Circle(5.5, 7, 3.2, strokeColor=szin, strokeWidth=1, fillColor=None))
    d.add(Circle(5.5, 7, 1.1, strokeColor=szin, strokeWidth=0, fillColor=szin))
    return d


# ── STÍLUSOK ─────────────────────────────────────────────────

def stilusok_keszites(akcent_szin, s: float = 1.0):
    # s = sűrítő-faktor (1.0 = normál; <1 = tömörebb térközök az egy oldalra illesztéshez)
    def sp(x):
        return max(1, round(x * s))
    return {
        "nev": ParagraphStyle('Nev', fontName=FONT_BOLD, fontSize=20,
                              textColor=SOTET, leading=24, spaceAfter=2),
        "pozicio": ParagraphStyle('Pozicio', fontName=FONT_BOLD, fontSize=10.5,
                                  textColor=akcent_szin, leading=14, spaceAfter=3),
        "elerheto": ParagraphStyle('Elerheto', fontName=FONT_NORMAL, fontSize=9,
                                   textColor=SZURKE, leading=12),
        "profil": ParagraphStyle('Profil', fontName=FONT_ITALIC, fontSize=10,
                                 textColor=PROFIL_SZ, leading=round(14*s) if s < 1 else 14, alignment=TA_JUSTIFY),
        "szekc": ParagraphStyle('Szekc', fontName=FONT_BOLD, fontSize=10.5,
                                textColor=SOTET, leading=14, spaceBefore=sp(11), spaceAfter=sp(2),
                                keepWithNext=1),
        "munka_cim": ParagraphStyle('MunkaCim', fontName=FONT_BOLD, fontSize=10.5,
                                    textColor=FEKETE, leading=14, spaceBefore=sp(8), spaceAfter=0,
                                    keepWithNext=1),
        "munka_ceg": ParagraphStyle('MunkaCeg', fontName=FONT_ITALIC, fontSize=9,
                                    textColor=SZURKE, leading=12, spaceAfter=sp(4), keepWithNext=1),
        "normal": ParagraphStyle('Normal', fontName=FONT_NORMAL, fontSize=10,
                                 textColor=FEKETE, leading=round(14*s) if s < 1 else 14, spaceAfter=sp(3), alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle('Bullet', fontName=FONT_NORMAL, fontSize=10,
                                 textColor=FEKETE, leading=round(14*s) if s < 1 else 14, spaceAfter=sp(3),
                                 leftIndent=14, firstLineIndent=-8, alignment=TA_LEFT),
    }


# ── FEJLÉC ───────────────────────────────────────────────────

def _kor_foto(foto_base64, meret=2.4*cm):
    """base64 stringből KÖR alakúra vágott profilfotó (platypus Image).
    Hibás/hiányzó kép esetén None, hogy a fejléc fotó nélkül menjen tovább."""
    if not foto_base64:
        return None
    try:
        import base64 as _b64
        from PIL import Image as _PILImage, ImageDraw as _ImageDraw
        from reportlab.platypus import Image as _RLImage

        adat = foto_base64
        if "," in adat:
            adat = adat.split(",", 1)[1]
        nyers = _b64.b64decode(adat)
        kep = _PILImage.open(io.BytesIO(nyers)).convert("RGBA")

        # középre vágás négyzetre
        w, h = kep.size
        oldal = min(w, h)
        bal = (w - oldal) // 2
        felso = (h - oldal) // 2
        kep = kep.crop((bal, felso, bal + oldal, felso + oldal))
        kep = kep.resize((300, 300), _PILImage.LANCZOS)

        # kör maszk
        maszk = _PILImage.new("L", (300, 300), 0)
        rajz = _ImageDraw.Draw(maszk)
        rajz.ellipse((0, 0, 300, 300), fill=255)
        kimenet = _PILImage.new("RGBA", (300, 300), (0, 0, 0, 0))
        kimenet.paste(kep, (0, 0), maszk)

        buf = io.BytesIO()
        kimenet.save(buf, format="PNG")
        buf.seek(0)
        return _RLImage(buf, width=meret, height=meret)
    except Exception:
        return None


def _fejlec(story, adatok, akcent_szin, st):
    nev = adatok.get("nev", "")
    pozicio = adatok.get("pozicio", "")
    email = adatok.get("email", "")
    telefon = adatok.get("telefon", "")
    varos = adatok.get("varos", "")
    foto = adatok.get("foto_base64", "")

    story.append(HRFlowable(width="100%", thickness=3, color=akcent_szin,
                            spaceBefore=0, spaceAfter=12))

    bal = [Paragraph(nev, st["nev"]), Spacer(1, 3)]
    if pozicio:
        bal.append(Paragraph(pozicio.upper(), st["pozicio"]))
        bal.append(Spacer(1, 3))

    # Elérhetőség: vektoros ikon + szöveg, táblázatban (fix szélességek, balra)
    cellak, szelessegek = [], []
    if telefon:
        cellak += [_ikon_telefon(akcent_szin), Paragraph(telefon, st["elerheto"])]
        szelessegek += [0.42*cm, 3.0*cm]
    if email:
        cellak += [_ikon_email(akcent_szin), Paragraph(email, st["elerheto"])]
        szelessegek += [0.42*cm, 6.2*cm]
    if varos:
        cellak += [_ikon_hely(akcent_szin), Paragraph(varos, st["elerheto"])]
        szelessegek += [0.42*cm, 3.0*cm]

    if cellak:
        elerheto_tabla = Table([cellak], colWidths=szelessegek, hAlign='LEFT')
        oszlopok = len(cellak)
        stilus = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]
        for c in range(0, oszlopok, 2):
            stilus.append(('RIGHTPADDING', (c, 0), (c, 0), 7))
            if c + 1 < oszlopok:
                stilus.append(('RIGHTPADDING', (c+1, 0), (c+1, 0), 16))
        elerheto_tabla.setStyle(TableStyle(stilus))
        bal.append(elerheto_tabla)

    # Fotó (opcionális): ha van, kétoszlopos fejléc, jobbra a kép
    foto_d = _kor_foto(foto)
    if foto_d is not None:
        fej_tabla = Table([[bal, foto_d]], colWidths=[None, 2.6*cm], hAlign='LEFT')
        fej_tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(fej_tabla)
    else:
        for elem in bal:
            story.append(elem)

    story.append(HRFlowable(width="100%", thickness=0.6, color=HAIRLINE,
                            spaceBefore=10, spaceAfter=4))


def _profil_blokk(story, sorok, akcent_szin, st):
    szoveg = " ".join(s.strip().replace('**', '') for s in sorok if s.strip())
    if not szoveg:
        return
    p = Paragraph(szoveg, st["profil"])
    tabla = Table([["", p]], colWidths=[0.12*cm, 16.3*cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), akcent_szin),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(Spacer(1, 8))
    story.append(tabla)
    story.append(Spacer(1, 6))


def _szekcio_cim_flowables(szoveg, akcent_szin, st):
    ah = '#' + akcent_szin.hexval()[2:]
    return [
        Spacer(1, 4),
        Paragraph(f'<font color="{ah}">▪</font>&nbsp;&nbsp;{szoveg.upper()}', st["szekc"]),
        HRFlowable(width="100%", thickness=0.6, color=HAIRLINE, spaceBefore=2, spaceAfter=5),
    ]


def _bullet(szoveg, st):
    szoveg = szoveg.replace('**', '')
    if ':' in szoveg and len(szoveg.split(':', 1)[0]) < 40:
        elotag, maradek = szoveg.split(':', 1)
        szoveg = f"<b>{elotag.strip()}:</b>{maradek}"
    return Paragraph(f"•&nbsp;&nbsp;{szoveg}", st["bullet"])


# ── CV TÖRZS (munkablokk együtt tartással) ───────────────────

def cv_feldolgozas(story, cv_szoveg, akcent_szin, st):
    """Word-szerű, természetes elrendezés: minden munkahely és a készséglista
    EGY-EGY összetartozó blokk. Ha egy blokk nem fér ki a lap alján, EGYBEN
    átcsúszik a következő oldalra (nem törik szét, nem zsúfolódik)."""
    sorok = cv_szoveg.split('\n')
    i, n = 0, len(sorok)
    blokk = []  # az aktuális, együtt tartandó blokk (egy munkahely vagy a készséglista)

    def flush_blokk():
        if blokk:
            # KeepTogether: ha nem fér ki, az egész blokk a következő oldalra megy
            story.append(KeepTogether(list(blokk)))
            blokk.clear()

    while i < n:
        sor = sorok[i].strip()
        if not sor:
            i += 1
            continue

        if sor.startswith('## '):
            cim = sor[3:].strip()
            flush_blokk()
            if 'PROFIL' in cim.upper():
                tomb = []
                i += 1
                while i < n and not sorok[i].strip().startswith('## '):
                    s = sorok[i].strip()
                    if s and not s.startswith('---'):
                        tomb.append(s)
                    i += 1
                _profil_blokk(story, tomb, akcent_szin, st)
                continue
            else:
                # A szekciócím keepWithNext-tel rendelkezik → nem marad árván a lap alján,
                # a következő blokkjával együtt csúszik át.
                for fl in _szekcio_cim_flowables(cim, akcent_szin, st):
                    story.append(fl)
        elif sor.startswith('# ') or sor.startswith('---'):
            pass
        elif sor.startswith('**') and sor.endswith('**'):
            flush_blokk()  # új munkahely kezdődik – az előzőt egyben kiírjuk
            blokk.append(Paragraph(sor[2:-2], st["munka_cim"]))
        elif sor.startswith('*') and sor.endswith('*'):
            # cég/időszak: a munkablokkhoz tartozik
            blokk.append(Paragraph(sor[1:-1], st["munka_ceg"]))
        elif sor.startswith('- ') or sor.startswith('✓ '):
            # bullet: a jelenlegi blokkhoz (munkahely VAGY készséglista) tapad
            blokk.append(_bullet(sor[2:], st))
        else:
            flush_blokk()
            story.append(Paragraph(sor.replace('**', ''), st["normal"]))
        i += 1
    flush_blokk()


# ── MOTIVÁCIÓS LEVÉL ─────────────────────────────────────────

def level_feldolgozas(story, level_szoveg, st):
    zaro = ("üdvözlettel", "tisztelettel", "köszönettel", "üdv")
    alairas_mod = False

    bek = ParagraphStyle('LevBek', fontName=FONT_NORMAL, fontSize=10,
                         textColor=FEKETE, leading=15, spaceAfter=10, alignment=TA_JUSTIFY)
    megsz = ParagraphStyle('LevMegsz', fontName=FONT_BOLD, fontSize=10,
                           textColor=FEKETE, leading=14, spaceAfter=12)
    zaro_st = ParagraphStyle('LevZaro', fontName=FONT_NORMAL, fontSize=10,
                             textColor=FEKETE, leading=14, spaceBefore=14, spaceAfter=6, alignment=TA_LEFT)
    alairas = ParagraphStyle('LevAl', fontName=FONT_NORMAL, fontSize=10,
                             textColor=FEKETE, leading=16, spaceAfter=5, alignment=TA_LEFT)
    alairas_halv = ParagraphStyle('LevAlH', fontName=FONT_NORMAL, fontSize=9,
                                  textColor=SZURKE, leading=15, spaceAfter=4, alignment=TA_LEFT)

    for sor in level_szoveg.split('\n'):
        sor = sor.strip()
        if not sor or sor.startswith('---'):
            continue
        tiszta = sor.replace('**', '')
        also = tiszta.lower()

        if alairas_mod:
            # a záróformula után CSAK a név – telefon/email NEM (már a fejlécben van)
            if ' ' in tiszta and '@' not in tiszta and not any(c.isdigit() for c in tiszta):
                story.append(Paragraph(tiszta, alairas))
            # számot/emailt tartalmazó sorokat kihagyjuk
            continue

        if (sor.startswith('**') and sor.endswith('**')) or also.startswith('tisztelt'):
            story.append(Paragraph(tiszta, megsz))
        elif any(also.startswith(z) for z in zaro):
            story.append(Paragraph(tiszta, zaro_st))
            alairas_mod = True
        else:
            story.append(Paragraph(tiszta, bek))


# ── FŐ GENERÁLÓK ─────────────────────────────────────────────

def _epit_cv(cv_szoveg, adatok, akcent, s, margo_cm):
    """Egy CV PDF megépítése adott sűrítéssel; visszaadja (bytes, oldalszám)."""
    st = stilusok_keszites(akcent, s)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=margo_cm*cm, leftMargin=margo_cm*cm,
                            topMargin=margo_cm*cm, bottomMargin=margo_cm*cm)
    story = []
    _fejlec(story, adatok, akcent, st)
    cv_feldolgozas(story, cv_szoveg, akcent, st)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue(), doc.page


def cv_pdf_general(cv_szoveg: str, adatok: dict, szin_valasztas: str = "arany") -> bytes:
    szin = SZINEK.get(szin_valasztas, SZINEK["arany"])
    akcent = szin["akcent"]

    # TERMÉSZETES, LEVEGŐS ELRENDEZÉS (Word-szerű):
    # NINCS erőltetett egy-oldalra zsugorítás (az nyomta össze a sorokat).
    # Normál sortávolság és térköz; ami nem fér ki, az a következő oldalra folyik,
    # a blokkok (munkahelyek, készséglista) egyben maradnak.
    pdf_bytes, _ = _epit_cv(cv_szoveg, adatok, akcent, 1.0, 2.0)
    return pdf_bytes


def level_pdf_general(level_szoveg: str, adatok: dict, szin_valasztas: str = "arany") -> bytes:
    szin = SZINEK.get(szin_valasztas, SZINEK["arany"])
    akcent = szin["akcent"]
    st = stilusok_keszites(akcent)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2.2*cm, leftMargin=2.2*cm,
                            topMargin=1.7*cm, bottomMargin=1.7*cm)
    story = []
    _fejlec(story, adatok, akcent, st)
    story.append(Spacer(1, 8))
    level_feldolgozas(story, level_szoveg, st)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()