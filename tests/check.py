"""End-to-end checks: the app's behaviour, and database prices against the raw hospital files.

Run:  python tests/check.py
"""

import csv
import sys
from pathlib import Path

import duckdb
import ijson
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from load import find_raw, to_number  # noqa: E402
from paths import DATABASE  # noqa: E402

results = []


def check(name, passed, detail=""):
    results.append(passed)
    print(f"{'PASS' if passed else 'FAIL'}  {name}{'  [' + str(detail) + ']' if detail else ''}")


NO_INSURANCE = "I don't have insurance (I will pay myself)"


def run_app(insurance=NO_INSURANCE):
    """Start the app and, unless told otherwise, pass step 1 as someone paying for themselves."""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    if insurance:
        next(s for s in at.selectbox if s.label == "Your insurance").select(insurance).run()
    return at


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def dollars(text):
    return float(text.strip("$").replace(",", ""))


def card_title(at):
    """The hospital named at the top of the details card."""
    return next(s.value[2:] for s in at.subheader if s.value.startswith("🏥 "))


def directions_url(at):
    """The Google Maps link on the hospital's details card (the last one on the page)."""
    return [b.proto.url for b in at.get("link_button") if "google.com/maps" in b.proto.url][-1]


# ------------------------------------------------------------------ the app

at = run_app(insurance=None)
check("app starts without errors", not at.exception)
check("choosing insurance comes first: search and services are hidden until then",
      not any(b.label == "MRI of the brain" for b in at.button) and len(at.text_input) == 0
      and [s.label for s in at.selectbox] == ["Your insurance"] and "choosing your insurance" in at.info[0].value)
quick = [b.label for b in at.button]
check("step 1 offers one-tap choices for common insurers and for no insurance",
      len(quick) == 8 and "I have no insurance" in quick and "Aetna" in quick, quick)
next(b for b in at.button if b.label == "Aetna").click().run()
check("a one-tap choice selects that insurer and opens the search",
      next(s for s in at.selectbox if s.label == "Your insurance").value == "Aetna" and len(at.text_input) == 1)
at = run_app()
keys = [b.key for b in at.button]
check("twelve popular-service tiles and six packages",
      sum(key.startswith("tile-") for key in keys) == 12 and sum(key.startswith("bundle-") for key in keys) == 6,
      len(keys))

next(b for b in at.button if b.label == "MRI of the brain").click().run()
check("a tile shows results", not at.exception and metric(at, "Hospitals with a price").isdigit(),
      metric(at, "Hospitals with a price"))
check("price chart and map are drawn",
      len(at.get("vega_lite_chart")) == 2 and len(at.get("deck_gl_json_chart")) == 1)
check("savings message is shown", len(at.success) == 1 and "depending on the hospital" in at.success[0].value)
details = [b for b in at.button if b.label == "See details"]
recommended = next(s.value[2:] for s in at.subheader if s.value.startswith("🏆 "))
check("one best option is recommended, with two alternatives", len(details) == 3 and bool(recommended), recommended)
check("a children's or other single-purpose hospital is not the automatic recommendation",
      not any(word in recommended for word in ("Children", "Behavioral", "Calvary", "Sloan Kettering")), recommended)
check("the recommendation explains itself and gives next steps",
      sum(m.value.startswith("- ") for m in at.markdown) >= 2
      and any("Questions to ask the hospital" in e.label for e in at.expander)
      and any(b.proto.url.startswith("tel:+1") for b in at.get("link_button")))
next(b for b in at.button if b.key == "recommended").click().run()
check("the recommendation's button opens that hospital's details",
      next(s for s in at.selectbox if s.label == "Hospital").value == recommended == card_title(at), card_title(at))
all_count = int(metric(at, "Hospitals with a price"))
hospital_box = next(s for s in at.selectbox if s.label == "Hospital")
check("hospital list matches the count", len(hospital_box.options) == all_count)
first = hospital_box.value
check("address is shown", any("📍" in m.value for m in at.markdown))
check("phone number is shown", any("📞" in m.value and "tel:+1" in m.value for m in at.markdown))
check("directions link points to Google Maps with the hospital as destination",
      directions_url(at).startswith("https://www.google.com/maps/dir/?api=1&destination=")
      and first.split()[0] in directions_url(at), directions_url(at)[:110])
ranked_cash = [dollars(m.value) for m in at.metric if m.label == "Cash price here"]
check("without insurance the recommendation is based on the cash price", len(ranked_cash) == 1, ranked_cash)

other = hospital_box.options[5]
hospital_box.select(other).run()
check("choosing another hospital changes the address and link",
      other.split()[0] in directions_url(at) and card_title(at) == other, other)

next(m for m in at.multiselect if m.label == "Borough").select("Bronx").run()
bronx = int(metric(at, "Hospitals with a price"))
check("borough filter narrows the list", 0 < bronx < all_count, f"{bronx} of {all_count}")
next(m for m in at.multiselect if m.label == "Borough").unselect("Bronx").run()

payer_box = next(s for s in at.selectbox if s.label == "Your insurance")
check("insurance list has the major insurers", {"Aetna", "Cigna", "Healthfirst"} <= set(payer_box.options),
      len(payer_box.options))
payer_box.select("Aetna").run()
check("insurance filter runs without errors", not at.exception)
payer_box.select(NO_INSURANCE).run()

def radio(label):
    return next(r for r in at.radio if r.label == label)


stars_by_hospital = dict(
    duckdb.connect(str(DATABASE), read_only=True)
    .execute("SELECT hospital, coalesce(patient_stars, 0) FROM hospitals")
    .fetchall()
)
order = [stars_by_hospital[h] for h in next(s for s in at.selectbox if s.label == "Hospital").options]
check("hospitals are sorted by patient rating, highest first, by default",
      order == sorted(order, reverse=True) and order[0] > order[-1], f"{order[0]} stars down to {order[-1]}")
for option in radio("Sort hospitals by").options[1:]:
    radio("Sort hospitals by").set_value(option).run()
    check(f"sort option works: {option}", not at.exception)

next(s for s in at.selectbox if s.label == "Type of visit").select("Inpatient (admitted to hospital)").run()
check("inpatient filter runs without errors", not at.exception)

at = run_app()
next(b for b in at.button if b.label == "Vaginal delivery").click().run()
check("an inpatient service shows results with the default filters",
      not at.exception and int(metric(at, "Hospitals with a price")) > 20, metric(at, "Hospitals with a price"))

at = run_app()
at.text_input[0].set_value("colonoscopy").run()
matches = next(s for s in at.selectbox if "matching services" in s.label)
check("text search finds services", len(matches.options) > 3, len(matches.options))
at.text_input[0].set_value("zzzzqqq").run()
check("unknown search shows a warning, not an error", not at.exception and len(at.warning) == 1)
at = run_app()
at.text_input[0].set_value("80053").run()
check("search by billing code works", any("80053" in o for o in next(
    s for s in at.selectbox if "matching services" in s.label).options))

# ------------------------------------------------------- newer features


def box(label):
    return next(s for s in at.selectbox if s.label == label)


def number(label):
    return next(n for n in at.number_input if n.label == label)


at = run_app()
at.text_input[0].set_value("broken arm").run()
options = next(s for s in at.selectbox if "matching services" in s.label).options
check("everyday words find a service", any(o.startswith("X-ray of the arm or wrist") for o in options), options[0])

at = run_app()
next(b for b in at.button if b.label == "MRI of the brain").click().run()
check("a doctor's-fee line is not promoted as the lowest price", metric(at, "Lowest cash price") != "$190",
      metric(at, "Lowest cash price"))
left_out = duckdb.connect(str(DATABASE), read_only=True).execute(
    """SELECT sum(p.partial_lines) FROM procedure_prices p JOIN hospitals h USING (file_id)
       WHERE p.code = '70551' AND h.hospital = 'Maimonides Medical Center'""").fetchone()[0]
check("the database leaves partial-service lines out of comparisons", left_out > 0, f"{left_out} lines left out")
box("Hospital").select("Maimonides Medical Center").run()
typical = metric(at, "Typical insurer price")
check("typical insurer price ignores partial-service lines", not at.exception and typical != "$65"
      and float(typical.strip("$").replace(",", "")) > 200, typical)
everyone = int(metric(at, "Hospitals with a price"))
table = at.dataframe[0].value
check("campuses that share a price list are grouped", len(table) < everyone, f"{len(table)} rows for {everyone}")
check("phone cards are available", len([b for b in at.button if b.label == "View hospital"]) > 0)

box("Patient rating").select("3 stars or more").run()
rated = int(metric(at, "Hospitals with a price"))
check("rating filter narrows the list", 0 < rated < everyone, f"{rated} of {everyone}")
box("Patient rating").select("Any rating").run()

number("Highest cash price ($, optional)").set_value(600).run()
cheap = int(metric(at, "Hospitals with a price"))
check("price filter narrows the list", 0 < cheap < everyone, f"{cheap} of {everyone}")
number("Highest cash price ($, optional)").set_value(None).run()

next(i for i in at.text_input if i.label == "Your ZIP code (optional)").set_value("11226").run()
check("a ZIP code adds a closest-first sort", "Closest first" in radio("Sort hospitals by").options)
radio("Sort hospitals by").set_value("Closest first").run()
nearest = box("Hospital").options[0]
# Kings County and SUNY Downstate face each other across the street, about a mile from this ZIP code's centre.
check("the closest hospital to 11226 is one of the two in that neighbourhood",
      nearest in ("Kings County Hospital Center", "SUNY Downstate (University Hospital of Brooklyn)"), nearest)
check("distance is shown", "Distance" in at.dataframe[0].value.columns
      and any("miles from ZIP code 11226" in m.value for m in at.markdown))
box("Distance").select("Within 2 miles").run()
near = int(metric(at, "Hospitals with a price"))
check("distance filter narrows the list", 0 < near < everyone, f"{near} of {everyone}")

box("Your insurance").select("Aetna").run()
number("Your plan's price ($)").set_value(1000.0).run()
number("Deductible left to meet ($)").set_value(300.0).run()
number("Coinsurance (%)").set_value(20.0).run()
number("Copay ($)").set_value(25.0).run()
check("cost calculator adds deductible, coinsurance and copay", metric(at, "You might owe about") == "$465",
      metric(at, "You might owe about"))

questions = [e.label for e in at.expander]
check("frequently asked questions are shown", sum(q.endswith("?") for q in questions) >= 10,
      sum(q.endswith("?") for q in questions))
check("the page address carries the insurance, service and hospital",
      at.query_params["insurance"] == "Aetna" and at.query_params["service"] == "CPT/HCPCS 70551"
      and at.query_params["hospital"] == box("Hospital").value,
      dict(at.query_params))

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
at.query_params["insurance"] = "Aetna"
at.query_params["service"] = "CPT/HCPCS 71046"
at.query_params["hospital"] = "Bellevue Hospital Center"
at.run()
check("a shared link opens the same insurance, service and hospital",
      not at.exception and "Chest X-ray" in at.header[0].value and box("Hospital").value == "Bellevue Hospital Center"
      and box("Your insurance").value == "Aetna",
      at.header[0].value if at.header else "no header")
check("old price files are marked", any("(old)" in str(v) for v in at.dataframe[0].value["Prices as of"]))

# -------------------------------------------------- with an insurer chosen


def dollars(text):
    return float(text.strip("$").replace(",", ""))


at = run_app()
next(b for b in at.button if b.label == "MRI of the brain").click().run()
box("Your insurance").select("Humana").run()
table = at.dataframe[0].value
check("choosing an insurer adds full price, insurance share and patient share to the list",
      {"Covered?", "Full price", "Humana agreed price", "Insurance pays (estimate)", "You pay (estimate)"}
      <= set(table.columns), list(table.columns)[:6])
check("an insurer adds a what-you-pay sort", "What you pay (lowest first)" in radio("Sort hospitals by").options)
covered = table[table["Covered?"].str.startswith("Yes")]
uncovered = table[table["Covered?"].str.startswith("No")]
check("the list separates hospitals with and without a price for that insurer",
      len(covered) > 0 and len(uncovered) > 0, f"{len(covered)} covered, {len(uncovered)} not")

name = covered.Hospital.iloc[0].split(" (+")[0]
box("Hospital").select(name).run()
agreed = dollars(metric(at, "Typical Humana price"))
check("with no deductible, the patient pays the coinsurance share of the agreed price",
      abs(dollars(metric(at, "You pay about")) - round(agreed * 0.2)) <= 1
      and abs(dollars(metric(at, "Insurance pays about")) - round(agreed * 0.8)) <= 1,
      f"agreed {agreed:,.0f}, you pay {metric(at, 'You pay about')}, plan pays {metric(at, 'Insurance pays about')}")
number("Deductible left to meet ($)").set_value(1000000.0).run()
check("with a large deductible left, the patient pays the whole agreed price and the plan pays nothing",
      abs(dollars(metric(at, "You pay about")) - round(agreed)) <= 1 and metric(at, "Insurance pays about") == "$0",
      metric(at, "You pay about"))
number("Deductible left to meet ($)").set_value(0.0).run()

name = uncovered.Hospital.iloc[0].split(" (+")[0]
box("Hospital").select(name).run()
check("a hospital with no price for that insurer is shown as not covered, at the cash price",
      metric(at, "Insurance pays about") == "$0"
      and any("lists no fixed Humana price" in w.value for w in at.warning), name)

# ------------------------------------ kind of plan, packages, odd prices, Spanish

at = run_app("Aetna")
kinds = box("What kind of Aetna plan do you have?")
check("an insurer's kinds of plan are offered", {"Commercial / employer", "Medicare Advantage"} <= set(kinds.options),
      kinds.options)
next(b for b in at.button if b.label == "Chest X-ray").click().run()
pays = [dollars(v.split(" ")[0]) for v, c in zip(at.dataframe[0].value["You pay (estimate)"],
                                                  at.dataframe[0].value["Covered?"]) if c.startswith("Yes")]
middle = sorted(pays)[len(pays) // 2]
suggested = dollars(metric(at, "Your cost (estimate)"))
check("a price far below every other hospital's is never the recommendation",
      suggested >= middle * 0.1, f"suggested ${suggested:,.0f}, middle ${middle:,.0f}")
any_plan = at.dataframe[0].value["Aetna agreed price"].tolist()
box("What kind of Aetna plan do you have?").select("Medicare Advantage").run()
check("choosing the kind of plan changes the prices and is kept in the page address",
      not at.exception and at.dataframe[0].value["Aetna agreed price"].tolist() != any_plan
      and at.query_params["plan"] == "Medicare Advantage"
      and any("Medicare Advantage" in c.value for c in at.caption))

at = run_app()
next(b for b in at.button if b.label == "Routine blood work").click().run()
parts = next(d.value for d in at.dataframe if "Billing code" in d.value.columns)
check("a package lists its parts and compares hospitals on the total",
      not at.exception and "Routine blood work" in at.header[0].value and len(parts) == 5
      and int(metric(at, "Hospitals with a price")) > 10, f"{len(parts)} parts")
cash = metric(at, "If you pay yourself").replace("\\", "")
if "–" not in cash and cash.startswith("$") and parts["Cash price"].notna().all():
    check("a package's cash total is the sum of its parts",
          abs(dollars(cash) - round(parts["Cash price"].sum())) <= 1, f"{cash} vs {parts['Cash price'].sum():,.2f}")

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
at.run()
radio("Language / Idioma").set_value("Español").run()
check("Spanish: step 1 is in Spanish", any("Paso 1: Elija su seguro" in s.value for s in at.subheader))
# Options are shown translated; the value the app receives stays in English.
next(s for s in at.selectbox if s.label == "Su seguro").select("No tengo seguro (pagaré por mi cuenta)").run()
check("Spanish: step 2 and the service tiles are in Spanish",
      any("Paso 2" in s.value for s in at.subheader)
      and any(b.label == "Resonancia magnética del cerebro" for b in at.button))
# Past this point the test tool cannot follow Spanish option names, so the translator is checked directly.
sys.path.insert(0, str(ROOT))
import i18n  # noqa: E402

i18n.spanish_on = lambda: True
sentence = ("💡 The same service costs from **\\$46** to **\\$878** depending on the hospital, a difference of "
            "**\\$832** (19 times more).")
check("Spanish: a sentence with numbers is translated whole, numbers kept",
      i18n.tr(sentence) == "💡 El mismo servicio cuesta entre **\\$46** y **\\$878** según el hospital, una "
                           "diferencia de **\\$832** (19 veces más).", i18n.tr(sentence)[:60])
rating = "Patient rating: ★★★★☆ (4 of 5), 87% would definitely recommend, from 897 patient surveys"
check("Spanish: the patient rating line is translated",
      i18n.tr(rating).startswith("Calificación de pacientes: ★★★★☆ (4 de 5), 87%"), i18n.tr(rating)[:50])
check("Spanish: short phrases and table headings are translated",
      i18n.tr("50 of 57") == "50 de 57" and i18n.tr("Aetna agreed price") == "Precio acordado con Aetna"
      and i18n.tr("Cash price (no insurance)") == "Precio en efectivo (sin seguro)")
check("Spanish: text with no translation is left as it is, not broken",
      i18n.tr("Hospital for Special Surgery Main Hospital") == "Hospital for Special Surgery Main Hospital")
import pandas as pd  # noqa: E402

cells = i18n.tr_table(pd.DataFrame({"List price": ["not published", "$5"], "plan": ["Plan of record", "x"]}))
check("Spanish: table cells are translated, text from hospital files is not",
      list(cells.columns) == ["Precio de lista", "plan"] and cells.iloc[0, 0] == "no publicado"
      and cells.iloc[0, 1] == "Plan of record", cells.iloc[0].tolist())
i18n.spanish_on = lambda: False
check("English: the translator changes nothing", i18n.tr("50 of 57") == "50 of 57")

# ----------------------------------------------------------------- the data

con = duckdb.connect(str(DATABASE), read_only=True)
total, with_address, with_prices = con.execute(
    "SELECT count(*), count(address), count(*) FILTER (has_prices) FROM hospitals"
).fetchone()
check("every hospital has an address", total == with_address, f"{with_address} of {total}")
with_phone = con.execute("SELECT count(*) FROM hospitals WHERE regexp_matches(phone, '^\\(\\d{3}\\) \\d{3}-\\d{4}$')").fetchone()[0]
check("every hospital has a phone number", total == with_phone, f"{with_phone} of {total}")
check("hospitals with prices loaded", with_prices >= 50, f"{with_prices} of {total}")
bad = con.execute(
    """SELECT (SELECT count(*) FROM items WHERE gross_charge <= 0 OR cash_price <= 0)
            + (SELECT count(*) FROM rates WHERE negotiated_dollar <= 0)"""
).fetchone()[0]
check("no zero or negative prices", bad == 0, bad)
dupes = con.execute(
    """SELECT count(*) FROM (SELECT 1 FROM procedure_prices GROUP BY file_id, code_type, code, setting
                             HAVING count(*) > 1)"""
).fetchone()[0]
check("one row per hospital file, code and setting", dupes == 0, dupes)


def raw_prices(file_id, code):
    """(list price, cash price) pairs for a code, read straight from the hospital's file."""
    path = find_raw(file_id)
    found = set()
    if path.suffix == ".json":
        with path.open("rb") as f:
            if f.read(3) != b"\xef\xbb\xbf":
                f.seek(0)
            for entry in ijson.items(f, "standard_charge_information.item", use_float=True):
                if any(str(c.get("code")).strip() == code for c in entry.get("code_information") or []):
                    for charge in entry.get("standard_charges") or []:
                        found.add((to_number(charge.get("gross_charge")), to_number(charge.get("discounted_cash"))))
    else:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            next(reader), next(reader)
            header = [h.strip().lower().replace(" ", "") for h in next(reader)]
            code_columns = [i for i, h in enumerate(header) if h.startswith("code|") and not h.endswith("type")]
            gross, cash = header.index("standard_charge|gross"), header.index("standard_charge|discounted_cash")
            for row in reader:
                if any(i < len(row) and row[i].strip() == code for i in code_columns):
                    found.add((to_number(row[gross]), to_number(row[cash])))
    return found


# One hospital per file layout: tall CSV, wide CSV and JSON.
for file_id, code in [
    ("bellevue-hospital-center", "71046"),
    ("jamaica-hospital-medical-center", "71046"),
    ("newyork-presbyterian-queens", "71046"),
]:
    raw = raw_prices(file_id, code)
    stored = set(
        con.execute(
            """SELECT i.gross_charge, i.cash_price FROM codes c JOIN items i USING (file_id, item_id)
               WHERE c.file_id = ? AND c.code = ? AND c.code_type = 'CPT/HCPCS'""",
            [file_id, code],
        ).fetchall()
    )
    check(f"prices for {code} at {file_id} match the raw file", raw == stored and len(raw) > 0,
          f"{len(raw)} distinct price pairs")

print(f"\n{sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
