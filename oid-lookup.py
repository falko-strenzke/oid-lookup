#!/usr/bin/env python3
"""
oid_lookup.py - Schlaegt eine OID (Punktnotation) auf https://oid-base.com nach.

Verwendung:
    python3 oid_lookup.py <OID>

Beispiel:
    python3 oid_lookup.py 1.3.6.1.4.1.259.10.1.24.1.5.6.6.1
    ->
    iso(1) identified-organization(3) dod(6) internet(1) private(4) enterprise(1) 259 edgecorenetworks(10) edgeCoreNetworksMgt(1) ecs4510MIB(24) ecs4510MIBObjects(1) staMgt(5) xstMgt(6) mstInstanceEditTable(6) mstInstanceEditEntry(1)
    mstInstanceEditEntry

Es wird die Seite https://oid-base.com/get/<OID> abgerufen. Die Webseite
enthaelt den vollen, benannten Pfad der OID u.a. im <title>-Tag in der Form:

    OID repository - <oid> = {iso(1) identified-organization(3) ... name(n)}

Dieser Pfad wird per Regex extrahiert. Schlaegt die Extraktion fehl (z.B.
weil die OID nicht in der Datenbank vorhanden ist, oder bei einem Netzwerk-
/HTTP-Fehler), erzeugt das Skript KEINE Ausgabe und beendet sich mit dem
Exit Code -1.

Hinweis: POSIX-Exit-Codes sind auf ein Byte begrenzt. sys.exit(-1) wird vom
Betriebssystem daher als Exit Code 255 sichtbar (Standardverhalten von
Python/Unix, technisch bedingt durch die Limitierung auf 0-255).
"""

import html
import re
import sys
import urllib.error
import urllib.request

BASE_URL = "https://oid-base.com/get/"
USER_AGENT = "Mozilla/5.0 (compatible; oid-lookup-script/1.0)"
TIMEOUT_SECONDS = 10

# Extrahiert den vollen Pfad aus dem <title>-Tag:
#   OID repository - <oid> = {<voller Pfad>}
TITLE_RE = re.compile(
    r"<title>\s*OID repository\s*-\s*[\d.]+\s*=\s*\{(.*?)\}\s*</title>",
    re.IGNORECASE | re.DOTALL,
)

# Fallback: Extrahiert den vollen Pfad aus der Body-Stelle "OID: {<Pfad>}"
BODY_RE = re.compile(r"\bOID:\s*\{([^}]*)\}", re.IGNORECASE)

# Trennt das letzte Pfadelement in Name und Knotennummer, z.B.:
#   "mstInstanceEditTable(6)" -> ("mstInstanceEditTable", "6")
LAST_ELEMENT_RE = re.compile(r"^(.*)\((\d+)\)$")


def fetch_oid_page(oid):
    """Laedt die OID-Seite herunter. Gibt den HTML-Quelltext zurueck,
    oder None, falls die Seite nicht erfolgreich geladen werden konnte."""
    url = BASE_URL + oid
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return None
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def extract_full_path(page_html):
    """Extrahiert den vollen, benannten OID-Pfad aus dem HTML der Seite.
    Gibt den Pfad-String zurueck, oder None, wenn die OID nicht gefunden
    wurde bzw. das erwartete Format nicht vorliegt."""
    match = TITLE_RE.search(page_html) or BODY_RE.search(page_html)
    if not match:
        return None

    full_path = html.unescape(match.group(1)).strip()
    if not full_path:
        return None

    return full_path


def lookup_oid(oid):
    """Fuehrt das komplette Nachschlagen einer OID durch.
    Gibt ein Tupel (voller_pfad, letztes_element_name) zurueck,
    oder None, wenn die OID nicht gefunden werden konnte."""
    page_html = fetch_oid_page(oid)
    if page_html is None:
        return None

    full_path = extract_full_path(page_html)
    if full_path is None:
        return None

    elements = full_path.split()
    if not elements:
        return None

    last_element = elements[-1]
    last_match = LAST_ELEMENT_RE.match(last_element)
    last_name = last_match.group(1) if last_match else last_element

    return full_path, last_name


def main():
    if len(sys.argv) != 2:
        print(f"Verwendung: {sys.argv[0]} <OID in Punktnotation>", file=sys.stderr)
        return -1

    oid = sys.argv[1].strip()

    result = lookup_oid(oid)
    if result is None:
        # OID nicht gefunden (oder Fehler beim Abruf): keine Ausgabe, Exit Code -1
        return -1

    full_path, last_name = result
    print(full_path)
    print(last_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
