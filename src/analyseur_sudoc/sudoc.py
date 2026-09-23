"""Collecte SRU paginée, reprise locale et contrôle d'exhaustivité."""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import unquote_plus

import httpx
from lxml import etree

ENDPOINT = "https://www.sudoc.abes.fr/cbs/sru/"
SRU = "http://www.loc.gov/zing/srw/"
DIAG = "http://www.loc.gov/zing/srw/diagnostic/"
NS = {"s": SRU, "d": DIAG}
COLLECTOR_VERSION = "0.2.0"


class SruError(ValueError):
    """Réponse SRU inexploitable, y compris sous HTTP 200."""

    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class Page:
    total: int
    ppns: tuple[str, ...]


def now():
    return datetime.now(timezone.utc).isoformat()


def build_query(year: int, prefix: str) -> str:
    if type(year) is not int or not 1000 <= year <= 9999:
        raise ValueError("L'année doit comporter quatre chiffres (1000–9999)")
    if prefix not in tuple("0123456789"):
        raise ValueError("Préfixe PPN attendu : un chiffre de 0 à 9")
    return f"ppn={prefix}* and apu={year} and (tdo=b or tdo=x)"


def request_params(query, start, page_size):
    return {"operation": "searchRetrieve", "version": "1.1",
            "recordSchema": "unimarc", "recordPacking": "xml", "query": query,
            "startRecord": start, "maximumRecords": page_size}


def parse_page(raw: bytes, start: int, page_size: int, query=None) -> Page:
    """Valide l'enveloppe, les positions et les PPN, sans parser les données métier."""
    try:
        root = etree.fromstring(raw, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, recover=False))
    except etree.XMLSyntaxError as exc:
        raise SruError(f"XML invalide : {exc}") from exc
    if root.getroottree().docinfo.doctype:
        raise SruError("DTD inattendue dans une réponse SRU")
    if root.tag != f"{{{SRU}}}searchRetrieveResponse":
        raise SruError("Réponse searchRetrieveResponse absente")
    # CBS renvoie également un diagnostic 1/0 vide sur des réponses réussies.
    for uri in root.findall(".//d:uri", NS):
        code = (uri.text or "").strip()
        if code == "info:srw/diagnostic/1/0":
            continue
        parent = uri.getparent()
        detail = parent.findtext("d:details", default="", namespaces=NS)
        message = parent.findtext("d:message", default="", namespaces=NS)
        if (code == "info:srw/diagnostic/1/61" and start == 1
                and root.findtext("s:numberOfRecords", namespaces=NS) == "0"
                and not root.findall("s:records/s:record", NS)):
            continue  # CBS signale aussi une position hors limites pour zéro résultat.
        raise SruError(f"Diagnostic SRU {code} : {detail} {message}".strip(),
                       retryable=code == "info:srw/diagnostic/1/2" and detail != "IMPOSSIBLE_ADI")
    if query is not None:
        echoed = root.findtext("s:echoedSearchRetrieveRequest/s:query", namespaces=NS)
        if echoed is None or unquote_plus(echoed).strip() != query:
            raise SruError("La requête renvoyée par le serveur diffère de la requête demandée")
    value = root.findtext("s:numberOfRecords", namespaces=NS)
    if value is None or not re.fullmatch(r"[0-9]+", value.strip()):
        raise SruError("numberOfRecords absent ou invalide")
    total = int(value)
    records = root.findall("s:records/s:record", NS)
    if len(records) > page_size or start + len(records) - 1 > total:
        raise SruError("Nombre de notices incohérent avec la page demandée")
    if not records and start <= total:
        raise SruError("Page vide avant la fin annoncée des résultats")
    ppns = []
    for offset, record in enumerate(records):
        position = record.findtext("s:recordPosition", namespaces=NS)
        if position is None or position.strip() != str(start + offset):
            raise SruError(f"Position SRU inattendue : {position!r}, attendu {start + offset}")
        if record.findtext("s:recordSchema", namespaces=NS) != "unimarc":
            raise SruError("Schéma de notice différent d'unimarc")
        if record.findtext("s:recordPacking", namespaces=NS) != "xml":
            raise SruError("Encapsulation de notice différente de xml")
        data = record.find("s:recordData", NS)
        children = [] if data is None else [child for child in data if isinstance(child.tag, str)]
        if len(children) != 1 or etree.QName(children[0]).localname != "record":
            raise SruError("Notice UNIMARC absente ou multiple")
        # Le Sudoc renvoie actuellement les champs MARC sans espace de noms.
        identifiers = children[0].xpath('./*[local-name()="controlfield"][@tag="001"]/text()')
        if len(identifiers) != 1 or not re.fullmatch(r"[0-9]{8}[0-9X]", identifiers[0].strip()):
            raise SruError("PPN 001 absent, multiple ou invalide")
        ppns.append(identifiers[0].strip())
    next_position = root.findtext("s:nextRecordPosition", namespaces=NS)
    if next_position and next_position.strip() not in ("0", str(start + len(ppns))):
        raise SruError("nextRecordPosition incohérent : risque de saut de notices")
    return Page(total, tuple(ppns))


def write_bytes(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def write_json(path: Path, payload):
    write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def download_page(client, run_dir, prefix, query, start, page_size, *, delay, sleep):
    """Conserve les réponses rejetées et réessaie seulement les erreurs transitoires."""
    for attempt in range(3):
        sleep(delay)
        response = None
        try:
            response = client.get(ENDPOINT, params=request_params(query, start, page_size))
            response.raise_for_status()
            page = parse_page(response.content, start, page_size, query)
            return response.content, page
        except (httpx.HTTPError, SruError) as exc:
            if response is not None:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                write_bytes(run_dir / "rejected" / f"{prefix}-{start:09d}-{stamp}.xml", response.content)
            if isinstance(exc, SruError):
                retryable = exc.retryable
            elif isinstance(exc, httpx.HTTPStatusError):
                retryable = exc.response.status_code in (429, 500, 502, 503, 504)
            else:
                retryable = isinstance(exc, httpx.TransportError)
            if not retryable or attempt == 2:
                raise
            wait = 2 ** attempt
            if response is not None:
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = max(wait, min(int(retry_after), 60))
            sleep(wait)
    raise AssertionError("Boucle de tentatives terminée sans résultat")


def collect_sudoc(client: httpx.Client, run_dir: Path, *, year=2025, page_size=200,
                  max_records=2000, max_pages=None, delay=0.5, sleep=time.sleep,
                  progress: Callable[[str], None] | None = None):
    """Rejoue le cache validé puis poursuit la collecte ; écrit report.json à chaque page.

    max_pages limite le nombre total de pages de la campagne, pages en cache incluses.
    max_records borne la campagne entière, pages en cache incluses. Retirer
    max_pages poursuit un essai sans dépasser ce plafond immuable.
    """
    queries = {prefix: build_query(year, prefix) for prefix in "0123456789"}
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records doit être un entier positif")
    if type(page_size) is not int or not 1 <= page_size <= 1000:
        raise ValueError("Taille de page attendue : 1 à 1000")
    if max_pages is not None and (type(max_pages) is not int or max_pages < 1):
        raise ValueError("max_pages doit être positif")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    settings = {"year_requested": year, "tdo_requested": ["b", "x"], "endpoint": ENDPOINT,
                "sru_version": "1.1", "record_schema": "unimarc", "page_size": page_size,
                "queries": queries, "collector_version": COLLECTOR_VERSION,
                "max_records": max_records}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(manifest.get(key) != value for key, value in settings.items()):
            raise ValueError("Paramètres différents de la campagne existante (année, taille de page, plafond ou version)")
    else:
        if any(run_dir.iterdir()):
            raise ValueError("Un nouveau dossier de campagne doit être vide")
        manifest = {**settings, "collection_id": run_dir.name, "collection_date": now()}
        write_json(manifest_path, manifest)
    report = {**manifest, "status": "running", "complete": False, "max_pages": max_pages,
              "physical_only_requested": True, "scope_validation": "pending_unimarc_validation",
              "pages_validated": 0, "records_downloaded": 0, "records_validated": 0,
              "records_parsed": None, "records_loaded": None, "distinct_ppns": 0,
              "sru_number_of_records": None, "announced_records_known_partitions": 0,
              "missing_records_known_partitions": 0, "errors": [], "partitions": []}
    seen = set()

    def save_report():
        parts = report["partitions"]
        known = [part for part in parts if part["number_of_records"] is not None]
        report["announced_records_known_partitions"] = sum(part["number_of_records"] for part in known)
        report["missing_records_known_partitions"] = sum(
            part["number_of_records"] - part["records_validated"] for part in known)
        if len(known) == len(queries):
            report["sru_number_of_records"] = report["announced_records_known_partitions"]
        report["distinct_ppns"] = len(seen)
        report["updated_at"] = now()
        write_json(run_dir / "report.json", report)

    save_report()
    try:
        for prefix, query in queries.items():
            part = {"prefix": prefix, "query": query, "number_of_records": None,
                    "records_validated": 0, "complete": False, "pages": []}
            report["partitions"].append(part)
            start = 1
            while True:
                remaining = max_records - report["records_validated"]
                if remaining <= 0:
                    report["status"] = "limited"
                    report["limit_reason"] = "max_records"
                    save_report()
                    return report
                requested_size = min(page_size, remaining)
                if max_pages is not None and report["pages_validated"] >= max_pages:
                    report["status"] = "limited"
                    report["limit_reason"] = "max_pages"
                    save_report()
                    return report
                path = run_dir / "pages" / prefix / f"{start:09d}.xml"
                metadata_path = path.with_suffix(".json")
                if path.exists() and metadata_path.exists():
                    raw = path.read_bytes()
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if metadata.get("sha256") != hashlib.sha256(raw).hexdigest():
                        raise SruError(f"Page en cache modifiée : {path}")
                    if metadata.get("params") != request_params(query, start, requested_size):
                        raise SruError(f"Paramètres du cache incohérents : {path}")
                    page = parse_page(raw, start, requested_size, query)
                else:
                    raw, page = download_page(client, run_dir, prefix, query, start, requested_size,
                                              delay=delay, sleep=sleep)
                    metadata = {"retrieved_at": now(), "params": request_params(query, start, requested_size),
                                "sha256": hashlib.sha256(raw).hexdigest()}
                    write_bytes(path, raw)
                    write_json(metadata_path, metadata)
                # Le XML reçu est conservé même si son contrôle inter-pages échoue.
                report["records_downloaded"] += len(page.ppns)
                if part["number_of_records"] is None:
                    part["number_of_records"] = page.total
                elif page.total != part["number_of_records"]:
                    raise SruError(f"Le total SRU du préfixe {prefix} a changé : "
                                   f"{part['number_of_records']} → {page.total}. Nouvelle campagne nécessaire.")
                if any(not ppn.startswith(prefix) for ppn in page.ppns):
                    raise SruError(f"PPN en dehors du préfixe demandé {prefix}")
                if len(set(page.ppns)) != len(page.ppns) or seen.intersection(page.ppns):
                    raise SruError(f"PPN dupliqués à la page {prefix}/{start} : exhaustivité non garantie")
                seen.update(page.ppns)
                part["records_validated"] += len(page.ppns)
                report["records_validated"] += len(page.ppns)
                report["pages_validated"] += 1
                part["pages"].append({"file": path.relative_to(run_dir).as_posix(),
                                      "start": start, "count": len(page.ppns), **metadata})
                start += len(page.ppns)
                part["complete"] = part["records_validated"] == page.total
                save_report()
                if progress:
                    progress(f"PPN {prefix}* : {part['records_validated']}/{page.total} ; "
                             f"total validé : {report['records_validated']}")
                if part["complete"]:
                    break
        report["status"] = "complete"
        report["complete"] = True
    except (OSError, ValueError, httpx.HTTPError) as exc:
        report["status"] = "failed"
        report["errors"].append(str(exc))
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        report["errors"].append("Collecte interrompue ; relancer avec le même dossier")
    save_report()
    return report
