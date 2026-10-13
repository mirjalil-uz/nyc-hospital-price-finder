"""Step 4: clean the converted files and build the DuckDB database.

Reads the Parquet files written by load.py and creates prices.duckdb with:

  hospitals         one row per NYC hospital, with its price file and file date
  items             every billable item, cleaned
  codes             billing codes per item, in a standard format
  rates             negotiated prices per insurance plan, de-duplicated
  procedure_prices  one row per hospital file, billing code and setting, with
                    list, cash and negotiated price ranges (what the app compares)
  payer_prices      the same, split by insurance company
  procedures        every comparable billing code with its best description
  quality           what the cleaning changed, per hospital file

Nothing is invented or estimated: a price that is missing in the hospital's
file stays missing here.

Run:  python pipeline/build.py
      python pipeline/build.py --hospitals-only   (after discover.py changed names, addresses or ratings)
"""

import argparse
import csv
import json
import os
import sys
import time

import duckdb

from paths import DATABASE, DATA, PARQUET, REGISTRY

# Billing code systems that mean the same thing at every hospital. Hospital-internal
# codes (CDM, LOCAL) and revenue codes (RC) cannot be compared across hospitals.
COMPARABLE = ("CPT/HCPCS", "MS-DRG", "APR-DRG")

# Insurance company names are spelled many ways; the first matching pattern wins.
PAYER_GROUPS = [
    (r"healthfirst|health first", "Healthfirst"),
    (r"fidelis", "Fidelis Care"),
    (r"metro ?plus", "MetroPlus"),
    (r"1199", "1199SEIU"),
    (r"aetna", "Aetna"),
    (r"cigna", "Cigna"),
    (r"oxford|united ?health|^united|^uhc|\buhc\b|optum|umr", "UnitedHealthcare / Oxford"),
    (r"empire|anthem|bcbs|blue ?cross|blue ?shield|health ?plus", "Anthem / Empire BCBS"),
    (r"emblem|^hip\b|^ghi\b|\bhip\b|\bghi\b", "EmblemHealth (HIP / GHI)"),
    (r"well ?care", "Wellcare"),
    (r"humana", "Humana"),
    (r"magna", "MagnaCare"),
    (r"multi ?plan", "MultiPlan"),
    (r"affinity|molina", "Molina / Affinity"),
    (r"amida", "Amida Care"),
    (r"elderplan", "Elderplan"),
    (r"\bvns", "VNS Health"),
    (r"oscar", "Oscar"),
    (r"carelon", "Carelon"),
    (r"centers plan", "Centers Plan for Healthy Living"),
    (r"village ?care", "VillageCare"),
    (r"meritain", "Meritain Health"),
    (r"\bmvp\b", "MVP Health Care"),
    (r"center ?light", "CenterLight"),
    (r"hamaspik", "Hamaspik"),
    (r"medicaid", "Medicaid"),
    (r"medicare", "Medicare"),
    (r"tricare|champva|veteran", "Tricare / VA"),
    (r"workers|no[- ]?fault", "Workers' Comp / No-Fault"),
]


# One insurer sells very different kinds of plan, and hospitals are paid very differently for each.
# The kind is read from the plan's name; the first matching pattern wins.
PLAN_TYPES = [
    (r"medicare|\bmapd\b|\bdsnp\b|d-snp|dual", "Medicare Advantage"),
    (r"essential plan|\bep ?[1-4]\b|essential", "Essential Plan"),
    (r"child health|\bchp\b|chplus", "Child Health Plus"),
    (r"medicaid|\bmltc\b|\bharp\b|managed long|\bfida\b|\bsnp\b|family health|\bmmc\b", "Medicaid"),
    (r"exchange|marketplace|\bqhp\b|qualified health|individual|ny state of health|nysoh|bronze|silver|gold|platinum",
     "Marketplace (individual)"),
    (r"worker|no[- ]?fault|\bauto\b", "Workers' comp / No-fault"),
]
DEFAULT_PLAN_TYPE = "Commercial / employer"
# A line priced (or paid) at less than this fraction of the hospital's top line for the same code is
# treated as covering only part of the service, such as the doctor's fee, and is left out of comparisons.
PARTIAL_LINE = 4


def plan_type_sql(plan_column, payer_column):
    text = f"lower(coalesce({plan_column}, '') || ' ' || coalesce({payer_column}, ''))"
    cases = " ".join(
        f"WHEN regexp_matches({text}, '{pattern}') THEN '{name.replace(chr(39), chr(39) * 2)}'"
        for pattern, name in PLAN_TYPES
    )
    return f"CASE {cases} ELSE '{DEFAULT_PLAN_TYPE}' END"


def payer_group_sql(column):
    cases = " ".join(
        f"WHEN regexp_matches(lower({column}), '{pattern}') THEN '{name.replace(chr(39), chr(39) * 2)}'"
        for pattern, name in PAYER_GROUPS
    )
    return f"CASE {cases} ELSE trim({column}) END"


# Codes are written inconsistently ('3' and '003' are the same MS-DRG).
CODE_SQL = """
    CASE
        WHEN code_type IN ('MS-DRG', 'APR-DRG') AND regexp_matches(code, '^[0-9]{1,3}$') THEN lpad(code, 3, '0')
        WHEN code_type = 'RC' AND regexp_matches(code, '^[0-9]{1,4}$') THEN lpad(code, 4, '0')
        ELSE code
    END
"""


def parquet_files(table, file_ids):
    """SQL for reading one table across the fully converted hospital files."""
    paths = ", ".join(f"'{(PARQUET / table / f'{f}.parquet').as_posix()}'" for f in sorted(file_ids))
    return f"read_parquet([{paths}])"


def load_hospitals(con, loaded):
    """(Re)create the hospitals table from the registry: names, addresses and Medicare ratings."""
    con.execute(
        """CREATE OR REPLACE TABLE hospitals (
               hospital_id VARCHAR, hospital VARCHAR, system VARCHAR, borough VARCHAR, address VARCHAR,
               phone VARCHAR, latitude DOUBLE, longitude DOUBLE,
               patient_stars INTEGER, patient_recommend_pct INTEGER, patient_surveys INTEGER,
               medicare_stars INTEGER, medicare_rated_as VARCHAR,
               file_id VARCHAR, source_url VARCHAR, has_prices BOOLEAN)"""
    )

    def whole(text):
        return int(text) if text else None

    for row in csv.DictReader(REGISTRY.open(encoding="utf-8")):
        con.execute(
            "INSERT INTO hospitals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [row["hospital_id"], row["hospital"], row["system"], row["borough"], row["address"] or None,
             row["phone"] or None,
             float(row["latitude"]) if row["latitude"] else None,
             float(row["longitude"]) if row["longitude"] else None,
             whole(row["patient_stars"]), whole(row["patient_recommend_pct"]), whole(row["patient_surveys"]),
             whole(row["medicare_stars"]), row["medicare_rated_as"] or None,
             row["file_id"], row["mrf_url"], row["file_id"] in loaded],
        )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    started = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--hospitals-only", action="store_true",
                        help="refresh hospital names, addresses and ratings without rebuilding the prices")
    args = parser.parse_args()
    infos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((PARQUET / "files").glob("*.json"))]
    loaded = {i["file_id"] for i in infos}
    if args.hospitals_only:
        con = duckdb.connect(str(DATABASE))
        in_database = {r[0] for r in con.execute("SELECT file_id FROM files").fetchall()}
        load_hospitals(con, in_database)
        con.close()
        print(f"refreshed the hospitals table in {DATABASE}")
        return
    building = DATABASE.with_suffix(".building")
    if building.exists():
        building.unlink()
    con = duckdb.connect(str(building))
    con.execute(f"SET temp_directory = '{(DATA / 'tmp').as_posix()}'")
    con.execute("SET preserve_insertion_order = false")

    # ---- hospitals and their files
    load_hospitals(con, loaded)
    con.execute(
        """CREATE TABLE files (file_id VARCHAR, layout VARCHAR, hospital_name_in_file VARCHAR,
                               last_updated_text VARCHAR, last_updated DATE, template_version VARCHAR,
                               raw_bytes BIGINT)"""
    )
    for i in infos:
        con.execute(
            """INSERT INTO files VALUES (?, ?, ?, ?, coalesce(try_strptime(?, '%Y-%m-%d'), try_strptime(?, '%m/%d/%Y'),
                                         try_strptime(?, '%m-%d-%Y'), try_strptime(?, '%Y/%m/%d'))::DATE, ?, ?)""",
            [i["file_id"], i["layout"], i["hospital_name_in_file"], i["last_updated_on"]]
            + [i["last_updated_on"]] * 4
            + [i["template_version"], i["raw_bytes"]],
        )

    # ---- items: tidy text, standard setting names, no impossible prices
    con.execute(
        f"""
        CREATE TABLE items AS
        SELECT file_id, item_id,
               regexp_replace(trim(description), '\\s+', ' ', 'g') AS description,
               CASE WHEN lower(setting) IN ('inpatient', 'outpatient', 'both') THEN lower(setting) END AS setting,
               nullif(trim(modifiers), '') AS modifiers,
               drug_unit, drug_type,
               CASE WHEN gross_charge > 0 THEN gross_charge END AS gross_charge,
               CASE WHEN cash_price > 0 THEN cash_price END AS cash_price,
               CASE WHEN min_charge > 0 THEN min_charge END AS min_charge,
               CASE WHEN max_charge > 0 THEN max_charge END AS max_charge
        FROM {parquet_files("items", loaded)}
        ORDER BY file_id, item_id
        """
    )
    con.execute(
        f"""
        CREATE TABLE codes AS
        SELECT DISTINCT file_id, item_id, code_type, {CODE_SQL} AS code
        FROM (SELECT file_id, item_id, upper(trim(code)) AS code,
                     -- CPT codes are one part of HCPCS, and hospitals label them either way.
                     CASE WHEN upper(trim(code_type)) IN ('CPT', 'HCPCS') THEN 'CPT/HCPCS'
                          ELSE upper(trim(code_type)) END AS code_type
              FROM {parquet_files("codes", loaded)})
        WHERE code_type IS NOT NULL AND code <> ''
        ORDER BY file_id, item_id
        """
    )

    # ---- rates: one hospital file at a time keeps memory use flat
    con.execute(
        """CREATE TABLE rates (file_id VARCHAR, item_id UBIGINT, payer_name VARCHAR, plan_name VARCHAR,
                               payer_group VARCHAR, plan_type VARCHAR,
                               negotiated_dollar DOUBLE, negotiated_percentage DOUBLE,
                               negotiated_algorithm VARCHAR, estimated_amount DOUBLE, methodology VARCHAR)"""
    )
    con.execute(
        """CREATE TABLE quality (file_id VARCHAR, raw_rates BIGINT, rates_kept BIGINT, duplicate_rates_removed BIGINT,
                                 rates_without_any_price BIGINT, nonpositive_rates_blanked BIGINT)"""
    )
    for i in infos:
        path = (PARQUET / "rates" / f"{i['file_id']}.parquet").as_posix()
        raw, no_price, nonpositive = con.execute(
            f"""SELECT count(*),
                       count(*) FILTER (negotiated_dollar IS NULL AND negotiated_percentage IS NULL
                                        AND negotiated_algorithm IS NULL AND estimated_amount IS NULL),
                       count(*) FILTER (negotiated_dollar <= 0)
                FROM '{path}'"""
        ).fetchone()
        con.execute(
            f"""
            INSERT INTO rates
            SELECT DISTINCT file_id, item_id, trim(payer_name), trim(plan_name), {payer_group_sql('payer_name')},
                   {plan_type_sql('plan_name', 'payer_name')},
                   CASE WHEN negotiated_dollar > 0 THEN negotiated_dollar END,
                   CASE WHEN negotiated_percentage > 0 THEN negotiated_percentage END,
                   negotiated_algorithm,
                   CASE WHEN estimated_amount > 0 THEN estimated_amount END,
                   lower(methodology)
            FROM '{path}'
            WHERE payer_name IS NOT NULL
              AND NOT (negotiated_dollar IS NULL AND negotiated_percentage IS NULL
                       AND negotiated_algorithm IS NULL AND estimated_amount IS NULL)
            ORDER BY item_id
            """
        )
        kept = con.execute("SELECT count(*) FROM rates WHERE file_id = ?", [i["file_id"]]).fetchone()[0]
        con.execute(
            "INSERT INTO quality VALUES (?, ?, ?, ?, ?, ?)",
            [i["file_id"], raw, kept, raw - no_price - kept, no_price, nonpositive],
        )
        print(f"rates {i['file_id']:60s} {kept:>11,} kept of {raw:>11,}", flush=True)

    # ---- comparison tables
    # A code can appear on several lines (for example with a billing modifier for the
    # doctor's fee only). Lines without a modifier describe the standard service, so
    # they are used when a hospital has any; otherwise all of its lines are used.
    comparable = ", ".join(f"'{c}'" for c in COMPARABLE)
    con.execute(
        """CREATE TEMP TABLE item_rate AS
           SELECT file_id, item_id, median(negotiated_dollar) AS line_rate
           FROM rates WHERE negotiated_dollar IS NOT NULL GROUP BY ALL"""
    )
    # Some hospitals file a part of a service (often the doctor's fee) under the same code as the
    # whole service. Such a line is far cheaper than the hospital's main line for that code, either
    # in its own price or, when it has no price of its own, in what insurers pay on it. It is marked
    # partial and left out of every comparison, so that nobody is drawn to a price for half a service.
    con.execute(
        f"""
        CREATE TEMP TABLE lines AS
        WITH standard AS (
            SELECT c.file_id, c.code_type, c.code, coalesce(i.setting, 'not stated') AS setting, i.item_id,
                   i.description, i.gross_charge, i.cash_price, i.modifiers IS NULL AS plain,
                   coalesce(i.cash_price, i.gross_charge) AS own_price, r.line_rate
            FROM codes c JOIN items i USING (file_id, item_id) LEFT JOIN item_rate r USING (file_id, item_id)
            WHERE c.code_type IN ({comparable})
            QUALIFY plain OR NOT bool_or(plain) OVER (PARTITION BY c.file_id, c.code_type, c.code, setting)
        )
        SELECT *,
               coalesce(own_price * {PARTIAL_LINE} < max(own_price) OVER same_code, false)
               OR coalesce(own_price IS NULL AND line_rate * {PARTIAL_LINE} < max(line_rate) OVER same_code, false)
                   AS partial
        FROM standard
        WINDOW same_code AS (PARTITION BY file_id, code_type, code)
        """
    )
    con.execute(
        """
        CREATE TABLE procedure_prices AS
        WITH negotiated AS (
            SELECT l.file_id, l.code_type, l.code, l.setting,
                   min(r.negotiated_dollar) AS negotiated_min,
                   median(r.negotiated_dollar) AS negotiated_median,
                   max(r.negotiated_dollar) AS negotiated_max,
                   count(DISTINCT r.payer_name || '|' || coalesce(r.plan_name, ''))
                       FILTER (r.negotiated_dollar IS NOT NULL) AS plans_with_price
            FROM lines l JOIN rates r USING (file_id, item_id)
            WHERE NOT l.partial
            GROUP BY ALL
        ),
        left_out AS (
            SELECT file_id, code_type, code, setting, count(*) AS partial_lines
            FROM lines WHERE partial GROUP BY ALL
        )
        SELECT l.file_id, l.code_type, l.code, l.setting,
               mode(l.description) AS description,
               count(*) AS line_items,
               coalesce(any_value(o.partial_lines), 0) AS partial_lines,
               NOT bool_or(l.plain) AS modifier_lines_only,
               min(l.gross_charge) AS gross_min, max(l.gross_charge) AS gross_max,
               min(l.cash_price) AS cash_min, max(l.cash_price) AS cash_max,
               any_value(n.negotiated_min) AS negotiated_min,
               any_value(n.negotiated_median) AS negotiated_median,
               any_value(n.negotiated_max) AS negotiated_max,
               coalesce(any_value(n.plans_with_price), 0) AS plans_with_price
        FROM lines l
        LEFT JOIN negotiated n USING (file_id, code_type, code, setting)
        LEFT JOIN left_out o USING (file_id, code_type, code, setting)
        WHERE NOT l.partial
        GROUP BY ALL
        ORDER BY code_type, code, file_id
        """
    )
    con.execute(
        """
        CREATE TABLE payer_prices AS
        SELECT l.file_id, l.code_type, l.code, l.setting, r.payer_group, r.plan_type,
               min(r.negotiated_dollar) AS negotiated_min,
               median(r.negotiated_dollar) AS negotiated_median,
               max(r.negotiated_dollar) AS negotiated_max,
               count(DISTINCT coalesce(r.plan_name, '')) AS plans
        FROM lines l JOIN rates r USING (file_id, item_id)
        WHERE r.negotiated_dollar IS NOT NULL AND NOT l.partial
        GROUP BY ALL
        ORDER BY code_type, code, payer_group, file_id
        """
    )
    # The description used for a code is the one most hospital systems use for it.
    # Counting systems, not hospitals, stops one large system's wording from always winning.
    con.execute(
        """
        CREATE TABLE procedures AS
        WITH priced AS (
            SELECT p.code_type, p.code, p.description, h.system, h.hospital_id
            FROM procedure_prices p JOIN hospitals h USING (file_id)
            WHERE p.gross_min IS NOT NULL OR p.cash_min IS NOT NULL OR p.negotiated_min IS NOT NULL
        ),
        names AS (
            SELECT code_type, code, mode(description) AS description
            FROM (SELECT DISTINCT code_type, code, system, description FROM priced)
            GROUP BY ALL
        )
        SELECT code_type, code, any_value(n.description) AS description,
               count(DISTINCT hospital_id) AS hospitals
        FROM priced JOIN names n USING (code_type, code)
        GROUP BY ALL
        ORDER BY hospitals DESC, code
        """
    )
    con.execute("CHECKPOINT")
    for table in ("hospitals", "files", "items", "codes", "rates", "procedure_prices", "payer_prices", "procedures"):
        print(f"{table:18s} {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>13,}")
    con.close()
    # The finished file replaces the old one in a single step. Windows refuses while the app has the
    # old file open, so in that case the new file is kept and the message says what to do.
    try:
        os.replace(building, DATABASE)
    except PermissionError:
        print(f"The app is using {DATABASE.name}. Stop the app, then rename {building.name} to {DATABASE.name}.")
        return
    print(f"built {DATABASE} ({DATABASE.stat().st_size / 1e9:.1f} GB) in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
