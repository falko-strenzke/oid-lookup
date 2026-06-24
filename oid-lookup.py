#!/usr/bin/env python3
"""
oid_lookup.py - Looks up an OID (dot notation) on https://oid-base.com

Usage:
    python3 oid_lookup.py <OID>

Example:
    python3 oid_lookup.py 1.3.6.1.4.1.259.10.1.24.1.5.6.6.1
    ->
    iso(1) identified-organization(3) dod(6) internet(1) private(4) enterprise(1) 259 edgecorenetworks(10) edgeCoreNetworksMgt(1) ecs4510MIB(24) ecs4510MIBObjects(1) staMgt(5) xstMgt(6) mstInstanceEditTable(6) mstInstanceEditEntry(1)
    mstInstanceEditEntry

The page https://oid-base.com/get/<OID> is fetched. The web page contains
the full, named path of the OID, among other places, in the <title> tag
in the form:

    OID repository - <oid> = {iso(1) identified-organization(3) ... name(n)}

This path is extracted via regex. If the extraction fails (e.g. because
the OID is not present in the database, or due to a network/HTTP error),
the script produces NO output and exits with exit code -1.

Note: POSIX exit codes are limited to one byte. sys.exit(-1) is therefore
seen by the operating system as exit code 255 (standard Python/Unix
behavior, due to the 0-255 limitation).
"""

import html
import re
import sys
import urllib.error
import urllib.request

BASE_URL = "https://oid-base.com/get/"
USER_AGENT = "Mozilla/5.0 (compatible; oid-lookup-script/1.0)"
TIMEOUT_SECONDS = 10

# Extracts the full path from the <title> tag:
#   OID repository - <oid> = {<full path>}
TITLE_RE = re.compile(
    r"<title>\s*OID repository\s*-\s*[\d.]+\s*=\s*\{(.*?)\}\s*</title>",
    re.IGNORECASE | re.DOTALL,
)

# Fallback: extracts the full path from the body location "OID: {<path>}"
BODY_RE = re.compile(r"\bOID:\s*\{([^}]*)\}", re.IGNORECASE)

# Splits the last path element into name and node number, e.g.:
#   "mstInstanceEditTable(6)" -> ("mstInstanceEditTable", "6")
LAST_ELEMENT_RE = re.compile(r"^(.*)\((\d+)\)$")


def fetch_oid_page(oid):
    """Downloads the OID page. Returns the HTML source, or None if the
    page could not be loaded successfully."""
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
    """Extracts the full, named OID path from the page's HTML.
    Returns the path string, or None if the OID was not found or the
    expected format is not present."""
    match = TITLE_RE.search(page_html) or BODY_RE.search(page_html)
    if not match:
        return None

    full_path = html.unescape(match.group(1)).strip()
    if not full_path:
        return None

    return full_path


def lookup_oid(oid):
    """Performs the complete lookup of an OID.
    Returns a tuple (full_path, last_element_name), or None if the OID
    could not be found."""
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
        print(f"Usage: {sys.argv[0]} <OID in dot notation>", file=sys.stderr)
        return -1

    oid = sys.argv[1].strip()

    result = lookup_oid(oid)
    if result is None:
        # OID not found (or fetch error): no output, exit code -1
        return -1

    full_path, last_name = result
    print(full_path)
    print(last_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
