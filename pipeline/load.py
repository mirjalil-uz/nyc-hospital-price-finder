"""Step 3: convert every raw price file into the same three tables.

Hospitals publish in one of three layouts defined by the federal template:
a "tall" CSV (one row per item and insurance plan), a "wide" CSV (one column
group per insurance plan) or JSON. Whatever the layout, this script writes:

  items  one row per billable item and setting, with its list and cash price
  codes  the billing codes attached to each item (CPT, HCPCS, MS-DRG, ...)
  rates  the price negotiated with each insurance plan for each item

Each table is saved as one Parquet file per hospital file, so a single
hospital can be reloaded without touching the others.

Run:  python pipeline/load.py            (files not converted yet)
      python pipeline/load.py --force    (reconvert everything)
      python pipeline/load.py --only bellevue-hospital-center
"""

import argparse
import csv
import io
import json
import re
import sys
import time

import duckdb
import ijson
import pyarrow as pa
import pyarrow.parquet as pq

from paths import PARQUET, RAW, REGISTRY

TABLES = ("items", "codes", "rates", "files")

ITEM_SCHEMA = pa.schema(
    [
        ("file_id", pa.string()),
        ("item_id", pa.uint64()),
        ("description", pa.string()),
        ("setting", pa.string()),
        ("modifiers", pa.string()),
        ("drug_unit", pa.string()),
        ("drug_type", pa.string()),
        ("gross_charge", pa.float64()),
        ("cash_price", pa.float64()),
        ("min_charge", pa.float64()),
        ("max_charge", pa.float64()),
    ]
)
CODE_SCHEMA = pa.schema(
    [("file_id", pa.string()), ("item_id", pa.uint64()), ("code_type", pa.string()), ("code", pa.string())]
)
RATE_SCHEMA = pa.schema(
    [
        ("file_id", pa.string()),
        ("item_id", pa.uint64()),
        ("payer_name", pa.string()),
        ("plan_name", pa.string()),
        ("negotiated_dollar", pa.float64()),
        ("negotiated_percentage", pa.float64()),
        ("negotiated_algorithm", pa.string()),
        ("estimated_amount", pa.float64()),
        ("methodology", pa.string()),
    ]
)


def find_raw(file_id):
    """The data file for a registry entry: a direct download or the biggest file from its zip."""
    for ext in ("csv", "json"):
        path = RAW / f"{file_id}.{ext}"
        if path.exists():
            return path
    folder = RAW / file_id
    if folder.is_dir():
        inside = [p for p in folder.rglob("*") if p.suffix.lower() in (".csv", ".json")]
        if inside:
            return max(inside, key=lambda p: p.stat().st_size)
    return None


def sniff(path):
    """(layout, text encoding) from the first bytes of the file."""
    with path.open("rb") as f:
        head = f.read(1 << 16)
    encoding = "utf-8"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        # A multi-byte character cut off at the end of the sample is not an error.
        if e.start < len(head) - 4:
            encoding = "latin-1"
    if head.lstrip(b"\xef\xbb\xbf \r\n\t")[:1] in (b"{", b"["):
        return "json", encoding
    return "csv", encoding


def to_number(value):
    """Prices arrive as numbers or as text like '$1,234.50'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------- JSON files


def json_metadata(path, encoding):
    """Hospital name, date and template version, read from either end of the file."""
    size = path.stat().st_size
    with path.open("rb") as f:
        text = f.read(1 << 16).decode(encoding, "replace")
        f.seek(max(0, size - (1 << 16)))
        text += f.read().decode(encoding, "replace")
    meta = {}
    for key in ("hospital_name", "last_updated_on", "version"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', text)
        meta[key] = m.group(1) if m else None
    return meta


class ParquetSink:
    """Collects rows and writes them to a Parquet file in batches."""

    def __init__(self, path, schema, batch=200_000):
        self.writer = pq.ParquetWriter(path, schema, compression="zstd")
        self.schema, self.batch, self.rows, self.count = schema, batch, [], 0

    def add(self, row):
        self.rows.append(row)
        if len(self.rows) >= self.batch:
            self.flush()

    def flush(self):
        if self.rows:
            columns = list(zip(*self.rows))
            arrays = [pa.array(col, type=field.type) for col, field in zip(columns, self.schema)]
            self.writer.write_table(pa.Table.from_arrays(arrays, schema=self.schema))
            self.count += len(self.rows)
            self.rows = []

    def close(self):
        self.flush()
        self.writer.close()


def load_json(file_id, path, encoding, out):
    items = ParquetSink(out["items"], ITEM_SCHEMA)
    codes = ParquetSink(out["codes"], CODE_SCHEMA)
    rates = ParquetSink(out["rates"], RATE_SCHEMA)
    item_id = 0
    with path.open("rb") as f:
        # Some files start with a byte-order mark, which is not valid JSON.
        if f.read(3) != b"\xef\xbb\xbf":
            f.seek(0)
        for entry in ijson.items(f, "standard_charge_information.item", use_float=True):
            description = clean_text(entry.get("description"))
            drug = entry.get("drug_information") or {}
            entry_codes = [
                (clean_text(c.get("type")), clean_text(c.get("code")))
                for c in entry.get("code_information") or []
                if clean_text(c.get("code"))
            ]
            for charge in entry.get("standard_charges") or []:
                item_id += 1
                modifiers = charge.get("modifiers")
                if isinstance(modifiers, list):
                    modifiers = "|".join(str(m) for m in modifiers)
                items.add(
                    (
                        file_id,
                        item_id,
                        description,
                        clean_text(charge.get("setting")),
                        clean_text(modifiers),
                        clean_text(drug.get("unit")),
                        clean_text(drug.get("type")),
                        to_number(charge.get("gross_charge")),
                        to_number(charge.get("discounted_cash")),
                        to_number(charge.get("minimum")),
                        to_number(charge.get("maximum")),
                    )
                )
                for code_type, code in entry_codes:
                    codes.add((file_id, item_id, code_type, code))
                for payer in charge.get("payers_information") or []:
                    rates.add(
                        (
                            file_id,
                            item_id,
                            clean_text(payer.get("payer_name")),
                            clean_text(payer.get("plan_name")),
                            to_number(payer.get("standard_charge_dollar")),
                            to_number(payer.get("standard_charge_percentage")),
                            clean_text(payer.get("standard_charge_algorithm")),
                            to_number(payer.get("estimated_amount", payer.get("median_amount"))),
                            clean_text(payer.get("methodology")),
                        )
                    )
    for sink in (items, codes, rates):
        sink.close()
    return json_metadata(path, encoding), {"items": items.count, "codes": codes.count, "rates": rates.count}


# ----------------------------------------------------------------- CSV files


def csv_header(path, encoding):
    """The template puts file metadata in rows 1-2 and the column names in row 3."""
    with path.open("r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f)
        meta_names, meta_values, columns = next(reader), next(reader), next(reader)
    meta = {k.strip().lower(): v.strip() for k, v in zip(meta_names, meta_values) if k.strip()}
    return meta, columns


def q(name):
    """Quote a column name for SQL."""
    return '"' + name.replace('"', '""') + '"'


def num(expr):
    return f"try_cast(replace(replace(trim({expr}), '$', ''), ',', '') AS DOUBLE)"


def txt(expr):
    return f"nullif(trim({expr}), '')"


def load_csv(file_id, path, encoding, out):
    meta, columns = csv_header(path, encoding)
    # Column names are matched case-insensitively and ignoring stray spaces.
    by_key = {}
    for col in columns:
        by_key.setdefault(re.sub(r"\s*\|\s*", "|", col.strip().lower()), col)

    def col(key):
        return q(by_key[key]) if key in by_key else "NULL"

    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    read = """
        CREATE TEMP TABLE src AS
        SELECT * FROM read_csv(?, skip = 2, header = true, all_varchar = true, null_padding = true,
                               delim = ',', quote = '"', escape = '"',
                               strict_mode = false, encoding = ?, max_line_size = 20000000)
        """
    try:
        con.execute(read, [str(path), encoding])
    except duckdb.InvalidInputException as e:
        # The sample looked like UTF-8 but a later line is not.
        if "utf-8" not in str(e).lower() or encoding == "latin-1":
            raise
        con.execute(read, [str(path), "latin-1"])
    # read_csv de-duplicates and trims header names; map our keys onto what it produced.
    actual = [r[0] for r in con.execute("DESCRIBE src").fetchall()]
    by_key = {}
    for name in actual:
        by_key.setdefault(re.sub(r"\s*\|\s*", "|", name.strip().lower()), name)

    code_numbers = sorted(
        int(m.group(1)) for k in by_key if (m := re.fullmatch(r"code\|(\d+)", k))
    )
    setting = col("setting")
    identity = [col("description"), setting, col("modifiers"), col("standard_charge|gross"),
                col("standard_charge|discounted_cash"), col("drug_unit_of_measurement"),
                col("drug_type_of_measurement")]
    identity += [col(f"code|{n}") for n in code_numbers] + [col(f"code|{n}|type") for n in code_numbers]
    key = "hash(" + ", ".join(f"coalesce({c}, '')" for c in identity) + ")"
    con.execute(f"ALTER TABLE src ADD COLUMN item_id UBIGINT")
    con.execute(f"UPDATE src SET item_id = {key}")

    con.execute(
        f"""
        COPY (
            SELECT ? AS file_id, item_id,
                   any_value({txt(col('description'))}) AS description,
                   any_value({txt(setting)}) AS setting,
                   any_value({txt(col('modifiers'))}) AS modifiers,
                   any_value({txt(col('drug_unit_of_measurement'))}) AS drug_unit,
                   any_value({txt(col('drug_type_of_measurement'))}) AS drug_type,
                   any_value({num(col('standard_charge|gross'))}) AS gross_charge,
                   any_value({num(col('standard_charge|discounted_cash'))}) AS cash_price,
                   min({num(col('standard_charge|min'))}) AS min_charge,
                   max({num(col('standard_charge|max'))}) AS max_charge
            FROM src GROUP BY item_id
        ) TO '{out["items"].as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """,
        [file_id],
    )

    code_selects = [
        f"SELECT item_id, {txt(col(f'code|{n}|type'))} AS code_type, {txt(col(f'code|{n}'))} AS code FROM src"
        for n in code_numbers
    ] or ["SELECT NULL::UBIGINT AS item_id, NULL::VARCHAR AS code_type, NULL::VARCHAR AS code WHERE false"]
    con.execute(
        f"""
        COPY (
            SELECT DISTINCT ? AS file_id, item_id, code_type, code
            FROM ({' UNION ALL '.join(code_selects)}) WHERE code IS NOT NULL
        ) TO '{out["codes"].as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """,
        [file_id],
    )

    if "payer_name" in by_key:
        layout = "csv-tall"
        estimated = col("estimated_amount") if "estimated_amount" in by_key else col("median_amount")
        rate_sql = f"""
            SELECT item_id, {txt(col('payer_name'))} AS payer_name, {txt(col('plan_name'))} AS plan_name,
                   {num(col('standard_charge|negotiated_dollar'))} AS negotiated_dollar,
                   {num(col('standard_charge|negotiated_percentage'))} AS negotiated_percentage,
                   {txt(col('standard_charge|negotiated_algorithm'))} AS negotiated_algorithm,
                   {num(estimated)} AS estimated_amount,
                   {txt(col('standard_charge|methodology'))} AS methodology
            FROM src WHERE {txt(col('payer_name'))} IS NOT NULL
        """
    else:
        layout = "csv-wide"
        # Columns look like standard_charge|<payer>|<plan>|negotiated_dollar.
        plans = {}
        for k, name in by_key.items():
            parts = k.split("|")
            if len(parts) == 4 and parts[0] == "standard_charge":
                plans.setdefault((parts[1], parts[2]), {})[parts[3]] = name
            elif len(parts) == 3 and parts[0] in ("estimated_amount", "median_amount"):
                plans.setdefault((parts[1], parts[2]), {})["estimated"] = name
        # Payer and plan names keep their original capitalisation from the header.
        original = {}
        for name in actual:
            parts = [p.strip() for p in name.split("|")]
            if len(parts) == 4 and parts[0].lower() == "standard_charge":
                original[(parts[1].lower(), parts[2].lower())] = (parts[1], parts[2])
        selects = []
        for (payer, plan), cols in plans.items():
            payer_name, plan_name = original.get((payer, plan), (payer, plan))
            c = lambda kind: q(cols[kind]) if kind in cols else "NULL"
            present = [q(v) for v in cols.values()]
            selects.append(
                f"""
                SELECT item_id, '{payer_name.replace("'", "''")}' AS payer_name,
                       '{plan_name.replace("'", "''")}' AS plan_name,
                       {num(c('negotiated_dollar'))} AS negotiated_dollar,
                       {num(c('negotiated_percentage'))} AS negotiated_percentage,
                       {txt(c('negotiated_algorithm'))} AS negotiated_algorithm,
                       {num(c('estimated'))} AS estimated_amount,
                       {txt(c('methodology'))} AS methodology
                FROM src WHERE {' OR '.join(f"{txt(p)} IS NOT NULL" for p in present)}
                """
            )
        rate_sql = " UNION ALL ".join(selects) or (
            "SELECT NULL::UBIGINT AS item_id, NULL AS payer_name, NULL AS plan_name, NULL::DOUBLE AS negotiated_dollar,"
            " NULL::DOUBLE AS negotiated_percentage, NULL AS negotiated_algorithm, NULL::DOUBLE AS estimated_amount,"
            " NULL AS methodology WHERE false"
        )
    con.execute(
        f"""
        COPY (SELECT ? AS file_id, * FROM ({rate_sql}))
        TO '{out["rates"].as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """,
        [file_id],
    )

    counts = {
        t: con.execute(f"SELECT count(*) FROM '{out[t].as_posix()}'").fetchone()[0]
        for t in ("items", "codes", "rates")
    }
    counts["source_rows"] = con.execute("SELECT count(*) FROM src").fetchone()[0]
    con.close()
    return {**meta, "layout": layout}, counts


# ---------------------------------------------------------------------- main


def convert(file_id, force):
    out = {t: PARQUET / t / f"{file_id}.parquet" for t in TABLES}
    info_path = PARQUET / "files" / f"{file_id}.json"
    if info_path.exists() and not force:
        return None
    path = find_raw(file_id)
    if path is None:
        return f"skip  {file_id}: not downloaded"
    for t in TABLES:
        (PARQUET / t).mkdir(parents=True, exist_ok=True)
    layout, encoding = sniff(path)
    started = time.time()
    if layout == "json":
        meta, counts = load_json(file_id, path, encoding, out)
        meta["layout"] = "json"
    else:
        meta, counts = load_csv(file_id, path, encoding, out)
    info = {
        "file_id": file_id,
        "raw_file": path.name,
        "raw_bytes": path.stat().st_size,
        "layout": meta.get("layout"),
        "hospital_name_in_file": meta.get("hospital_name"),
        "last_updated_on": meta.get("last_updated_on"),
        "template_version": meta.get("version"),
        **counts,
    }
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return (
        f"ok    {file_id:55s} {info['layout']:8s} items={counts['items']:>9,} "
        f"rates={counts['rates']:>11,} {time.time() - started:6.0f}s"
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()

    file_ids = sorted({row["file_id"] for row in csv.DictReader(REGISTRY.open(encoding="utf-8"))})
    for file_id in file_ids:
        if args.only and file_id not in args.only:
            continue
        try:
            message = convert(file_id, args.force or bool(args.only))
        except Exception as e:
            message = f"FAIL  {file_id}: {type(e).__name__}: {str(e)[:300]}"
        if message:
            print(message, flush=True)


if __name__ == "__main__":
    main()
