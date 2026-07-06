#!/usr/bin/env python3
"""
Robust rewrite of CloudflareCIDR-main.py:
- download zip to a temporary directory
- extract safely
- locate `as/*/ipv4-aggregated.txt` files for specified ASNs
- validate IPv4 CIDR entries using ipaddress
- write outputs to Clash/CloudflareCIDR.list and CloudflareCIDR.txt
- log progress and failures, avoid uncaught FileNotFoundError
"""
import sys
import logging
import tempfile
import zipfile
from pathlib import Path
import requests
import ipaddress

# Config
URL = "https://github.com/ipverse/asn-ip/archive/refs/heads/master.zip"
INCLUDED_ASNS = {'209242', '13335', '149648', '132892', '139242', '202623', '203898', '394536'}
TIMEOUT = 30  # seconds for requests

# Output paths
CLASH_DIR = Path("Clash")
CLASH_FILE = CLASH_DIR / "CloudflareCIDR.list"
CIDR_FILE = Path("CloudflareCIDR.txt")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

def download_zip(dest: Path) -> None:
    logging.info("Downloading %s -> %s", URL, dest)
    resp = requests.get(URL, timeout=TIMEOUT)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    logging.info("Downloaded %d bytes", dest.stat().st_size)

def find_extracted_root(extract_dir: Path) -> Path | None:
    # Prefer a single top-level folder; fallback to any folder containing 'asn-ip' in name
    entries = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(entries) == 1:
        return entries[0]
    for p in entries:
        if "asn-ip" in p.name:
            return p
    # fallback: try to find 'as' subdir anywhere
    for p in extract_dir.rglob("as"):
        if p.is_dir():
            return p.parent
    return None

def collect_ips(as_root: Path) -> set:
    """
    Locate the 'as' directory under as_root and collect ipv4-aggregated.txt
    for included ASNs.
    """
    result = set()
    as_dir = as_root / "as"
    if not as_dir.exists():
        # try to find 'as' dir recursively
        found = list(as_root.rglob("as"))
        if found:
            as_dir = found[0]
        else:
            raise FileNotFoundError(f"No 'as' directory found under {as_root}")
    logging.info("Searching AS directory: %s", as_dir)
    for child in as_dir.iterdir():
        if not child.is_dir():
            continue
        asn = child.name.strip()
        if asn not in INCLUDED_ASNS:
            continue
        file_path = child / "ipv4-aggregated.txt"
        if not file_path.exists():
            logging.warning("Expected file missing: %s", file_path)
            continue
        logging.info("Reading %s (ASN %s)", file_path, asn)
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result.add(line)
    return result

def validate_cidrs(entries: set) -> list:
    valid = []
    for e in sorted(entries):
        try:
            net = ipaddress.ip_network(e, strict=False)
            if net.version != 4:
                logging.debug("Skipping non-IPv4 network: %s", e)
                continue
            valid.append(str(net))
        except Exception:
            logging.warning("Invalid CIDR ignored: %s", e)
    # dedupe and keep stable order
    seen = set()
    out = []
    for n in valid:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out

def write_outputs(cidr_list: list) -> None:
    CLASH_DIR.mkdir(parents=True, exist_ok=True)
    logging.info("Writing %d CIDRs to %s and %s", len(cidr_list), CLASH_FILE, CIDR_FILE)
    with CLASH_FILE.open("w", encoding="utf-8") as cf, CIDR_FILE.open("w", encoding="utf-8") as tf:
        for cidr in cidr_list:
            cf.write(f"IP-CIDR,{cidr},no-resolve\n")
            tf.write(f"{cidr}\n")

def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as td:
            tempdir = Path(td)
            zip_path = tempdir / "asn-ip-master.zip"
            download_zip(zip_path)
            logging.info("Extracting zip to %s", tempdir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tempdir)
            root = find_extracted_root(tempdir)
            if root is None:
                logging.error("Could not locate extracted repository root under %s", tempdir)
                return 1
            logging.info("Using extracted root: %s", root)
            raw_entries = collect_ips(root)
            logging.info("Collected %d raw entries", len(raw_entries))
            cidrs = validate_cidrs(raw_entries)
            logging.info("%d valid IPv4 CIDR entries", len(cidrs))
            write_outputs(cidrs)
        logging.info("Done.")
        return 0
    except requests.RequestException as e:
        logging.exception("Network/download error: %s", e)
        return 2
    except FileNotFoundError as e:
        logging.exception("File error: %s", e)
        return 3
    except zipfile.BadZipFile as e:
        logging.exception("Bad zip file: %s", e)
        return 4
    except Exception as e:
        logging.exception("Unexpected error: %s", e)
        return 5

if __name__ == "__main__":
    sys.exit(main())
