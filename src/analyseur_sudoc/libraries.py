"""Collecte et normalisation du référentiel national RCR."""

import csv
import io
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

LISTRCR_URL = "https://www.idref.fr/services/listrcr"
COLUMNS = {
    "RCR": "rcr", "LIBELLE": "label", "ILN": "iln", "PPN": "library_ppn",
    "VILLE": "city", "CDPOSTAL": "postal_code", "PAYS": "country",
    "LATITUDE": "latitude", "LONGITUDE": "longitude",
}


def normalize(value):
    if value is None:
        return None
    value = str(value).strip()
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1].strip()
    return None if not value or value.lower() == "null" else value


def parse_listrcr(raw: bytes, retrieved_at: str, warnings=None):
    """Refuse les lignes invalides ; conserve le fichier source séparément."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif b"\x00" in raw[:100]:
        text = raw.decode("utf-16-le")
    else:
        text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
        raise ValueError("Colonnes listrcr absentes ou format TSV invalide")
    rows, seen = [], {}
    for line, source in enumerate(reader, 2):
        if None in source or any(source[key] is None for key in COLUMNS):
            raise ValueError(f"Ligne {line} : nombre de colonnes invalide")
        row = {target: normalize(source[key]) for key, target in COLUMNS.items()}
        rcr, ppn = row["rcr"], row["library_ppn"]
        if not rcr or not re.fullmatch(r"[0-9]{9}", rcr):
            raise ValueError(f"Ligne {line} : RCR invalide {rcr!r}")
        if ppn and not re.fullmatch(r"[0-9]{8}[0-9X]", ppn):
            raise ValueError(f"Ligne {line} : PPN invalide {ppn!r}")
        for field, bound in (("latitude", 90), ("longitude", 180)):
            value = row[field]
            if value is not None:
                try:
                    value = float(value.replace(",", "."))
                except ValueError:
                    value = None
                if value is None or not math.isfinite(value) or abs(value) > bound:
                    if warnings is not None:
                        warnings.append({"line": line, "rcr": rcr, "field": field,
                                         "raw_value": row[field], "reason": "Coordonnée invalide"})
                    value = None
            row[field] = value
        row.update(library_type=None, metadata_retrieved_at=retrieved_at)
        if rcr in seen:
            existing = seen[rcr]
            conflicts = {field: [existing[field], row[field]] for field in COLUMNS.values()
                         if existing[field] != row[field]}
            if warnings is not None:
                warnings.append({"line": line, "rcr": rcr, "reason": "RCR dupliqué",
                                 "conflicts": conflicts})
            for field in conflicts:
                existing[field] = None
            continue
        seen[rcr] = row
        rows.append(row)
    if not rows:
        raise ValueError("Référentiel vide")
    return rows


def as_list(value):
    return value if isinstance(value, list) else [value]


def extract_library_type(payload):
    """IdRef utilise des objets ou des listes et des tags numériques."""
    if not isinstance(payload, dict) or not isinstance(payload.get("record"), dict):
        raise ValueError("Notice JSON IdRef invalide : record absent")
    fields = payload["record"].get("datafield", [])
    values = []
    for field in as_list(fields):
        if not isinstance(field, dict):
            raise ValueError("Champ IdRef invalide")
        if str(field.get("tag")) != "130":
            continue
        for subfield in as_list(field.get("subfield", [])):
            if not isinstance(subfield, dict):
                raise ValueError("Sous-zone IdRef invalide")
            if subfield.get("code") == "a":
                value = normalize(subfield.get("content"))
                if value and value not in values:
                    values.append(value)
    return " ; ".join(values) or None


def fetch(client, url, attempts=3, delay=0.2):
    for attempt in range(attempts):
        time.sleep(delay)
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in (429, 500, 502, 503, 504)
            if not retryable or attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def collect_references(client, run_dir: Path, source=None, limit=None, delay=0.2):
    """Une campagne conserve ses sources ; la même campagne peut être reprise."""
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "listrcr.tsv"
    manifest_path = run_dir / "manifest.json"
    if not raw_path.exists():
        raw = Path(source).read_bytes() if source else fetch(client, LISTRCR_URL, delay=delay)
        raw_path.write_bytes(raw)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"source": str(source) if source else LISTRCR_URL,
                    "retrieved_at": datetime.now(timezone.utc).isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    warnings = []
    rows = parse_listrcr(raw_path.read_bytes(), manifest["retrieved_at"], warnings)
    total = len(rows)
    if limit is not None:
        rows = rows[:limit]
    cache = run_dir / "idref"
    cache.mkdir(exist_ok=True)
    errors, results = [], {}
    for row in rows:
        ppn = row["library_ppn"]
        if ppn is None:
            continue
        if ppn not in results:
            path = cache / f"{ppn}.json"
            try:
                raw = path.read_bytes() if path.exists() else fetch(client, f"https://www.idref.fr/{ppn}.json", delay=delay)
                value = extract_library_type(json.loads(raw))
                if not path.exists():
                    path.write_bytes(raw)
                results[ppn] = (value, None)
            except (httpx.HTTPError, ValueError) as exc:
                results[ppn] = (None, str(exc))
        row["library_type"], error = results[ppn]
        if error:
            errors.append({"rcr": row["rcr"], "ppn": ppn, "error": error})
    typed = sum(row["library_type"] is not None for row in rows)
    report = {**manifest, "source_rows": total, "processed_rows": len(rows),
              "limited": limit is not None, "with_type": typed,
              "type_coverage_percent": round(100 * typed / len(rows), 2),
              "without_ppn": sum(row["library_ppn"] is None for row in rows),
              "without_type": len(rows) - typed, "warnings": warnings, "errors": errors}
    return rows, report
