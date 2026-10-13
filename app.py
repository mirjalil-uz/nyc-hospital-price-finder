"""NYC Hospital Price Finder: compare what New York City hospitals charge.

Run:  streamlit run app.py
"""

import csv
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import altair as alt
import duckdb
import pandas as pd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT))
import i18n  # noqa: E402
from content import EVERYDAY, FAQ, FAQ_ES, PACKAGES, SPANISH_SEARCH  # noqa: E402
from i18n import tr  # noqa: E402
from paths import DATABASE  # noqa: E402

st.set_page_config(page_title="NYC Hospital Price Finder", page_icon="🏥", layout="wide")
i18n.install()

BLUE, ORANGE = "#2a78d6", "#eb6834"
ASSETS = ROOT / "assets"

# Look and feel: white cards with soft shadows, gentle entrance and hover motion.
STYLE = """
<style>
  @keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
  .block-container { padding-top: 3.6rem; }
  .nav { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
         margin-bottom: 0.4rem; animation: rise 0.5s ease both; }
  .nav .logo { display: flex; align-items: center; gap: 0.6rem; font-weight: 700; font-size: 1.15rem; color: #0d366b; }
  .nav .cross { position: relative; width: 30px; height: 30px; border-radius: 9px; background: #2a78d6; flex: none; }
  .nav .cross::before, .nav .cross::after { content: ""; position: absolute; background: #ffffff; border-radius: 2px; }
  .nav .cross::before { left: 13px; top: 6px; width: 4px; height: 18px; }
  .nav .cross::after { left: 6px; top: 13px; width: 18px; height: 4px; }
  .nav .pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .nav .pill { background: #e6f4ee; color: #0b6b47; border-radius: 999px; padding: 0.25rem 0.8rem; font-size: 0.82rem;
               font-weight: 600; }
  .nav .pill.blue { background: #e3eefc; color: #184f95; }
  [data-testid="stMetric"] { background: #ffffff; border: 1px solid #e3ebf6; border-left: 5px solid #2a78d6;
        border-radius: 14px; padding: 14px 18px; box-shadow: 0 2px 10px rgba(13, 54, 107, 0.06);
        animation: rise 0.5s ease both; }
  /* Price ranges such as "$400 – $2,185" must never be cut off with an ellipsis. */
  [data-testid="stMetricValue"], [data-testid="stMetricValue"] * { white-space: normal !important;
        overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere; }
  [data-testid="stMetricValue"] { font-size: 1.65rem; line-height: 1.25; }
  .st-key-hospital-card, .st-key-results, .st-key-search-step { scroll-margin-top: 4.5rem; }
  .st-key-language { display: flex; justify-content: flex-end; margin-bottom: -0.6rem; }
  .st-key-language [role="radiogroup"] { background: #ffffff; border: 1px solid #c6d4e6; border-radius: 999px;
        padding: 0.15rem 0.9rem; }
  /* Each section is its own coloured panel on a grey page, so it is clear where one ends and the next begins. */
  [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: #e9eef5; }
  .st-key-search-step, .st-key-results, .st-key-list-section, .st-key-faq-section, .st-key-how-section,
  .st-key-stats { border-radius: 18px; padding: 1.3rem 1.5rem 1.5rem; box-shadow: 0 2px 10px rgba(13, 54, 107, 0.06); }
  .st-key-search-step { background: #e6f6ef; border: 1px solid #b7e2cf; border-left: 8px solid #1baf7a; }
  .st-key-results { background: #e3eefc; border: 1px solid #bcd6f6; border-left: 8px solid #2a78d6; }
  .st-key-list-section { background: #ffffff; border: 1px solid #d5dee9; border-left: 8px solid #4a3aa7; }
  .st-key-hospital-card { background: #fff6e6 !important; border: 1px solid #f3d9a8 !important;
        border-left: 8px solid #eb6834 !important; }
  .st-key-faq-section { background: #f1edfb; border: 1px solid #d6cdf2; border-left: 8px solid #4a3aa7; }
  .st-key-how-section { background: #fff6e6; border: 1px solid #f3d9a8; border-left: 8px solid #eda100; }
  .st-key-stats { background: #ffffff; border: 1px solid #d5dee9; }
  .st-key-search-step h3 { color: #0b6b47; }
  .st-key-results h2 { color: #0d366b; }
  .st-key-list-section h3, .st-key-faq-section h3 { color: #3a2d8a; }
  .st-key-hospital-card h3 { color: #a8431a; }
  /* The recommendation is the answer to the person's question, so it is the most prominent thing in the results. */
  .st-key-recommendation { background: linear-gradient(135deg, #fff1bf 0%, #ffffff 75%); border: 2px solid #eda100;
        border-left: 10px solid #eda100; border-radius: 18px; padding: 1.2rem 1.5rem 1.4rem;
        box-shadow: 0 8px 22px rgba(237, 161, 0, 0.22); margin-bottom: 0.6rem; }
  .st-key-recommendation h3 { font-size: 1.9rem !important; color: #0d366b !important; }
  /* Step 1 must be impossible to miss: a framed, softly glowing card with a large dropdown. */
  @keyframes glow { 0%, 100% { box-shadow: 0 8px 24px rgba(42, 120, 214, 0.18); }
                    50% { box-shadow: 0 8px 34px rgba(42, 120, 214, 0.45); } }
  .st-key-insurance-todo { background: linear-gradient(135deg, #2a78d6 0%, #184f95 100%); border-radius: 18px;
        padding: 1.4rem 1.6rem 1.6rem; animation: glow 2.4s ease-in-out infinite; }
  .st-key-insurance-todo h3 { font-size: 1.8rem !important; color: #ffffff !important; }
  .st-key-insurance-todo p { color: #e6f0ff; font-size: 1.05rem; }
  /* The dropdown: white with a dark frame on the blue card, tall, with dark placeholder text. */
  .st-key-insurance-todo [data-testid="stSelectbox"] div:has(> input) { min-height: 3.8rem; background: #ffffff;
        border: 3px solid #ffd27a !important; border-radius: 14px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18); }
  .st-key-insurance-todo [data-testid="stSelectbox"] div:has(> input) * { font-size: 1.15rem; color: #0d1b2a;
        opacity: 1; }
  .st-key-insurance-todo .stButton > button { background: #ffffff; border: 0; font-weight: 600; min-height: 3rem;
        color: #0d366b; }
  .st-key-insurance-todo .stButton > button p { color: #0d366b; font-size: 1rem; }
  /* Every other input gets a visible frame too, so fields never blend into the page. */
  [data-testid="stSelectbox"] div:has(> input), [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stTextInput"] div:has(> input), [data-testid="stNumberInput"] div:has(> input) {
        border: 1.5px solid #9db8d9; }
  [data-testid="stTextInput"] div:has(> input):focus-within, [data-testid="stSelectbox"] div:has(> input):focus-within {
        border-color: #2a78d6; }
  .st-key-insurance-done { background: #f0f9f4; border: 1px solid #b9e3cd; border-radius: 18px;
        padding: 1rem 1.5rem 1.2rem; }
  [data-testid="stImage"] img { border-radius: 18px; }
  [data-testid="stImage"] { animation: rise 0.6s ease both; }
  .stButton > button { transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease; }
  .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(42, 120, 214, 0.18);
        border-color: #2a78d6; }
  [data-testid="stAlert"] { animation: rise 0.5s ease both; }
  /* Phones: a taller banner with larger text, two tiles per row, tighter margins. */
  .st-key-hero-mobile, .st-key-chart-mobile, .st-key-list-mobile { display: none; }
  @media (max-width: 640px) {
    .st-key-hero-desktop, .st-key-chart-desktop, .st-key-list-desktop { display: none; }
    .st-key-hero-mobile, .st-key-chart-mobile, .st-key-list-mobile { display: block; }
    .block-container { padding: 4.2rem 0.9rem 2rem; }
    .nav .pills { display: none; }
    .st-key-bundles [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.5rem; }
    .st-key-bundles [data-testid="stColumn"] { min-width: 100% !important; }
    .st-key-tiles [data-testid="stHorizontalBlock"], .st-key-stats [data-testid="stHorizontalBlock"],
    .st-key-insurance-todo [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap; gap: 0.5rem; }
    .st-key-tiles [data-testid="stColumn"], .st-key-stats [data-testid="stColumn"],
    .st-key-insurance-todo [data-testid="stColumn"] {
        min-width: calc(50% - 0.25rem) !important; width: calc(50% - 0.25rem) !important;
        flex: 0 0 calc(50% - 0.25rem) !important; }
    .st-key-tiles .stButton > button { min-height: 3.6rem; padding: 0.3rem 0.4rem; }
    .st-key-tiles .stButton > button * { white-space: normal !important; overflow: visible !important;
        text-overflow: clip !important; line-height: 1.2; }
    [data-testid="stMetric"] { padding: 10px 12px; }
    .st-key-search-step, .st-key-results, .st-key-list-section, .st-key-faq-section, .st-key-how-section,
    .st-key-stats, .st-key-insurance-todo, .st-key-insurance-done { padding: 0.9rem 0.8rem 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.3rem; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.2rem !important; }
  }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
"""
NAV = """
<div class="nav">
  <div class="logo"><span class="cross"></span>NYC Hospital Price Finder</div>
  <div class="pills">
    <span class="pill">{official}</span>
    <span class="pill blue">{free}</span>
  </div>
</div>
"""
# The wording inside the banner pictures, for the Spanish version.
HERO_WORDS = [
    ("Know the price", "Conozca el precio"),
    ("before you go", "antes de ir"),
    ("Compare what New York City hospitals really charge", "Compare lo que cobran los hospitales de Nueva York"),
    ("for the same care, using their own published prices.", "por la misma atención, con sus precios publicados."),
    ("Compare what New York City hospitals", "Compare lo que cobran los hospitales"),
    ("really charge for the same care.", "de Nueva York por la misma atención."),
]

# Common services offered as one-click tiles: (icon, label, code type, code).
POPULAR = [
    ("🧠", "MRI of the brain", "CPT/HCPCS", "70551"),
    ("🩻", "Chest X-ray", "CPT/HCPCS", "71046"),
    ("🖥️", "CT scan of the abdomen", "CPT/HCPCS", "74177"),
    ("🦵", "MRI of the knee", "CPT/HCPCS", "73721"),
    ("🩸", "Blood test: metabolic panel", "CPT/HCPCS", "80053"),
    ("🧪", "Complete blood count", "CPT/HCPCS", "85025"),
    ("🫀", "Heart tracing (EKG)", "CPT/HCPCS", "93005"),
    ("🎗️", "Screening mammogram", "CPT/HCPCS", "77067"),
    ("🚑", "Emergency room visit", "CPT/HCPCS", "99283"),
    ("🔬", "Colonoscopy", "CPT/HCPCS", "45378"),
    ("👶", "Vaginal delivery", "MS-DRG", "807"),
    ("🦴", "Knee or hip replacement", "MS-DRG", "470"),
]
PACKAGE = "PACKAGE"  # the "code type" of a bundle of several services
BUNDLES = {key: (icon, name, about, parts) for key, icon, name, about, parts in PACKAGES}
FRIENDLY = {(code_type, code): (icon, label) for icon, label, code_type, code in POPULAR}

SETTINGS = {
    "Any type of visit": ("outpatient", "inpatient", "both", "not stated"),
    "Outpatient (no overnight stay)": ("outpatient", "both", "not stated"),
    "Inpatient (admitted to hospital)": ("inpatient", "both", "not stated"),
}
SORTS = {
    "Patient rating (highest first)": (["patient_stars", "patient_recommend_pct", "cash_compare"], [False, False, True]),
    "Cash price (lowest first)": (["cash_compare", "insurer_typical", "list_low"], [True, True, True]),
    "Typical insurer price (lowest first)": (["insurer_typical", "cash_compare", "list_low"], [True, True, True]),
}
DISTANCES = {"Any distance": None, "Within 2 miles": 2, "Within 5 miles": 5, "Within 10 miles": 10}
RATINGS = {"Any rating": None, "2 stars or more": 2, "3 stars or more": 3, "4 stars or more": 4}
MOBILE_ROWS = 20  # hospital cards shown in the phone list
UNUSUALLY_LOW = 0.1  # a price under this fraction of the middle price is flagged
WIDE_RANGE = 4  # a hospital whose highest cash line is over this many times its lowest is flagged
with (ROOT / "data" / "zip_centroids.csv").open(encoding="utf-8") as f:
    ZIP_CENTRES = {r["zip"]: (float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(f)}
ACRONYMS = {"mri", "mra", "ct", "ekg", "ecg", "er", "iv", "hiv", "cbc", "tsh", "psa", "us", "pet", "ob", "dna", "ii", "iii"}



@st.cache_resource
def connect():
    return duckdb.connect(str(DATABASE), read_only=True)


@st.cache_data(show_spinner=False)
def query(sql, params=()):
    """Run a query; `params` is a list for "?" marks or a dict for $named values."""
    return connect().cursor().execute(sql, params if isinstance(params, dict) else list(params)).df()


# ------------------------------------------------------------------- helpers


def plain_name(description):
    """Hospital wording such as 'MRI BRAIN STEM W/O DYE' in a calmer, readable form."""
    text = re.sub(r"\bw/o\b", "without", str(description), flags=re.I)
    text = re.sub(r"\bw/", "with ", text, flags=re.I)
    words = [w.upper() if w.lower().strip(",;()") in ACRONYMS else w.lower() for w in text.split()]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def service_title(code_type, code):
    if code_type == PACKAGE:
        icon, name, _, _ = BUNDLES[code]
        return f"{icon} {tr(name)}"
    if (code_type, code) in FRIENDLY:
        icon, label = FRIENDLY[(code_type, code)]
        return f"{icon} {tr(label)}"
    info = query("SELECT description FROM procedures WHERE code_type = ? AND code = ?", [code_type, code])
    return plain_name(info.description[0]) if len(info) else "Service"


def stars(rating):
    if pd.isna(rating):
        return "not rated"
    return "★" * int(rating) + "☆" * (5 - int(rating))


def money(value):
    return "not published" if pd.isna(value) else f"${value:,.0f}"


def md(text):
    """Escape dollar signs, which Markdown would otherwise read as the start of a formula."""
    return text.replace("$", "\\$")


def money_range(low, high):
    if pd.isna(low):
        return "not published"
    if pd.isna(high) or abs(high - low) < 0.005:
        return f"${low:,.0f}"
    return f"${low:,.0f} – ${high:,.0f}"


def tidy(df):
    """Drop columns the hospital left entirely empty and blank out missing text."""
    df = df.dropna(axis="columns", how="all")
    text = df.select_dtypes(include=["object", "string"]).columns
    return df.assign(**{c: df[c].fillna("") for c in text})


def payment_details(row):
    """One readable sentence for the ways a plan can pay other than a fixed price."""
    parts = []
    if pd.notna(row.percent_of_charges):
        parts.append(f"{row.percent_of_charges:g}% of charges")
    if pd.notna(row.estimated_amount):
        parts.append(f"estimated ${row.estimated_amount:,.2f}")
    if pd.notna(row.formula) and row.formula:
        parts.append(str(row.formula))
    return "; ".join(parts) or None


def miles(a, b):
    """Straight-line distance in miles between two (latitude, longitude) points."""
    if a is None or b is None or any(pd.isna(v) for v in (*a, *b)):
        return float("nan")
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def far_below_the_rest(prices):
    """True for prices under a tenth of the middle price, when at least five hospitals publish one."""
    if prices.notna().sum() < 5:
        return pd.Series(False, index=prices.index)
    return (prices < prices.median() * UNUSUALLY_LOW).fillna(False)


# Hospitals that serve one kind of patient. They stay in the list, but are not recommended to
# everyone automatically: a children's hospital is the wrong suggestion for most adults.
SPECIALISED = ("Children", "Behavioral", "Zucker Hillside", "Calvary", "Henry J. Carter", "Eye and Ear",
               "Memorial Sloan Kettering")


def rank_options(results, with_insurance, with_distance):
    """Hospitals in order of recommendation, one row per price list.

    Each hospital is placed among the others on three things: what the person would pay, how
    patients rate it and how far away it is. Its place on each (0 = worst, 1 = best) is blended:
    cost counts for half, rating for three tenths and distance for two tenths, or cost for six
    tenths and rating for four when no ZIP code was given. Places are used instead of raw numbers
    so that one extremely expensive hospital cannot make every other price look alike.
    Prices flagged as unusually low are left out, and so are hospitals with no price to compare.
    Hospitals for one kind of patient (children's, psychiatric, cancer, long-term care) are left out
    whenever a general hospital is available.
    """
    pool = results.copy()
    if with_insurance:
        pool["cost"] = pool.you_pay.where(pool.covered & ~pool.insurer_odd)
    else:
        pool["cost"] = pool.cash_compare.where(~pool.cash_odd)
    pool = pool.dropna(subset=["cost"])
    general = pool[~pool.hospital.str.contains("|".join(SPECIALISED))]
    if not general.empty:
        pool = general.copy()
    if pool.empty:
        return pool
    pool["cost_place"] = 1 - pool.cost.rank(pct=True, method="min") + 1 / len(pool)
    # A hospital with no patient rating is treated as average, neither rewarded nor punished.
    pool["rating_place"] = pool.patient_recommend_pct.rank(pct=True).fillna(0.5)
    if with_distance:
        pool["distance_place"] = 1 - pool.miles.rank(pct=True, method="min") + 1 / len(pool)
        pool["score"] = 0.5 * pool.cost_place + 0.3 * pool.rating_place + 0.2 * pool.distance_place
    else:
        pool["score"] = 0.6 * pool.cost_place + 0.4 * pool.rating_place
    pool = pool.sort_values(["score", "cost"], ascending=[False, True])
    return pool.drop_duplicates("file_id")


def reasons_for(row, pool, cost_words):
    """Short plain reasons why a hospital ranks where it does."""
    reasons = []
    middle = pool.cost.median()
    if row.cost <= pool.cost.min():
        reasons.append(f"{cost_words} is the lowest of the {len(pool)} hospitals compared: {money(row.cost)}")
    elif row.cost < middle:
        reasons.append(f"{cost_words} is {money(middle - row.cost)} below the middle of the hospitals compared")
    else:
        reasons.append(f"{cost_words} is {money(row.cost)}, close to or above the middle ({money(middle)})")
    if pd.notna(row.patient_stars):
        reasons.append(f"Patients rate it {int(row.patient_stars)} of 5 stars, and "
                       f"{int(row.patient_recommend_pct)}% would definitely recommend it")
    else:
        reasons.append("Medicare has no patient rating for it")
    if pd.notna(row.miles):
        reasons.append(f"It is about {row.miles:.1f} miles from you")
    return reasons


def is_old(file_date):
    """True when a hospital's price file is more than a year old."""
    return pd.notna(file_date) and file_date.date() < date.today() - timedelta(days=365)


def estimate_owed(plan_price, deductible, coinsurance_pct, copay):
    """Split a plan's price into what the patient and the plan each pay."""
    toward_deductible = min(plan_price, deductible)
    share = (plan_price - toward_deductible) * coinsurance_pct / 100
    return {
        "deductible": toward_deductible,
        "coinsurance": share,
        "copay": copay,
        "total": toward_deductible + share + copay,
        "plan_pays": max(plan_price - toward_deductible - share, 0),
    }


def hero(file_name):
    """The banner picture; its wording is swapped for Spanish when that language is chosen."""
    picture = (ASSETS / file_name).read_text(encoding="utf-8")
    if i18n.spanish_on():
        for english, spanish in HERO_WORDS:
            picture = picture.replace(f">{english}<", f">{spanish}<")
    st.image(picture, width="stretch")


def faq_section():
    with st.container(key="faq-section"):
        st.subheader("❓ Frequently asked questions")
        for question, answer in (FAQ_ES if i18n.spanish_on() else FAQ):
            with st.expander(question):
                st.write(md(answer))


def pulse_divider():
    """An animated heartbeat line between sections."""
    st.image(str(ASSETS / "pulse.svg"), width="stretch")


def choose_hospital(name):
    st.session_state.hospital = name
    st.session_state.scroll_target = "hospital-card"


def scroll_if_asked():
    """Move the page to the next step when a choice has just been made.

    Each step's result appears further down the page, so without this a choice can look as if it
    did nothing. The target is the key of a container, which Streamlit exposes as a CSS class.
    """
    target = st.session_state.pop("scroll_target", None)
    if not target:
        return
    st.session_state.scrolls = st.session_state.get("scrolls", 0) + 1
    components.html(
        f"""<script>
        // scroll {st.session_state.scrolls}: a changing number makes the browser run this again each time
        const step = window.parent.document.querySelector(".st-key-{target}");
        if (step) step.scrollIntoView({{behavior: "smooth", block: "start"}});
        </script>""",
        height=0,
    )


def choose_insurance(name=None):
    """Record the insurance (from a one-tap button, or already set by the dropdown) and go to step 2."""
    if name:
        st.session_state.insurance = name
    st.session_state.scroll_target = "search-step"


def pick_service(code_type, code):
    st.session_state.picked = (code_type, code)
    st.session_state.scroll_target = "results"
    st.session_state.search = ""


# ------------------------------------------------------------------- queries


def search_services(text):
    """Services matching the search, as {label: (code type, code)}; everyday words are tried first."""
    found = {}
    lowered = text.lower()
    if i18n.spanish_on():
        for spanish, english in SPANISH_SEARCH:
            lowered = lowered.replace(spanish, english)
        text = lowered
    for key, (icon, name, about, parts) in BUNDLES.items():
        if any(len(word) > 2 and word in f"{name} {about}".lower() for word in lowered.split()):
            found[f"{icon} {name}  ·  package of {len(parts)} services"] = (PACKAGE, key)
    known = query("SELECT code_type, code, description, hospitals FROM procedures")
    known = {(r.code_type, r.code): r for r in known.itertuples()}
    for name, triggers, codes in EVERYDAY:
        if any(t in lowered for t in triggers) or lowered.strip() in name.lower():
            for key in codes:
                if key in known:
                    r = known[key]
                    detail = "" if len(codes) == 1 else f": {plain_name(r.description)}"
                    found[f"{name}{detail}  ·  {r.code_type} {r.code}  ·  {r.hospitals} hospitals"] = key
    words = [w for w in text.split() if w]
    if words:
        where = " AND ".join("(description ILIKE ? OR code = ?)" for _ in words)
        params = [p for w in words for p in (f"%{w}%", w.upper())]
        rows = query(
            f"""SELECT code_type, code, description, hospitals FROM procedures
                WHERE {where} ORDER BY hospitals DESC, code LIMIT 300""",
            params,
        )
        for r in rows.itertuples():
            if (r.code_type, r.code) not in found.values():
                found[f"{plain_name(r.description)}  ·  {r.code_type} {r.code}  ·  {r.hospitals} hospitals"] = (
                    r.code_type, r.code)
    return found


def main_line_insurer_prices(file_id, code_type, code, settings, payer, smallest_full_price, plan_type=None):
    """Lowest, typical and highest insurer price at one hospital, leaving out partial-service lines.

    A line counts as partial when its own cash or list price is known and below `smallest_full_price`,
    or when insurers pay far less on it than on the hospital's best-paid line for the same code (some
    hospitals give the doctor's-fee line no price of its own, only insurer rates).
    Lines without a billing modifier are preferred, as in the pipeline.
    """
    marks = ", ".join(f"$s{n}" for n in range(len(settings)))
    return query(
        f"""
        WITH lines AS (
            SELECT i.item_id, i.modifiers IS NULL AS plain, coalesce(i.cash_price, i.gross_charge) AS own_price
            FROM codes c JOIN items i USING (file_id, item_id)
            WHERE c.file_id = $file AND c.code_type = $code_type AND c.code = $code
              AND coalesce(i.setting, 'not stated') IN ({marks})
        ),
        candidates AS (
            SELECT item_id FROM lines
            WHERE (plain OR NOT (SELECT bool_or(plain) FROM lines))
              AND (own_price IS NULL OR own_price >= $smallest)
        ),
        paid AS (
            SELECT item_id, negotiated_dollar FROM rates
            WHERE file_id = $file AND item_id IN (SELECT item_id FROM candidates)
              AND negotiated_dollar IS NOT NULL AND ($payer IS NULL OR payer_group = $payer)
              AND ($plan IS NULL OR plan_type = $plan)
        ),
        line_level AS (SELECT item_id, median(negotiated_dollar) AS typical FROM paid GROUP BY item_id),
        full_service AS (
            SELECT item_id FROM line_level WHERE typical >= (SELECT max(typical) FROM line_level) / {WIDE_RANGE}
        )
        SELECT min(negotiated_dollar) AS low, median(negotiated_dollar) AS typical, max(negotiated_dollar) AS high
        FROM paid WHERE item_id IN (SELECT item_id FROM full_service)
        """,
        {"file": file_id, "code_type": code_type, "code": code, "smallest": float(smallest_full_price),
         "payer": payer, "plan": plan_type, **{f"s{n}": v for n, v in enumerate(settings)}},
    ).iloc[0]


def compare(code_type, code, settings, boroughs, payer, plan_type=None):
    marks = ", ".join("?" for _ in settings)
    if payer:
        negotiated = f"""
            LEFT JOIN (SELECT file_id, min(negotiated_min) AS lo, max(negotiated_max) AS hi,
                              median(negotiated_median) AS mid
                       FROM payer_prices
                       WHERE code_type = ? AND code = ? AND setting IN ({marks}) AND payer_group = ?
                         AND (?::VARCHAR IS NULL OR plan_type = ?)
                       GROUP BY file_id) n USING (file_id)
        """
        negotiated_params = [code_type, code, *settings, payer, plan_type, plan_type]
        columns = "any_value(n.lo) AS insurer_low, any_value(n.mid) AS insurer_typical, any_value(n.hi) AS insurer_high"
    else:
        negotiated = ""
        negotiated_params = []
        columns = """min(p.negotiated_min) AS insurer_low,
                     arg_max(p.negotiated_median, p.plans_with_price) AS insurer_typical,
                     max(p.negotiated_max) AS insurer_high"""
    df = query(
        f"""
        SELECT h.hospital, h.borough, h.system, h.address, h.phone, h.latitude, h.longitude, h.patient_stars,
               h.patient_recommend_pct, h.patient_surveys, h.medicare_stars, h.medicare_rated_as,
               min(p.cash_min) AS cash_low, max(p.cash_max) AS cash_high,
               min(p.gross_min) AS list_low, max(p.gross_max) AS list_high,
               {columns},
               any_value(f.last_updated) AS file_date, h.file_id
        FROM procedure_prices p
        JOIN hospitals h USING (file_id)
        JOIN files f USING (file_id)
        {negotiated}
        WHERE p.code_type = ? AND p.code = ? AND p.setting IN ({marks})
        GROUP BY ALL
        """,
        [*negotiated_params, code_type, code, *settings],
    )
    df["file_date"] = pd.to_datetime(df.file_date)
    # Some hospitals put a part of the service (such as the doctor's fee) under the same code as the
    # whole service. Comparing on the higher line avoids promoting a price that covers only a part.
    df["cash_wide"] = df.cash_high > WIDE_RANGE * df.cash_low
    df["cash_compare"] = df.cash_low.where(~df.cash_wide, df.cash_high)
    # The same partial-service lines would drag the insurer prices down, so for those hospitals
    # the insurer prices are recalculated from the full-service lines only.
    for file_id, group in df[df.cash_wide].groupby("file_id"):
        main = main_line_insurer_prices(file_id, code_type, code, settings, payer,
                                        group.cash_high.iloc[0] / WIDE_RANGE, plan_type)
        if pd.notna(main.typical):
            df.loc[df.file_id == file_id, ["insurer_low", "insurer_typical", "insurer_high"]] = [
                main.low, main.typical, main.high]
    return df[df.borough.isin(boroughs)] if boroughs else df


SUMMED = ["cash_low", "cash_high", "cash_compare", "list_low", "list_high",
          "insurer_low", "insurer_typical", "insurer_high"]


def compare_package(key, settings, boroughs, payer, plan_type=None):
    """Hospitals that price every part of a package, with each price column added up across the parts.

    A total is left blank when any part has no price of that kind, so a total is never a part-total.
    """
    parts = BUNDLES[key][3]
    frames = [compare(t, c, settings, (), payer, plan_type).set_index("hospital") for t, c, _ in parts]
    everywhere = sorted(set.intersection(*(set(f.index) for f in frames)))
    total = frames[0].loc[everywhere].copy()
    for column in SUMMED:
        total[column] = sum(f.loc[everywhere, column] for f in frames)
    total["cash_wide"] = pd.concat([f.loc[everywhere, "cash_wide"] for f in frames], axis=1).any(axis=1)
    total = total.reset_index()
    return total[total.borough.isin(boroughs)] if boroughs else total


def package_breakdown(key, hospital, settings, payer, plan_type=None):
    """One row per part of a package at one hospital."""
    rows = []
    for code_type, code, name in BUNDLES[key][3]:
        frame = compare(code_type, code, settings, (), payer, plan_type)
        match = frame[frame.hospital == hospital]
        price = match.iloc[0] if len(match) else None
        rows.append({
            "Service": name,
            "Billing code": code,
            "Cash price": None if price is None else price.cash_compare,
            "Insurer price": None if price is None else price.insurer_typical,
            "List price": None if price is None else price.list_high,
        })
    return pd.DataFrame(rows)


def line_items(file_id, code_type, code):
    return query(
        """SELECT i.description, i.setting, i.modifiers, i.gross_charge AS list_price, i.cash_price
           FROM codes c JOIN items i USING (file_id, item_id)
           WHERE c.file_id = ? AND c.code_type = ? AND c.code = ?
           ORDER BY i.modifiers NULLS FIRST, i.description""",
        [file_id, code_type, code],
    )


def plan_rates(file_id, code_type, code):
    return query(
        """SELECT r.payer_name AS insurer, r.plan_name AS plan, r.plan_type, i.setting, i.modifiers,
                  r.negotiated_dollar AS price, r.negotiated_percentage AS percent_of_charges,
                  r.estimated_amount, r.methodology, r.negotiated_algorithm AS formula
           FROM codes c JOIN items i USING (file_id, item_id) JOIN rates r USING (file_id, item_id)
           WHERE c.file_id = ? AND c.code_type = ? AND c.code = ?
           ORDER BY insurer, plan, price""",
        [file_id, code_type, code],
    )


# -------------------------------------------------------------------- pieces


def pick_card(column, badge, row, headline):
    """A highlighted hospital with a button that opens its details."""
    with column.container(border=True):
        st.caption(badge)
        st.markdown(f"**{row.hospital}**")
        st.markdown(f"### {md(headline)}")
        where = f"{row.miles:.1f} mi" if pd.notna(row.get("miles", float("nan"))) else row.borough
        st.write(f"{stars(row.patient_stars)} · {where}")
        st.button("See details", key=f"pick-{badge}", on_click=choose_hospital, args=(row.hospital,),
                  width="stretch")


def price_chart(results, label_width=340):
    """Horizontal bars of the lowest published cash price, cheapest at the top."""
    data = results.dropna(subset=["cash_compare"]).assign(
        rating=lambda d: [stars(s) for s in d.patient_stars],
        price=lambda d: [money_range(a, b) for a, b in zip(d.cash_low, d.cash_high)],
    )
    if data.empty:
        st.info("No hospital publishes a cash price for this service.")
        return
    chart = (
        alt.Chart(data)
        .mark_bar(color=BLUE, cornerRadiusEnd=4)
        .encode(
            x=alt.X("cash_compare:Q", title=tr("Published cash price"),
                    axis=alt.Axis(format="$,.0f", tickCount=6, gridColor="#e1e0d9", domain=False, ticks=False)),
            y=alt.Y("label:N", sort="x", title=None,
                    axis=alt.Axis(labelLimit=label_width, domainColor="#c3c2b7", ticks=False)),
            tooltip=[alt.Tooltip("label:N", title="Hospital"), alt.Tooltip("price:N", title="Cash price"),
                     alt.Tooltip("borough:N", title="Borough"), alt.Tooltip("rating:N", title="Patient rating")],
        )
        .properties(height=max(160, 24 * len(data)))
        .configure_view(strokeWidth=0)
        .configure_scale(bandPaddingInner=0.25)
    )
    st.altair_chart(chart, width="stretch")
    st.caption("Hover over a bar for details. Hospitals that publish no cash price are left out.")


def hospital_map(results, selected):
    """Every hospital with a price as a dot; the selected one is larger and orange."""
    data = results.dropna(subset=["latitude", "longitude"]).assign(
        price=lambda d: [money_range(a, b) for a, b in zip(d.cash_low, d.cash_high)],
        rating=lambda d: [stars(s) for s in d.patient_stars],
        chosen=lambda d: d.hospital == selected,
    )
    columns = ["hospital", "address", "phone", "latitude", "longitude", "price", "rating"]

    def dots(layer_id, rows, color, pixels):
        # A tiny real-world radius clamped to a fixed pixel size keeps dots the same size at every zoom.
        return pdk.Layer(
            "ScatterplotLayer", data=rows[columns], id=layer_id, get_position="[longitude, latitude]",
            get_fill_color=color, get_radius=1, radius_min_pixels=pixels, radius_max_pixels=pixels,
            stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True,
        )

    # The selected hospital is drawn last so it sits on top of its neighbours.
    layers = [
        dots("hospitals", data[~data.chosen], [42, 120, 214], 7),
        dots("selected", data[data.chosen], [235, 104, 52], 12),
    ]
    deck = pdk.Deck(
        layers=layers, map_style="light",
        initial_view_state=pdk.ViewState(latitude=40.73, longitude=-73.93, zoom=9.6),
        tooltip={"html": "<b>{hospital}</b><br/>Cash price: {price}<br/>Patient rating: {rating}<br/>{address}<br/>{phone}"},
    )
    event = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", height=520, key="hospital_map")
    st.caption("Each dot is a hospital with a price for this service. Click a dot to open its details; "
               "the orange dot is the hospital shown below.")
    picked_dots = (event.selection.objects or {}) if event else {}
    objects = picked_dots.get("hospitals", []) + picked_dots.get("selected", [])
    return objects[0]["hospital"] if objects else None


# ---------------------------------------------------------------------- page

if not DATABASE.exists():
    st.error(f"Database not found at {DATABASE}. Run the pipeline scripts first (see README).")
    st.stop()

st.html(STYLE)
# Language comes first, because every later line of text depends on it. A shared link can carry it.
if "lang" not in st.session_state:
    st.session_state.lang = i18n.SPANISH if st.query_params.get("lang") == "es" else "English"
with st.container(key="language"):
    st.radio("Language / Idioma", ["English", i18n.SPANISH], horizontal=True, key="lang",
             label_visibility="collapsed")
if i18n.spanish_on():
    st.query_params["lang"] = "es"
else:
    st.query_params.pop("lang", None)
st.html(NAV.format(official=tr("Official hospital price files"), free=tr("Free to use, no sign-up")))
with st.container(key="hero-desktop"):
    hero("hero.svg")
with st.container(key="hero-mobile"):
    hero("hero-mobile.svg")

st.session_state.setdefault("search", "")
NO_INSURANCE = "I don't have insurance (I will pay myself)"
NOT_LISTED = "My insurance is not listed"
ANY_PLAN = "Not sure (use all of this insurer's plans)"
payers = query(
    """SELECT payer_group FROM payer_prices GROUP BY 1
       HAVING count(DISTINCT file_id) >= 3 ORDER BY count(DISTINCT file_id) DESC, 1"""
).payer_group.tolist()
insurance_choices = [NO_INSURANCE, *payers, NOT_LISTED]

# A shared link carries the insurance, the service and the hospital in the page address.
if "insurance" not in st.session_state and st.query_params.get("insurance") in insurance_choices:
    st.session_state.insurance = st.query_params["insurance"]
if "picked" not in st.session_state and "service" in st.query_params:
    linked_type, _, linked_code = st.query_params["service"].partition(" ")
    known_service = (linked_code in BUNDLES if linked_type == PACKAGE else
                     len(query("SELECT 1 FROM procedures WHERE code_type = ? AND code = ?", [linked_type, linked_code])))
    if known_service:
        st.session_state.picked = (linked_type, linked_code)
        if "hospital" in st.query_params:
            st.session_state.hospital = st.query_params["hospital"]


def landing_sections():
    """What a first-time visitor sees under the steps: the numbers, how it works and the questions."""
    totals = query(
        """SELECT (SELECT count(*) FROM hospitals WHERE has_prices) AS loaded,
                  (SELECT count(*) FROM hospitals) AS hospitals,
                  (SELECT count(*) FROM rates) AS prices,
                  (SELECT count(*) FROM procedures) AS services"""
    ).iloc[0]
    stat = st.container(key="stats").columns(4)
    stat[0].metric("Hospitals", f"{int(totals.loaded)} of {int(totals.hospitals)}")
    stat[1].metric("Insurance prices", f"{totals.prices / 1e6:.0f} million")
    stat[2].metric("Services to search", f"{int(totals.services):,}")
    stat[3].metric("Boroughs covered", "All 5")

    with st.container(key="how-section"):
        st.subheader("🧭 How it works")
        steps = st.columns(3)
        for column, picture, title, body in (
            (steps[0], "step-search.svg", "1. Choose your insurance, then search",
             "Pick your insurance provider, then type what you need in everyday words, such as a broken arm or a "
             "blood test, or tap a popular service."),
            (steps[1], "step-compare.svg", "2. Compare hospitals",
             "See the full price, what your insurance pays and what you pay, with patient ratings and distance, "
             "in a list, on a chart or on a map."),
            (steps[2], "step-go.svg", "3. Call or get directions",
             "Open any hospital for its phone number, address and directions before you go."),
        ):
            with column.container(border=True):
                st.image(str(ASSETS / picture), width="stretch")
                st.markdown(f"**{title}**")
                st.write(body)
        st.caption(
            "Hospitals in the United States must publish their prices, but the files are huge and hard to read. "
            "This app loads the official file from each New York City hospital and puts the prices side by side."
        )
    faq_section()


# Step 1 is a highlighted card until it is answered, then a quiet confirmation.
answered = st.session_state.get("insurance") is not None
with st.container(key="insurance-done" if answered else "insurance-todo"):
    if answered:
        st.subheader("✅ Step 1: Your insurance")
    else:
        st.subheader("💳 Step 1: Choose your insurance")
        st.write("Prices depend on your insurance, so this comes first. Pick from the list, or tap a common choice below.")
    insurance = st.selectbox(
        "Your insurance", insurance_choices, index=None, key="insurance",
        placeholder="Choose your insurance provider, or say that you have none",
        label_visibility="collapsed" if not answered else "visible",
        on_change=choose_insurance,
    )
    if insurance is None:
        quick = st.columns(4)
        for n, name in enumerate([*payers[:7], NO_INSURANCE]):
            quick[n % 4].button("I have no insurance" if name == NO_INSURANCE else name, key=f"quick-{name}",
                                width="stretch", on_click=choose_insurance, args=(name,))
if insurance is None:
    st.info("👆 Start by choosing your insurance, so that the prices you see are the ones that apply to you.")
    landing_sections()
    st.stop()

payer = insurance if insurance in payers else None
deductible, coinsurance, copay = 0.0, 20.0, 0.0
# One insurer sells very different kinds of plan (employer, Medicare, Medicaid ...), and hospitals are
# paid very differently for each, so the kind of plan matters as much as the company.
plan_type = None
if payer:
    kinds = query(
        """SELECT plan_type FROM payer_prices WHERE payer_group = ?
           GROUP BY 1 ORDER BY count(DISTINCT file_id) DESC, 1""", [payer]).plan_type.tolist()
    if st.session_state.get("plan_kind") not in [ANY_PLAN, *kinds]:
        linked = st.query_params.get("plan")
        st.session_state.plan_kind = linked if linked in kinds else ANY_PLAN
    kind = st.selectbox(
        f"What kind of {payer} plan do you have?", [ANY_PLAN, *kinds], key="plan_kind",
        help="It is usually printed on your insurance card. Plans through a job are commercial; Medicare "
             "Advantage, Medicaid, Essential Plan and Child Health Plus are government programmes.")
    plan_type = None if kind == ANY_PLAN else kind
if insurance == NO_INSURANCE:
    st.caption("You will see each hospital's cash price, which is what it charges people who pay themselves.")
else:
    title = f"💳 Your {payer} plan details" if payer else "💳 Your plan details"
    with st.expander(f"{title}: used to estimate what you would pay", expanded=True):
        plan = st.columns(3)
        deductible = plan[0].number_input(
            "Deductible left to meet ($)", min_value=0.0, value=0.0, step=100.0,
            help="The amount you still have to pay this year before your plan starts paying.")
        coinsurance = plan[1].number_input(
            "Coinsurance (%)", min_value=0.0, max_value=100.0, value=20.0, step=5.0,
            help="Your share of the price after the deductible. 20% is common.")
        copay = plan[2].number_input(
            "Copay ($)", min_value=0.0, value=0.0, step=10.0,
            help="A fixed fee your plan charges for the visit, if any.")
        st.caption(
            "These numbers are on your insurance card or plan summary. Leave them as they are if you are not sure. "
            + ("" if payer else "Because your insurer is not in the list, you will see cash prices and every "
               "insurer's prices; open a hospital to look for your plan by name and enter its price by hand.")
        )

with st.container(key="search-step"):
    st.subheader("Step 2: Search for your care")
    text = st.text_input(
        "What care are you looking for?",
        key="search",
        placeholder="🔍  Try: broken arm, pregnancy scan, MRI brain, blood test, or a billing code like 80053",
    )

    st.markdown("**Popular services**")
    tiles = st.container(key="tiles").columns(4)
    for n, (icon, label, tile_type, tile_code) in enumerate(POPULAR):
        tiles[n % 4].button(label, icon=icon, key=f"tile-{tile_code}", width="stretch",
                            on_click=pick_service, args=(tile_type, tile_code))

    st.markdown("**Common visits: several services added together**")
    bundles = st.container(key="bundles").columns(3)
    for n, (key, (icon, name, about, parts)) in enumerate(BUNDLES.items()):
        bundles[n % 3].button(name, icon=icon, key=f"bundle-{key}", width="stretch", help=about,
                              on_click=pick_service, args=(PACKAGE, key))

    matches = search_services(text) if text else {}
    if text and not matches:
        st.warning("No service matches that search. Try fewer or different words.")
    if matches:
        choice = st.selectbox(f"{len(matches)} matching services", list(matches))
        if matches[choice] != st.session_state.get("picked"):
            st.session_state.scroll_target = "results"
        st.session_state.picked = matches[choice]

picked = st.session_state.get("picked")
if not picked:
    st.info("👆 Search above or tap a popular service to compare prices across the city.")
    scroll_if_asked()
    landing_sections()
    st.stop()

code_type, code = picked
pulse_divider()
with st.container(key="results"):
    st.header(service_title(code_type, code))
    is_package = code_type == PACKAGE
    if is_package:
        part_names = ", ".join(f"{name} ({part_code})" for _, part_code, name in BUNDLES[code][3])
        st.write(f"{BUNDLES[code][2]}. Prices are the total of: {part_names}.")
    st.caption(f"Step 3: Compare hospitals  ·  "
               + (f"Package of {len(BUNDLES[code][3])} billing codes" if is_package
                  else f"Billing code: {code_type} {code}") + "  ·  "
               f"Insurance: {payer or insurance.split(' (')[0]}" + (f", {plan_type}" if plan_type else ""))

    filters = st.columns(2)
    setting_label = filters[0].selectbox("Type of visit", list(SETTINGS))
    boroughs = filters[1].multiselect("Borough", ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"],
                                      placeholder="All boroughs")

    more = st.columns(4)
    zip_text = more[0].text_input("Your ZIP code (optional)", max_chars=5, placeholder="For example 11226")
    zip_code = "".join(c for c in zip_text if c.isdigit())
    home = ZIP_CENTRES.get(zip_code)
    if zip_text and not home:
        more[0].caption("That ZIP code is not in the New York area list.")
    distance_label = more[1].selectbox("Distance", list(DISTANCES), disabled=not home, key="distance",
                                       help="Enter your ZIP code to filter by distance.")
    rating_label = more[2].selectbox("Patient rating", list(RATINGS))
    max_price = more[3].number_input("Highest cash price ($, optional)", min_value=0, value=None, step=100,
                                     placeholder="Any price")

    if is_package:
        everything = compare_package(code, SETTINGS[setting_label], tuple(boroughs), payer, plan_type)
    else:
        everything = compare(code_type, code, SETTINGS[setting_label], tuple(boroughs), payer, plan_type)
    if everything.empty:
        st.warning("No hospital publishes a price for every part of this with these filters. "
                   "Try a different type of visit." if is_package else
                   "No hospital publishes a price for this service with these filters. Try a different type of visit.")
        st.stop()
    everything["miles"] = (
        [miles(home, (lat, lon)) for lat, lon in zip(everything.latitude, everything.longitude)] if home else float("nan")
    )
    # The full price is the hospital's list price, taken from the full-service line when lines differ widely.
    everything["full_price"] = everything.list_low.where(
        ~(everything.list_high > WIDE_RANGE * everything.list_low), everything.list_high)
    # With an insurer chosen, each hospital shows what the plan would pay and what is left for the patient.
    # A hospital with no price for that insurer is treated as not covered: the patient pays the cash price.
    everything["covered"] = everything.insurer_typical.notna() if payer else False
    split = [estimate_owed(price, deductible, coinsurance, copay) if pd.notna(price) else None
             for price in everything.insurer_typical]
    uncovered_cost = everything.cash_compare.fillna(everything.full_price)
    everything["plan_pays"] = [part["plan_pays"] if part else 0.0 for part in split]
    everything["you_pay"] = [part["total"] if part else cost for part, cost in zip(split, uncovered_cost)]
    # A price under a tenth of what the other hospitals publish is almost always a filing mistake or a
    # line for something smaller. It stays in the list, marked, but is kept out of the highlights.
    everything["cash_odd"] = far_below_the_rest(everything.cash_compare)
    everything["insurer_odd"] = far_below_the_rest(everything.insurer_typical) & everything.covered
    results = everything
    if home and DISTANCES[distance_label]:
        results = results[results.miles <= DISTANCES[distance_label]]
    if RATINGS[rating_label]:
        results = results[results.patient_stars >= RATINGS[rating_label]]
    if max_price:
        results = results[results.cash_compare <= max_price]
    if results.empty:
        st.warning(
            f"None of the {len(everything)} hospitals with a price for this service match the distance, rating and "
            "price filters. Loosen one of them to see results."
        )
        st.stop()

    with_cash = results[~results.cash_odd].dropna(subset=["cash_compare"]).sort_values("cash_compare")

    # One clear answer first; the numbers and the full list follow for anyone who wants to check it.
    ranked = rank_options(results, bool(payer), bool(home))
    insured = bool(payer) and not ranked.empty
    if ranked.empty:
        ranked = rank_options(results, False, bool(home))
    if not ranked.empty:
        best = ranked.iloc[0]
        cost_words = "What you would pay" if insured else "The cash price"
        with st.container(key="recommendation"):
            st.markdown(f":orange[**{tr('🏆 Your best option')}**]")
            st.subheader(f"🏆 {best.hospital}")
            figure = st.columns(3)
            figure[0].metric("Your cost (estimate)" if insured else "Cash price here", money(best.cost))
            figure[1].metric("Patients say", "not rated" if pd.isna(best.patient_stars)
                             else f"{stars(best.patient_stars)}  {int(best.patient_recommend_pct)}% recommend")
            figure[2].metric("How far", f"{best.miles:.1f} miles" if pd.notna(best.miles) else best.borough)
            st.markdown("**Why this one**")
            for reason in reasons_for(best, ranked, cost_words):
                st.markdown(f"- {md(reason)}")
            action = st.columns(3)
            action[0].button("See details", key="recommended", type="primary", width="stretch",
                             on_click=choose_hospital, args=(best.hospital,))
            if best.phone:
                digits = "".join(c for c in best.phone if c.isdigit())
                action[1].link_button(f"📞 Call {best.phone}", f"tel:+1{digits}", width="stretch")
            if best.address:
                destination = quote_plus(f"{best.hospital}, {best.address}")
                action[2].link_button("🧭 Get directions",
                                      f"https://www.google.com/maps/dir/?api=1&destination={destination}",
                                      width="stretch")
            st.caption(
                "Chosen by weighing cost first, then patient rating"
                + (", then distance. " if home else ". Enter your ZIP code above to take distance into account. ")
                + ("" if insured or not payer else f"No hospital lists a {payer} price for this, so cash prices "
                   "were compared. ")
                + "Children's, psychiatric, cancer and long-term care hospitals are not suggested automatically. "
                "It is a suggestion to start from, not medical advice."
            )
        runners = ranked.iloc[1:3]
        if len(runners):
            st.markdown("**Two other good options**" if len(runners) == 2 else "**Another good option**")
            places = st.columns(2)
            for column, badge, (_, row) in zip(places, ("🥈 Second choice", "🥉 Third choice"), runners.iterrows()):
                pick_card(column, badge, row, f"{'You pay about' if insured else 'Cash price'} {money(row.cost)}")
        with st.expander("📝 Questions to ask the hospital before you go"):
            st.markdown(
                "- Is this the total price, or will there be separate bills, such as a doctor's fee?\n"
                "- Are you in my insurance plan's network for this service?\n"
                "- What will I owe on the day, and can I pay in instalments?\n"
                "- If I pay myself, is there a discount or financial assistance I can apply for?\n"
                "- Do I need a referral or prior approval from my insurer?"
            )

    st.markdown("**The numbers behind it**")
    left, middle, right = st.columns(3)
    left.metric("Hospitals with a price", len(results))
    if len(with_cash):
        cheapest, priciest = with_cash.iloc[0], with_cash.iloc[-1]
        middle.metric("Lowest cash price", money(cheapest.cash_compare), cheapest.hospital, delta_color="off",
                      delta_arrow="off")
        right.metric("Highest cash price", money(priciest.cash_compare), priciest.hospital, delta_color="off",
                     delta_arrow="off")
        if len(with_cash) > 1 and priciest.cash_compare > cheapest.cash_compare:
            times = priciest.cash_compare / cheapest.cash_compare
            st.success(md(
                f"💡 The same service costs from **{money(cheapest.cash_compare)}** to "
                f"**{money(priciest.cash_compare)}** depending on the hospital, a difference of "
                f"**{money(priciest.cash_compare - cheapest.cash_compare)}**"
                + (f" ({times:.0f} times more)." if times >= 2 else ".")
            ))
    odd = int((results.cash_odd | results.insurer_odd).sum())
    if odd:
        st.caption(
            f"⚠️ {odd} {'hospital shows a price' if odd == 1 else 'hospitals show prices'} under a tenth of what "
            "the others publish. Such a price is usually a filing mistake, so it is marked in the list and left "
            "out of the figures and suggestions here."
        )
    wide = int(results.cash_wide.sum())
    if wide:
        st.caption(
            f"⚠️ {wide} {'hospital lists' if wide == 1 else 'hospitals list'} very different prices under this one "
            "billing code. They are compared on their higher price, because the low line often covers only part of "
            "the service, such as the doctor's fee."
        )

with st.container(key="list-section"):
    st.subheader("All hospitals for this service")
    sorts = dict(SORTS)
    if payer:
        sorts["What you pay (lowest first)"] = (["you_pay", "cash_compare"], [True, True])
    if home:
        sorts["Closest first"] = (["miles", "cash_compare"], [True, True])
    controls = st.columns([3, 2])
    sort_label = controls[0].radio("Sort hospitals by", list(sorts), horizontal=True, key="sort_by")
    grouped = controls[1].toggle("Group campuses that share one price list", value=True, key="grouped",
                                 help="Hospitals in one system often publish a single price file, so their prices "
                                      "are identical. Grouping shows them as one row.")
    sort_columns, ascending = sorts[sort_label]
    results = results.sort_values(sort_columns, ascending=ascending, na_position="last")
    names = results.hospital.tolist()
    if st.session_state.get("hospital") not in names:
        st.session_state.hospital = names[0]

    # One row per price list when grouped: the first campus in the current order stands for the group.
    shown = results.assign(campuses=results.groupby("file_id").hospital.transform("count") if grouped else 1)
    if grouped:
        shown = shown.drop_duplicates("file_id")
    shown = shown.assign(
        label=[h if n == 1 else f"{h} (+{n - 1} more with the same prices)" for h, n in zip(shown.hospital, shown.campuses)],
        cash_text=[money_range(a, b) + (" ⚠️" if w else "") + (" ⚠️ unusually low" if odd_one else "")
                   for a, b, w, odd_one in zip(shown.cash_low, shown.cash_high, shown.cash_wide, shown.cash_odd)],
        distance=["" if pd.isna(m) else f"{m:.1f} mi" for m in shown.miles],
        coverage=[f"Yes, {payer} price listed" if c else f"No {payer} price listed" for c in shown.covered],
        as_of=[("" if pd.isna(d) else f"{d:%b %d, %Y}") + (" (old)" if is_old(d) else "") for d in shown.file_date],
    )
    shown_names = shown.hospital.tolist()

    list_tab, chart_tab, map_tab = st.tabs(["📋 All hospitals", "📊 Price chart", "🗺️ Map"])
    with list_tab:
        insurer_heading = f"{payer} price" if payer else "Insurer prices (all plans)"
        table = pd.DataFrame(
            {
                "Hospital": shown.label,
                "Patient rating": [stars(s) for s in shown.patient_stars],
                "Would recommend": ["" if pd.isna(p) else f"{int(p)}% of patients" for p in shown.patient_recommend_pct],
                "Distance": shown.distance,
                "Borough": shown.borough,
                "Phone": shown.phone,
                "Cash price (no insurance)": shown.cash_text,
                insurer_heading: [money_range(a, b) for a, b in zip(shown.insurer_low, shown.insurer_high)],
                "Typical insurer price": [money_range(a, a) for a in shown.insurer_typical],
                "List price": [money_range(a, b) for a, b in zip(shown.list_low, shown.list_high)],
                "Prices as of": shown.as_of,
            }
        )
        if payer:
            # With an insurer chosen the list answers three questions: the full price, what the plan pays, what is left.
            table = pd.DataFrame(
                {
                    "Hospital": shown.label,
                    "Patient rating": [stars(s) for s in shown.patient_stars],
                    "Distance": shown.distance,
                    "Covered?": shown.coverage,
                    "Full price": [money(v) for v in shown.full_price],
                    f"{payer} agreed price": [money(v) if c else "none listed"
                                              for v, c in zip(shown.insurer_typical, shown.covered)],
                    "Insurance pays (estimate)": [money(v) if c else "$0" for v, c in zip(shown.plan_pays, shown.covered)],
                    "You pay (estimate)": [
                        money(v) + ("" if c else " (cash price)") + (" ⚠️ unusually low" if odd_one else "")
                        for v, c, odd_one in zip(shown.you_pay, shown.covered, shown.insurer_odd)],
                    "Cash price (no insurance)": shown.cash_text,
                    "Borough": shown.borough,
                    "Phone": shown.phone,
                    "Prices as of": shown.as_of,
                }
            )
        if not home:
            table = table.drop(columns="Distance")
        with st.container(key="list-desktop"):
            st.write("Click a hospital's row to see its address, directions and full price detail.")
            clicked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun",
                                   selection_mode="single-row", key="hospital_table")
        # On a phone the wide table is replaced by a stack of cards.
        with st.container(key="list-mobile"):
            for row in shown.head(MOBILE_ROWS).itertuples():
                with st.container(border=True):
                    st.markdown(f"**{row.label}**")
                    st.write(" · ".join(part for part in (stars(row.patient_stars), row.borough, row.distance) if part))
                    if payer and row.covered:
                        st.write(md(f"Full price: **{money(row.full_price)}** · {payer} pays about "
                                    f"**{money(row.plan_pays)}** · You pay about **{money(row.you_pay)}**"))
                    elif payer:
                        st.write(md(f"No {payer} price listed. Cash price: **{row.cash_text}**"))
                    else:
                        st.write(md(f"Cash price: **{row.cash_text}** · Typical insurer price: "
                                    f"**{money(row.insurer_typical)}**"))
                    st.button("View hospital", key=f"mobile-{row.hospital}", on_click=choose_hospital,
                              args=(row.hospital,), width="stretch")
            if len(shown) > MOBILE_ROWS:
                st.caption(f"Showing the first {MOBILE_ROWS} of {len(shown)}. Change the sort or filters to see others.")
        all_hospitals = query("SELECT hospital, has_prices FROM hospitals ORDER BY hospital")
        missing = all_hospitals[~all_hospitals.hospital.isin(everything.hospital)]
        if not boroughs and len(missing):
            with st.expander(f"{len(missing)} hospitals with no published price for this service"):
                not_loaded = missing[~missing.has_prices].hospital.tolist()
                st.write(", ".join(missing[missing.has_prices].hospital) or "None")
                if not_loaded:
                    st.write("Price file not loaded yet: " + ", ".join(not_loaded))
    with chart_tab:
        # Two versions of the chart: hospital names get less room on a phone. CSS shows one of them.
        with st.container(key="chart-desktop"):
            price_chart(shown)
        with st.container(key="chart-mobile"):
            price_chart(shown, label_width=130)
    with map_tab:
        map_click = hospital_map(results, st.session_state.hospital)

# A new click on the table or the map moves the selection to that hospital.
rows = clicked.selection.rows
table_click = shown_names[rows[0]] if rows and rows[0] < len(shown_names) else None
for source, name in (("table", table_click), ("map", map_click)):
    if not name:
        st.session_state[f"last_{source}"] = None
    elif st.session_state.get(f"last_{source}") != (picked, name):
        st.session_state[f"last_{source}"] = (picked, name)
        st.session_state.scroll_target = "hospital-card"
        if name in names and name != st.session_state.hospital:
            st.session_state.hospital = name
            st.rerun()

# ------------------------------------------------------------ one hospital

hospital = st.selectbox("Hospital", names, key="hospital")
chosen = results[results.hospital == hospital].iloc[0]
file_id = chosen.file_id
# Keeping the choice in the page address makes the page shareable as a link.
st.query_params.update({"insurance": insurance, "service": f"{code_type} {code}", "hospital": hospital})
if plan_type:
    st.query_params["plan"] = plan_type
else:
    st.query_params.pop("plan", None)

with st.container(border=True, key="hospital-card"):
    st.caption("Step 4: Hospital details")
    st.subheader(f"🏥 {hospital}")
    if chosen.cash_odd or chosen.insurer_odd:
        st.warning("A price here is under a tenth of what other hospitals publish for this service. That usually "
                   "means a mistake in the hospital's file or a line for something smaller. Call to confirm it.")
    if is_old(chosen.file_date):
        st.warning(f"These prices are from {chosen.file_date:%B %Y}, more than a year ago. Call the hospital to "
                   "check that they still apply.")
    about, prices = st.columns([2, 3])
    with about:
        if pd.isna(chosen.patient_stars):
            st.write("Patient rating: not rated")
        else:
            st.write(
                f"Patient rating: {stars(chosen.patient_stars)} ({int(chosen.patient_stars)} of 5), "
                f"{int(chosen.patient_recommend_pct)}% would definitely recommend, "
                f"from {int(chosen.patient_surveys):,} patient surveys"
            )
        if not pd.isna(chosen.medicare_stars):
            st.write(f"Medicare overall quality: {stars(chosen.medicare_stars)} ({int(chosen.medicare_stars)} of 5)")
        if chosen.medicare_rated_as and chosen.medicare_rated_as.lower() not in hospital.lower():
            st.caption(f"Rated by Medicare as part of {chosen.medicare_rated_as}.")
        if chosen.address:
            st.write(f"📍 {chosen.address}")
        if pd.notna(chosen.miles):
            st.write(f"🚗 About {chosen.miles:.1f} miles from ZIP code {zip_code}, in a straight line")
        if chosen.phone:
            digits = "".join(c for c in chosen.phone if c.isdigit())
            st.markdown(f"📞 [{chosen.phone}](tel:+1{digits}) (main line)")
        if chosen.address:
            destination = quote_plus(f"{hospital}, {chosen.address}")
            st.link_button("🧭 Get directions on Google Maps",
                           f"https://www.google.com/maps/dir/?api=1&destination={destination}")
    with prices:
        if payer:
            st.markdown(f"**With {payer}**")
            cover = st.columns(3)
            cover[0].metric("Full price", money(chosen.full_price))
            if chosen.covered:
                cover[1].metric("Insurance pays about", money(chosen.plan_pays))
                cover[2].metric("You pay about", money(chosen.you_pay))
                st.write(md(
                    f"{payer} has agreed a price of **{money(chosen.insurer_typical)}** for this service here. "
                    f"With {money(deductible)} of deductible left, {coinsurance:g}% coinsurance and "
                    f"{money(copay)} copay, your share is about **{money(chosen.you_pay)}**."
                ))
            else:
                cover[1].metric("Insurance pays about", "$0")
                cover[2].metric("You pay about", money(chosen.you_pay))
                st.warning(md(
                    f"This hospital's price file lists no fixed {payer} price for this service. It may be out of "
                    f"network for your plan, or the plan may pay by a formula. If it is not covered, you would pay "
                    f"the cash price, about {money(chosen.you_pay)}. Call the hospital and your insurer to check."
                ))
            st.markdown("**Other prices here**")
        tile = st.columns(3)
        tile[0].metric("If you pay yourself", md(money_range(chosen.cash_low, chosen.cash_high)))
        tile[1].metric(f"Typical {payer} price" if payer else "Typical insurer price", money(chosen.insurer_typical))
        tile[2].metric("List price", md(money_range(chosen.list_low, chosen.list_high)))
        if chosen.cash_wide:
            st.caption("⚠️ This hospital lists very different cash prices under this billing code. The lower one "
                       "may cover only part of the service. Ask the hospital which price applies to you.")
        if pd.notna(chosen.cash_compare) and len(with_cash) > 2:
            middle_price = with_cash.cash_compare.median()
            gap = chosen.cash_compare - middle_price
            if abs(gap) >= 1:
                st.write(md(
                    f"The cash price here is **{money(abs(gap))} {'below' if gap < 0 else 'above'}** the "
                    f"middle cash price of the hospitals listed ({money(middle_price)})."
                ))
        if pd.notna(chosen.file_date):
            st.caption(f"Prices from the hospital's file dated {chosen.file_date:%B %d, %Y}.")
        st.caption("🔗 To share this comparison, copy the address from your browser's address bar.")

    with st.expander("🧮 Try a different plan price"):
        starting = chosen.insurer_typical if pd.notna(chosen.insurer_typical) else chosen.cash_compare
        box = st.columns(4)
        # The price box starts again from this hospital's typical price whenever the hospital,
        # service or insurer changes, and otherwise keeps what the person typed.
        if st.session_state.get("plan_context") != (file_id, code, payer):
            st.session_state.plan_context = (file_id, code, payer)
            st.session_state.plan_price = float(round(starting)) if pd.notna(starting) else 0.0
        plan_price = box[0].number_input(
            "Your plan's price ($)", min_value=0.0, step=50.0, key="plan_price",
            help="Starts at the typical insurer price here. Replace it with your own plan's price from the table below.",
        )
        box[1].metric("Deductible left", money(deductible))
        box[2].metric("Coinsurance", f"{coinsurance:g}%")
        box[3].metric("Copay", money(copay))
        owed = estimate_owed(plan_price, deductible, coinsurance, copay)
        st.metric("You might owe about", money(owed["total"]))
        st.write(md(
            f"That is {money(owed['deductible'])} toward your deductible, {money(owed['coinsurance'])} coinsurance "
            f"and {money(owed['copay'])} copay. Your plan would pay about {money(owed['plan_pays'])}."
        ))
        if pd.notna(chosen.cash_compare) and owed["total"] > chosen.cash_compare:
            st.info(md(f"The cash price here is {money(chosen.cash_compare)}, lower than this estimate. Ask the "
                       "hospital whether you can pay the cash price instead of using insurance."))
        st.caption("The deductible, coinsurance and copay come from your plan details in step 1. "
                   "A rough guide only. It does not know your out-of-pocket maximum, whether this hospital is in "
                   "your network, or what other services your visit will include. Confirm with your insurer and "
                   "the hospital.")

    if is_package:
        st.markdown("**What the total is made of**")
        st.dataframe(
            package_breakdown(code, hospital, SETTINGS[setting_label], payer, plan_type),
            hide_index=True, width="stretch",
            column_config={
                "Cash price": st.column_config.NumberColumn(format="$%.2f"),
                "Insurer price": st.column_config.NumberColumn(f"{payer} price" if payer else "Typical insurer price",
                                                               format="$%.2f"),
                "List price": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        st.caption("Search for one of these services by name to see every insurance plan's price for it. "
                   "A real visit can include other charges, such as a doctor's fee.")
    else:
        rates = plan_rates(file_id, code_type, code)
        if payer:
            rates = rates[rates.insurer.isin(
                query("SELECT DISTINCT payer_name FROM rates WHERE file_id = ? AND payer_group = ?",
                      [file_id, payer]).payer_name
            )]
            if plan_type:
                rates = rates[rates.plan_type == plan_type]
        rates = rates.assign(details=[payment_details(r) for r in rates.itertuples()]).drop(
            columns=["percent_of_charges", "estimated_amount", "formula"]
        )
        # Some hospitals append their internal plan number, for example "APWU [1016]"; it only crowds the table.
        for column in ("insurer", "plan"):
            rates[column] = rates[column].str.replace(r"\s*\[\d+\]\s*$", "", regex=True)
        # A column where every row says the same thing is stated once below instead of repeated.
        same_everywhere = {
            label: rates[column].iloc[0]
            for column, label in (("setting", "setting"), ("methodology", "payment method"))
            if len(rates) > 1 and rates[column].nunique(dropna=False) == 1 and pd.notna(rates[column].iloc[0])
        }
        rates = rates.drop(columns=[c for c, label in (("setting", "setting"), ("methodology", "payment method"))
                                    if label in same_everywhere])
        with st.expander(f"Prices by insurance plan ({len(rates):,} rows)", expanded=True):
            st.dataframe(
                tidy(rates),
                hide_index=True,
                width="stretch",
                column_config={
                    "insurer": st.column_config.TextColumn("Insurer", width=250),
                    "plan": st.column_config.TextColumn("Plan", width=290),
                    "plan_type": st.column_config.TextColumn("Kind of plan", width=170),
                    "setting": st.column_config.TextColumn("Setting", width=85),
                    "modifiers": st.column_config.TextColumn("Modifiers", width=80),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f", width=85),
                    "methodology": st.column_config.TextColumn("Method", width=100),
                    "details": st.column_config.TextColumn("Other payment terms", width=300),
                },
            )
            st.caption(
                "".join(f"Every row has the same {label}: {value}. " for label, value in same_everywhere.items())
                + "A blank price means the plan pays by a percentage or a formula instead of a fixed amount; "
                "the last column gives those terms. Drag a column edge to widen it, or use the full-screen "
                "button at the top right of the table."
            )
            terms = rates.details.dropna().value_counts()
            if len(terms):
                # The table cannot wrap text, so long payment terms are also written out in full.
                st.markdown(f"**Payment terms in full ({len(terms)})**")
                for term, count in terms.head(25).items():
                    st.markdown(f"- {md(term)} *({count} {'row' if count == 1 else 'rows'})*")
                if len(terms) > 25:
                    st.caption(f"Showing the 25 most common of {len(terms)}.")
        with st.expander(f"Lines in the hospital's price file for {code_type} {code}"):
            st.dataframe(
                tidy(line_items(file_id, code_type, code)),
                hide_index=True,
                width="stretch",
                column_config={
                    "list_price": st.column_config.NumberColumn("List price", format="$%.2f"),
                    "cash_price": st.column_config.NumberColumn("Cash price", format="$%.2f"),
                },
            )

scroll_if_asked()

# --------------------------------------------------------------- explainers

faq_section()
with st.expander("🗂️ Where does the data come from?"):
    files = query(
        """SELECT h.hospital, h.borough, h.address, h.phone, h.system, f.last_updated AS prices_as_of, h.has_prices,
                  h.source_url
           FROM hospitals h LEFT JOIN files f USING (file_id) ORDER BY h.has_prices, h.hospital"""
    )
    st.write(
        f"{int(files.has_prices.sum())} of {len(files)} New York City hospitals are loaded. "
        "Each hospital's file is downloaded from the address it publishes in its own `cms-hpt.txt` index, "
        "as required by the federal Hospital Price Transparency rule. Prices are shown exactly as published; "
        "missing prices are left blank, never estimated. Ratings come from Medicare's patient survey, addresses "
        "from the New York State health facility registry, and ZIP code positions from the Census Bureau."
    )
    st.dataframe(files, hide_index=True, width="stretch")
st.caption(
    "These are published prices, not a quote. What you pay depends on your plan, your deductible and the care "
    "you receive, and a doctor's fee may be billed separately. Hospitals in the same system often share one "
    "price file, so their prices match. This app is not medical or financial advice."
)
