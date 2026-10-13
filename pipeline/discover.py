"""Step 1: find every NYC hospital's published price file.

Federal rules require each hospital website to host a small text file at
/cms-hpt.txt that lists the hospital's locations and the URL of its
machine-readable price file (MRF). This script reads that index for every
hospital system in SYSTEMS, keeps the locations inside the five boroughs
(NYC_LOCATIONS), asks each MRF's server for its size, and writes the result
to data/registry.csv.

Run:  python pipeline/discover.py
"""

import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from paths import REGISTRY

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# Hospital system -> website domains to try for /cms-hpt.txt (first that works wins).
SYSTEMS = {
    "NYC Health + Hospitals": ["www.nychealthandhospitals.org"],
    "NYU Langone": ["nyulangone.org"],
    "NewYork-Presbyterian": ["www.nyp.org"],
    "Northwell Health": ["www.northwell.edu"],
    "Montefiore": ["montefioreeinstein.org", "www.montefiore.org"],
    "Memorial Sloan Kettering": ["www.mskcc.org"],
    "Hospital for Special Surgery": ["www.hss.edu"],
    "Maimonides": ["maimo.org", "www.maimonidesmed.org"],
    "BronxCare": ["www.bronxcare.org"],
    "SBH Health System": ["www.sbhny.org"],
    "The Brooklyn Hospital Center": ["www.tbh.org"],
    "Richmond University Medical Center": ["www.rumcsi.org"],
    "Jamaica Hospital": ["jamaicahospital.org"],
    "Flushing Hospital": ["flushinghospital.org"],
    "One Brooklyn Health": ["onebrooklynhealth.org", "www.onebrooklynhealth.org"],
    "SUNY Downstate": ["www.downstate.edu"],
    "St. John's Episcopal": ["ehs.org", "www.ehs.org"],
    "Calvary Hospital": ["www.calvaryhospital.org"],
}

# Sources that the automatic lookup cannot read, entered by hand.
# Mount Sinai's site blocks scripts; these come from its /cms-hpt.txt as seen in a browser on 2026-10-09.
_MS = "https://www.mountsinai.org/files/mrf/"
MANUAL = {
    "Mount Sinai": {
        "index_url": "https://www.mountsinai.org/cms-hpt.txt",
        "entries": {
            "Mount Sinai Hospital": _MS + "131624096_mount-sinai-hospital_standardcharges.json",
            "Mount Sinai Queens": _MS + "131624096_mount-sinai-queens_standardcharges.json",
            "Mount Sinai Brooklyn": _MS + "135564934_mount-sinai-brooklyn_standardcharges.json",
            "Mount Sinai Morningside": _MS + "132997301_mount-sinai-morningside_standardcharges.json",
            "Mount Sinai West": _MS + "132997301_mount-sinai-morningside_standardcharges.json",
            "New York Eye and Ear Infirmary of Mount Sinai": _MS
            + "135562304_new-york-eye-and-ear-infirmary-of-mount-sinai_standardcharges.json",
            "Mount Sinai Behavioral Health Center": _MS
            + "135564934_mount-sinai-behavioral-health-center_standardcharges.json",
        },
    },
    # Wyckoff has no index file; its website links to a pricing page that offers this download.
    "Wyckoff Heights": {
        "index_url": "https://www.cdmpricing.com/101527cba4e89fb2e982b5ed19f92364/standard-charges",
        "entries": {
            "Wyckoff Heights Medical Center": "https://apim.services.craneware.com/api-pricing-transparency"
            "/api/public/101527cba4e89fb2e982b5ed19f92364/charges/mrf",
        },
    },
}

# Hospital locations inside the five boroughs, as named in the indexes -> borough.
# Anything not listed here (suburban hospitals, outpatient-only centers) is dropped.
NYC_LOCATIONS = {
    "Bellevue Hospital Center": "Manhattan",
    "Elmhurst Hospital Center": "Queens",
    "Harlem Hospital Center": "Manhattan",
    "Henry J. Carter Specialty Hospital": "Manhattan",
    "Jacobi Medical Center": "Bronx",
    "Kings County Hospital Center": "Brooklyn",
    "Lincoln Medical Center": "Bronx",
    "Metropolitan Hospital Center": "Manhattan",
    "North Central Bronx": "Bronx",
    "Queens Hospital Center": "Queens",
    "South Brooklyn Health": "Brooklyn",
    "Woodhull Medical Center": "Brooklyn",
    "NYU Langone Tisch Hospital": "Manhattan",
    "NYU Langone Orthopedic Hospital": "Manhattan",
    "NYU Langone Hospital - Brooklyn": "Brooklyn",
    "NewYork-Presbyterian Columbia University Irving Medical Center": "Manhattan",
    "NewYork-Presbyterian Weill Cornell Medical Center": "Manhattan",
    "NewYork-Presbyterian Allen Hospital": "Manhattan",
    "NewYork-Presbyterian Lower Manhattan Hospital": "Manhattan",
    "NewYork-Presbyterian Brooklyn Methodist Hospital": "Brooklyn",
    "NewYork-Presbyterian Queens": "Queens",
    "Lenox Hill Hospital": "Manhattan",
    "Long Island Jewish Forest Hills": "Queens",
    "Long Island Jewish Medical Center": "Queens",
    "Cohen Children's Medical Center": "Queens",
    "Zucker Hillside Hospital": "Queens",
    "Staten Island University Hospital": "Staten Island",
    "Montefiore Medical Center Moses DIV": "Bronx",
    "Montefiore Medical Center – Jack D. Weiler (Einstein Campus)": "Bronx",
    "Montefiore Medical Center Wakefield": "Bronx",
    "Montefiore Medical Center Westchester Square": "Bronx",
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": "Bronx",
    "Memorial Sloan Kettering Cancer Center": "Manhattan",
    "Hospital for Special Surgery Main Hospital": "Manhattan",
    "Maimonides Medical Center": "Brooklyn",
    "BronxCare Hospital Center - Fulton Campus": "Bronx",
    "BronxCare Health System - BronxCare Hospital Center Concourse": "Bronx",
    "SBH Health System": "Bronx",
    "The Brooklyn Hospital Center": "Brooklyn",
    "richmonduniversitymedicalcenter": "Staten Island",
    "Jamaica Hospital Medical Center": "Queens",
    "Flushing Hospital Medical Center": "Queens",
    "Brookdale Hospital Medical Center": "Brooklyn",
    "Interfaith Medical Center": "Brooklyn",
    "Kingsbrook Jewish Medical Center": "Brooklyn",
    "SUNY Downstate Health Sciences University": "Brooklyn",
    "Episcopal Health Services": "Queens",
    "Calvary Hospital-Bronx": "Bronx",
    "Calvary Hospital-Brooklyn": "Brooklyn",
    "Mount Sinai Hospital": "Manhattan",
    "Mount Sinai Queens": "Queens",
    "Mount Sinai Brooklyn": "Brooklyn",
    "Mount Sinai Morningside": "Manhattan",
    "Mount Sinai West": "Manhattan",
    "New York Eye and Ear Infirmary of Mount Sinai": "Manhattan",
    "Mount Sinai Behavioral Health Center": "Manhattan",
    "Wyckoff Heights Medical Center": "Brooklyn",
}

# Street addresses come from the New York State health facility registry.
# Location name -> the state's facility id.
STATE_FACILITIES = "https://health.data.ny.gov/resource/vn5v-hh5r.json"
FACILITY_IDS = {
    "Bellevue Hospital Center": "1438",
    "Elmhurst Hospital Center": "1626",
    "Harlem Hospital Center": "1445",
    "Henry J. Carter Specialty Hospital": "1486",
    "Jacobi Medical Center": "1165",
    "Kings County Hospital Center": "1301",
    "Lincoln Medical Center": "1172",
    "Metropolitan Hospital Center": "1454",
    "North Central Bronx": "1186",
    "Queens Hospital Center": "1633",
    "South Brooklyn Health": "1294",
    "Woodhull Medical Center": "1692",
    "NYU Langone Tisch Hospital": "1463",
    "NYU Langone Orthopedic Hospital": "1446",
    "NYU Langone Hospital - Brooklyn": "1304",
    "NewYork-Presbyterian Columbia University Irving Medical Center": "1464",
    "NewYork-Presbyterian Weill Cornell Medical Center": "1458",
    "NewYork-Presbyterian Allen Hospital": "3975",
    "NewYork-Presbyterian Lower Manhattan Hospital": "1437",
    "NewYork-Presbyterian Brooklyn Methodist Hospital": "1306",
    "NewYork-Presbyterian Queens": "1637",
    "Lenox Hill Hospital": "1450",
    "Long Island Jewish Forest Hills": "1638",
    "Long Island Jewish Medical Center": "1630",
    "Staten Island University Hospital": "1740",
    "Montefiore Medical Center Moses DIV": "1169",
    "Montefiore Medical Center – Jack D. Weiler (Einstein Campus)": "3058",
    "Montefiore Medical Center Wakefield": "1168",
    "Montefiore Medical Center Westchester Square": "1185",
    "Memorial Sloan Kettering Cancer Center": "1453",
    "Hospital for Special Surgery Main Hospital": "1447",
    "Maimonides Medical Center": "1305",
    "BronxCare Hospital Center - Fulton Campus": "1164",
    "BronxCare Health System - BronxCare Hospital Center Concourse": "1178",
    "SBH Health System": "1176",
    "The Brooklyn Hospital Center": "1288",
    "richmonduniversitymedicalcenter": "1738",
    "Jamaica Hospital Medical Center": "1629",
    "Flushing Hospital Medical Center": "1628",
    "Brookdale Hospital Medical Center": "1286",
    "Interfaith Medical Center": "1309",
    "Kingsbrook Jewish Medical Center": "1315",
    "SUNY Downstate Health Sciences University": "1320",
    "Episcopal Health Services": "1635",
    "Calvary Hospital-Bronx": "1175",
    "Calvary Hospital-Brooklyn": "10223",
    "Mount Sinai Hospital": "1456",
    "Mount Sinai Queens": "1639",
    "Mount Sinai Brooklyn": "1324",
    "Mount Sinai Morningside": "1469",
    "Mount Sinai West": "1466",
    "New York Eye and Ear Infirmary of Mount Sinai": "1460",
    "Mount Sinai Behavioral Health Center": "15437",
    "Wyckoff Heights Medical Center": "1318",
}
# Hospitals the state lists under a parent hospital's licence, so they have no entry of their own.
MANUAL_ADDRESSES = {
    "Cohen Children's Medical Center": "269-01 76th Avenue, New Hyde Park, NY 11040",
    "Zucker Hillside Hospital": "75-59 263rd Street, Glen Oaks, NY 11004",
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": "3415 Bainbridge Avenue, Bronx, NY 10467",
}

# Main switchboard numbers, checked on 2026-10-11. No single public dataset is reliable
# for these (Medicare's file gives one number per licence, and some are wrong), so each
# number here was confirmed in at least one official source for that address: Medicare's
# hospital file, the federal provider registry (NPPES), or the hospital's own website.
PHONES = {
    "Bellevue Hospital Center": "(212) 562-4141",
    "Elmhurst Hospital Center": "(718) 334-4000",
    "Harlem Hospital Center": "(212) 939-1000",
    "Henry J. Carter Specialty Hospital": "(646) 686-0000",
    "Jacobi Medical Center": "(718) 918-5000",
    "Kings County Hospital Center": "(718) 245-3131",
    "Lincoln Medical Center": "(718) 579-5000",
    "Metropolitan Hospital Center": "(212) 423-6262",
    "North Central Bronx": "(718) 519-5000",
    "Queens Hospital Center": "(718) 883-3000",
    "South Brooklyn Health": "(718) 616-3000",
    "Woodhull Medical Center": "(718) 963-8000",
    "NYU Langone Tisch Hospital": "(212) 263-7300",
    "NYU Langone Orthopedic Hospital": "(212) 598-6000",
    "NYU Langone Hospital - Brooklyn": "(718) 630-7000",
    "NewYork-Presbyterian Columbia University Irving Medical Center": "(212) 305-2500",
    "NewYork-Presbyterian Weill Cornell Medical Center": "(212) 746-5454",
    "NewYork-Presbyterian Allen Hospital": "(212) 932-4000",
    "NewYork-Presbyterian Lower Manhattan Hospital": "(212) 312-5000",
    "NewYork-Presbyterian Brooklyn Methodist Hospital": "(718) 780-3000",
    "NewYork-Presbyterian Queens": "(718) 670-2000",
    "Lenox Hill Hospital": "(212) 434-2000",
    "Long Island Jewish Forest Hills": "(718) 830-4000",
    "Long Island Jewish Medical Center": "(718) 470-7000",
    "Cohen Children's Medical Center": "(718) 470-3000",
    "Zucker Hillside Hospital": "(718) 470-8100",
    "Staten Island University Hospital": "(718) 226-9000",
    "Montefiore Medical Center Moses DIV": "(718) 920-4321",
    "Montefiore Medical Center – Jack D. Weiler (Einstein Campus)": "(718) 904-2000",
    "Montefiore Medical Center Wakefield": "(718) 920-9000",
    "Montefiore Medical Center Westchester Square": "(718) 430-7300",
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": "(718) 741-2400",
    "Memorial Sloan Kettering Cancer Center": "(212) 639-2000",
    "Hospital for Special Surgery Main Hospital": "(212) 606-1000",
    "Maimonides Medical Center": "(718) 283-6000",
    "BronxCare Hospital Center - Fulton Campus": "(718) 590-1800",
    "BronxCare Health System - BronxCare Hospital Center Concourse": "(718) 590-1800",
    "SBH Health System": "(718) 960-9000",
    "The Brooklyn Hospital Center": "(718) 250-8000",
    "richmonduniversitymedicalcenter": "(718) 818-1234",
    "Jamaica Hospital Medical Center": "(718) 206-6000",
    "Flushing Hospital Medical Center": "(718) 670-5000",
    "Brookdale Hospital Medical Center": "(718) 240-5000",
    "Interfaith Medical Center": "(718) 613-4000",
    "Kingsbrook Jewish Medical Center": "(718) 604-5000",
    "SUNY Downstate Health Sciences University": "(718) 270-1000",
    "Episcopal Health Services": "(718) 869-7000",
    "Calvary Hospital-Bronx": "(718) 518-2000",
    "Calvary Hospital-Brooklyn": "(718) 630-6666",
    "Mount Sinai Hospital": "(212) 241-6500",
    "Mount Sinai Queens": "(718) 932-1000",
    "Mount Sinai Brooklyn": "(718) 252-3000",
    "Mount Sinai Morningside": "(212) 523-4000",
    "Mount Sinai West": "(212) 523-4000",
    "New York Eye and Ear Infirmary of Mount Sinai": "(212) 979-4000",
    "Mount Sinai Behavioral Health Center": "(332) 243-1600",
    "Wyckoff Heights Medical Center": "(718) 963-7272",
}

# Map positions the state registry does not give, placed by hand at the street address.
MANUAL_COORDINATES = {
    "Cohen Children's Medical Center": (40.7537, -73.7085),
    "Zucker Hillside Hospital": (40.7489, -73.7107),
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": (40.8805, -73.8786),
    "Montefiore Medical Center Moses DIV": (40.8802, -73.8795),
}

# Ratings come from Medicare. The patient rating is the HCAHPS survey, in which a random
# sample of recent patients reviews their stay (1 to 5 stars, plus the share who would
# definitely recommend the hospital). The overall quality rating also counts outcomes
# such as safety and readmissions.
# Medicare rates each licensed hospital once, so campuses that operate under one
# licence share a rating. Location name -> Medicare facility id (CCN).
# Not rated by Medicare: Memorial Sloan Kettering (cancer hospitals are exempt),
# Calvary and Henry J. Carter (long-term and specialty care).
CMS_HOSPITALS = "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
CMS_PATIENT_SURVEY = "https://data.cms.gov/provider-data/api/1/datastore/query/dgck-syfz/0"
RATING_COLUMNS = ("patient_stars", "patient_recommend_pct", "patient_surveys", "medicare_stars", "medicare_rated_as")
MEDICARE_IDS = {
    "Bellevue Hospital Center": "330204",
    "Elmhurst Hospital Center": "330128",
    "Harlem Hospital Center": "330240",
    "Jacobi Medical Center": "330127",
    "North Central Bronx": "330127",
    "Kings County Hospital Center": "330202",
    "Lincoln Medical Center": "330080",
    "Metropolitan Hospital Center": "330199",
    "Queens Hospital Center": "330231",
    "South Brooklyn Health": "330196",
    "Woodhull Medical Center": "330396",
    "NYU Langone Tisch Hospital": "330214",
    "NYU Langone Orthopedic Hospital": "330214",
    "NYU Langone Hospital - Brooklyn": "330214",
    "NewYork-Presbyterian Columbia University Irving Medical Center": "330101",
    "NewYork-Presbyterian Weill Cornell Medical Center": "330101",
    "NewYork-Presbyterian Allen Hospital": "330101",
    "NewYork-Presbyterian Lower Manhattan Hospital": "330101",
    "NewYork-Presbyterian Brooklyn Methodist Hospital": "330101",
    "NewYork-Presbyterian Queens": "330055",
    "Lenox Hill Hospital": "330119",
    "Long Island Jewish Forest Hills": "330195",
    "Long Island Jewish Medical Center": "330195",
    "Cohen Children's Medical Center": "330195",
    "Zucker Hillside Hospital": "330195",
    "Staten Island University Hospital": "330160",
    "Montefiore Medical Center Moses DIV": "330059",
    "Montefiore Medical Center – Jack D. Weiler (Einstein Campus)": "330059",
    "Montefiore Medical Center Wakefield": "330059",
    "Montefiore Medical Center Westchester Square": "330059",
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": "330059",
    "Hospital for Special Surgery Main Hospital": "330270",
    "Maimonides Medical Center": "330194",
    "BronxCare Hospital Center - Fulton Campus": "330009",
    "BronxCare Health System - BronxCare Hospital Center Concourse": "330009",
    "SBH Health System": "330399",
    "The Brooklyn Hospital Center": "330056",
    "richmonduniversitymedicalcenter": "330028",
    "Jamaica Hospital Medical Center": "330014",
    "Flushing Hospital Medical Center": "330193",
    "Brookdale Hospital Medical Center": "330233",
    "Interfaith Medical Center": "330233",
    "Kingsbrook Jewish Medical Center": "330233",
    "SUNY Downstate Health Sciences University": "330350",
    "Episcopal Health Services": "330395",
    "Mount Sinai Hospital": "330024",
    "Mount Sinai Queens": "330024",
    "Mount Sinai Brooklyn": "330169",
    "Mount Sinai Behavioral Health Center": "330169",
    "Mount Sinai Morningside": "330046",
    "Mount Sinai West": "330046",
    "New York Eye and Ear Infirmary of Mount Sinai": "330100",
    "Wyckoff Heights Medical Center": "330221",
}

# Clearer display names for locations whose index name is unhelpful.
DISPLAY_NAMES = {
    "richmonduniversitymedicalcenter": "Richmond University Medical Center",
    "Episcopal Health Services": "St. John's Episcopal Hospital",
    "North Central Bronx": "North Central Bronx Hospital",
    "SBH Health System": "SBH Health System (St. Barnabas Hospital)",
    "Montefiore Medical Center Moses DIV": "Montefiore Medical Center - Moses Campus",
    "Montefiore Medical Center – Jack D. Weiler (Einstein Campus)": "Montefiore Medical Center - Weiler (Einstein) Campus",
    "Montefiore Medical Center Wakefield": "Montefiore Medical Center - Wakefield Campus",
    "Montefiore Medical Center Westchester Square": "Montefiore Medical Center - Westchester Square",
    "Montefiore Medical Center – Children’s Hospital at Montefiore Einstein": "Children's Hospital at Montefiore Einstein",
    "BronxCare Health System - BronxCare Hospital Center Concourse": "BronxCare Hospital Center - Concourse Campus",
    "Calvary Hospital-Bronx": "Calvary Hospital - Bronx",
    "Calvary Hospital-Brooklyn": "Calvary Hospital - Brooklyn",
    "SUNY Downstate Health Sciences University": "SUNY Downstate (University Hospital of Brooklyn)",
}


def parse_index(text):
    """Turn a cms-hpt.txt body into a list of {location-name, mrf-url, ...} dicts."""
    entries, current = [], {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, sep, value = line.partition(":")
        if sep:
            current[key.strip().lower()] = value.strip()
    if current:
        entries.append(current)
    return [e for e in entries if e.get("mrf-url")]


def fetch_index(system, domains):
    last = ""
    for domain in domains:
        url = f"https://{domain}/cms-hpt.txt"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            last = f"{url}: {type(e).__name__}"
            continue
        r.encoding = r.apparent_encoding or "utf-8"
        entries = parse_index(r.text) if r.ok else []
        if entries:
            return system, url, entries, ""
        last = f"{url}: HTTP {r.status_code}, no entries"
    return system, "", [], last


def file_size(url):
    """(size in bytes or None, content type) as reported by the server."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if r.ok and int(r.headers.get("content-length") or 0) > 0:
            return int(r.headers["content-length"]), r.headers.get("content-type", "")
        # Some servers refuse HEAD; ask for the first byte only instead.
        r = requests.get(url, headers={**HEADERS, "Range": "bytes=0-0"}, timeout=30, stream=True)
        total = r.headers.get("content-range", "").rpartition("/")[2]
        r.close()
        if total.isdigit():
            return int(total), r.headers.get("content-type", "")
        return None, r.headers.get("content-type", "") if r.ok else f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return None, type(e).__name__


def fetch_addresses():
    """Location name -> {address, latitude, longitude} for every hospital in NYC_LOCATIONS."""
    ids = ", ".join(f"'{i}'" for i in sorted(set(FACILITY_IDS.values())))
    r = requests.get(
        STATE_FACILITIES,
        params={"$where": f"fac_id in ({ids})", "$limit": 1000,
                "$select": "fac_id,address1,city,fac_zip,latitude,longitude"},
        timeout=60,
    )
    r.raise_for_status()
    by_id = {
        f["fac_id"]: {
            "address": f"{f['address1'].strip()}, {f['city'].strip()}, NY {f['fac_zip'].strip()[:5]}",
            "latitude": f.get("latitude", ""),
            "longitude": f.get("longitude", ""),
        }
        for f in r.json()
    }
    places = {name: dict(by_id.get(fac_id, {})) for name, fac_id in FACILITY_IDS.items()}
    for name, address in MANUAL_ADDRESSES.items():
        places[name] = {"address": address}
    for name, (latitude, longitude) in MANUAL_COORDINATES.items():
        places[name].update(latitude=latitude, longitude=longitude)
    return places


def cms_rows(url, measure=None):
    """New York rows of a Medicare dataset, keyed by facility id."""
    params = {"conditions[0][property]": "state", "conditions[0][value]": "NY",
              "conditions[0][operator]": "=", "limit": 500}
    if measure:
        params.update({"conditions[1][property]": "hcahps_measure_id", "conditions[1][value]": measure,
                       "conditions[1][operator]": "="})
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return {f["facility_id"]: f for f in r.json()["results"]}


def fetch_ratings():
    """Location name -> rating columns for the registry (blank where Medicare has no value)."""
    overall = cms_rows(CMS_HOSPITALS)
    survey_stars = cms_rows(CMS_PATIENT_SURVEY, "H_STAR_RATING")
    recommend = cms_rows(CMS_PATIENT_SURVEY, "H_RECMND_DY")

    def number(row, field):
        value = (row or {}).get(field, "")
        return value if value.isdigit() else ""

    ratings = {}
    for name, ccn in MEDICARE_IDS.items():
        if ccn not in overall:
            continue
        ratings[name] = {
            "patient_stars": number(survey_stars.get(ccn), "patient_survey_star_rating"),
            "patient_recommend_pct": number(recommend.get(ccn), "hcahps_answer_percent"),
            "patient_surveys": number(survey_stars.get(ccn), "number_of_completed_surveys"),
            "medicare_stars": number(overall[ccn], "hospital_overall_rating"),
            "medicare_rated_as": overall[ccn]["facility_name"].title(),
        }
    return ratings


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda kv: fetch_index(*kv), SYSTEMS.items()))
    for system, manual in MANUAL.items():
        entries = [{"location-name": n, "mrf-url": u} for n, u in manual["entries"].items()]
        results.append((system, manual["index_url"], entries, ""))

    addresses = fetch_addresses()
    ratings = fetch_ratings()
    rows, seen = [], set()
    for system, index_url, entries, error in results:
        if error:
            print(f"[no index] {system}: {error}")
        for e in entries:
            name = e.get("location-name", "").strip()
            if name not in NYC_LOCATIONS:
                continue
            seen.add(name)
            rows.append(
                {
                    "hospital_id": slug(DISPLAY_NAMES.get(name, name)),
                    "hospital": DISPLAY_NAMES.get(name, name),
                    "system": system,
                    "borough": NYC_LOCATIONS[name],
                    "address": addresses.get(name, {}).get("address", ""),
                    "phone": PHONES.get(name, ""),
                    "latitude": addresses.get(name, {}).get("latitude", ""),
                    "longitude": addresses.get(name, {}).get("longitude", ""),
                    **{c: ratings.get(name, {}).get(c, "") for c in RATING_COLUMNS},
                    "mrf_url": e["mrf-url"],
                    "index_url": index_url,
                }
            )
    for name in sorted(set(NYC_LOCATIONS) - seen):
        print(f"[missing] expected location not found in any index: {name}")

    # One file can cover several hospitals, so files get their own id.
    urls = sorted({r["mrf_url"] for r in rows})
    with ThreadPoolExecutor(8) as pool:
        sizes = dict(zip(urls, pool.map(file_size, urls)))
    first_hospital = {}
    for r in rows:
        first_hospital.setdefault(r["mrf_url"], r["hospital_id"])
    for r in rows:
        size, content_type = sizes[r["mrf_url"]]
        r["file_id"] = first_hospital[r["mrf_url"]]
        r["size_bytes"] = size if size is not None else ""
        r["content_type"] = content_type

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    known = sum(s for s, _ in sizes.values() if s)
    unknown = sum(1 for s, _ in sizes.values() if not s)
    print(f"{len(rows)} hospitals, {len(urls)} files, {known / 1e9:.1f} GB known, {unknown} files of unknown size")
    print(f"wrote {REGISTRY}")


if __name__ == "__main__":
    main()
