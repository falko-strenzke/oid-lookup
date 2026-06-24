#!/usr/bin/env python3
"""
oid_lookup.py - Looks up an OID (dot notation) on https://oid-base.com

Usage:
    python3 oid_lookup.py [-a PATH] <OID>

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

Optional: -a / --append-to-dumpasn1-cfg PATH
    If given, the script checks whether the looked-up OID is already
    present in the dumpasn1.cfg file at PATH. If not, a new entry is
    appended in the format used by dumpasn1.cfg:

        OID = <oid as space-separated decimal numbers>
        Comment = <full_path>
        Description = <last_name>

    (dumpasn1.cfg stores OIDs as space-separated decimal numbers rather
    than dot notation, e.g. "1 2 840 113549 1 1" instead of
    "1.2.840.113549.1.1" - the dots are converted to spaces accordingly.)
    This only happens if the OID lookup itself succeeded.
"""

import argparse
import html
import os
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


def oid_to_dumpasn1_form(oid):
    """Converts an OID from dot notation to the space-separated decimal
    form used in dumpasn1.cfg, e.g. "1.2.840.113549.1.1" ->
    "1 2 840 113549 1 1"."""
    return oid.replace(".", " ")


def cfg_contains_oid(cfg_path, oid_dumpasn1_form):
    """Checks whether dumpasn1.cfg already contains an 'OID = ...' line
    matching oid_dumpasn1_form. Comparison is whitespace-tolerant.
    Returns False if the file does not exist yet."""
    target_tokens = oid_dumpasn1_form.split()

    try:
        with open(cfg_path, "r", encoding="utf-8") as cfg_file:
            for line in cfg_file:
                stripped = line.strip()
                if not stripped.startswith("OID"):
                    continue
                _, _, value = stripped.partition("=")
                if value.split() == target_tokens:
                    return True
    except FileNotFoundError:
        return False

    return False


def append_oid_entry(cfg_path, oid, full_path, last_name):
    """Appends a new OID entry to dumpasn1.cfg, unless an entry for this
    OID is already present. Returns True if an entry was appended, False
    if it was already present."""
    oid_dumpasn1_form = oid_to_dumpasn1_form(oid)

    if cfg_contains_oid(cfg_path, oid_dumpasn1_form):
        return False

    file_has_content = os.path.exists(cfg_path) and os.path.getsize(cfg_path) > 0

    entry = (
        "# added by oid_lookup.py\n"
        f"OID = {oid_dumpasn1_form}\n"
        f"Comment = {full_path}\n"
        f"Description = {last_name}\n"
    )
    if file_has_content:
        # Separate from the previous entry with a blank line, matching
        # the style used in the official dumpasn1.cfg file.
        entry = "\n" + entry

    with open(cfg_path, "a", encoding="utf-8") as cfg_file:
        cfg_file.write(entry)
    print("wrote new OID entry")
    return True


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Look up an OID (dot notation) on https://oid-base.com",
    )
    parser.add_argument(
        "oid",
        help="OID in dot notation, e.g. 1.3.6.1.4.1.259.10.1.24.1.5.6.6.1",
    )
    parser.add_argument(
        "-a",
        "--append-to-dumpasn1-cfg",
        metavar="PATH",
        dest="dumpasn1_cfg_path",
        help=(
            "Path to a dumpasn1.cfg file. If the OID is not yet present "
            "there, a new entry is appended for it."
        ),
    )
    return parser


def main():
    args = build_arg_parser().parse_args()

    oid = args.oid.strip()

    result = lookup_oid(oid)
    if result is None:
        # OID not found (or fetch error): no output, exit code -1
        return -1

    full_path, last_name = result

    if args.dumpasn1_cfg_path:
        try:
            append_oid_entry(args.dumpasn1_cfg_path, oid, full_path, last_name)
        except OSError as exc:
            print(
                f"Warning: could not update '{args.dumpasn1_cfg_path}': {exc}",
                file=sys.stderr,
            )

    print(full_path)
    print(last_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
