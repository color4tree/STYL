#!/usr/bin/env python3
"""Root-only logging migration, not a code deployment or general retention tool.

prepare pauses existing backup/report timers, waits for their jobs (never kills
mail), saves configuration, provisions capture, and exports all journal history.
cutover requires the operator to have built/activated the approved application.
retention requires a downloaded/re-upload-verified Records ZIP and an explicit
operator confirmation of live capture coverage. Only journald is then capped;
non-journal operational logs still require a separate inventory and review.

No phase deletes business archives, source records, or captured history. Failed
phases leave timers paused for investigation. Reuse the SAME protected release
directory for retries; never discard its backups/state/history manifest.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import uuid
import zipfile


SOURCE = Path(__file__).resolve().parent
LOGS = Path("/var/log/styl-website")
RECORDS = Path("/var/lib/styl-records")
ENV = Path("/etc/styl/styl.env")
CADDY = Path("/etc/caddy/Caddyfile")
SNIPPET = Path("/etc/caddy/website-logging.caddy")
JOURNAL = Path("/etc/systemd/journald.conf.d/60-styl-operational.conf")
TOOLS = Path("/usr/local/lib/styl")
SYSTEMD = Path("/etc/systemd/system")
TIMERS = ("styl-backup.timer", "styl-analytics-report.timer")
SERVICES = ("styl-api.service", "styl-web.service", "caddy.service")
UNITS = (*SERVICES, "styl-backup.service", "styl-analytics-report.service", *TIMERS)
SOURCE_FILES = (
    "install-records-logging.py",
    "capture_website_logs.py", "backup.sh", "check_logging_install.py",
    "styl-api.service", "styl-web.service", "styl-backup.service",
    "styl-analytics-report.service", "caddy-website-logs.conf",
    "website-logging.caddy", "journald-operational.conf",
)
CONFIGS = (
    ENV, CADDY, SNIPPET, JOURNAL,
    SYSTEMD / "caddy.service.d/website-logs.conf",
    *(SYSTEMD / name for name in UNITS),
    TOOLS / "capture_website_logs.py", TOOLS / "backup.sh",
)
CUTOVER_CONFIGS = (
    CADDY, SNIPPET, SYSTEMD / "caddy.service.d/website-logs.conf",
    *(SYSTEMD / name for name in ("styl-api.service", "styl-web.service", "styl-analytics-report.service")),
)
CHUNK = 1024 * 1024
MAX_BYTES = 100 * 1024**3
HASH = re.compile(r"[a-f0-9]{64}")
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


class Refused(ValueError):
    """A safe, fixed diagnostic; never include file contents or subprocess output."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def utcstamp():
    return datetime.now(timezone.utc).isoformat()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON fields.")
        result[key] = value
    return result


def load_json(data):
    return json.loads(data, object_pairs_hook=unique_object)


def digest(source, limit=MAX_BYTES):
    checksum, size = hashlib.sha256(), 0
    while chunk := source.read(min(CHUNK, limit - size + 1)):
        size += len(chunk)
        require(size <= limit, "File exceeds verification limit.")
        checksum.update(chunk)
    return size, checksum.hexdigest()


def real_path(path):
    require(path.is_absolute() and path.resolve() == path, "Path must be absolute without symlinks.")
    require(not path.is_symlink(), "Symlinks are not supported.")


def regular(path):
    real_path(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Expected an unlinked regular file.")
    return info


def file_digest(path):
    regular(path)
    with path.open("rb") as source:
        return digest(source)


def timestamp(value):
    require(isinstance(value, str), "Missing verification timestamp.")
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Verification timestamps require a timezone.")
    return result


@dataclass
class Token:
    text: str
    start: int
    end: int


@dataclass
class Directive:
    words: tuple[str, ...]
    start: int
    end: int
    opening: int | None = None
    closing: int | None = None
    children: list | None = None


def caddy_tokens(text):
    """Keep offsets; braces inside quoted values/placeholders are not blocks."""
    require(len(text) <= CHUNK and "\x00" not in text, "Unsupported Caddyfile size or content.")
    result, index = [], 0
    while index < len(text):
        char = text[index]
        if char in " \t\r":
            index += 1
            continue
        start = index
        if char == "\n":
            index += 1
        elif char == "#":
            index = text.find("\n", index)
            if index < 0:
                break
            continue
        elif char == '"':
            index += 1
            while index < len(text) and text[index] != '"':
                require(text[index] != "\n", "Multiline Caddy strings are unsupported.")
                index += 2 if text[index] == "\\" else 1
            require(index < len(text), "Unclosed Caddy string.")
            index += 1
        else:
            while index < len(text) and not text[index].isspace():
                index += 1
            value = text[start:index]
            require("`" not in value and "<<" not in value, "Caddy heredocs/backticks are unsupported.")
            if "{" in value or "}" in value:
                require(value in ("{", "}") or re.fullmatch(
                    r"(?:[^{}]|\{[^{}\s]+\})+", value
                ), "Unsupported Caddy brace syntax.")
        result.append(Token(text[start:index], start, index))
    return result


def parse_caddy(text):
    tokens = caddy_tokens(text)

    def sequence(index, depth):
        require(depth < 64, "Caddy nesting is excessive.")
        nodes, words = [], []
        while index < len(tokens):
            token = tokens[index]
            if token.text == "\n":
                if words:
                    nodes.append(Directive(tuple(item.text for item in words), words[0].start, words[-1].end))
                    words = []
            elif token.text == "}":
                require(depth > 0 and not words, "Unsupported or unbalanced Caddy block.")
                return nodes, index
            elif token.text == "{":
                children, closing = sequence(index + 1, depth + 1)
                nodes.append(Directive(
                    tuple(item.text for item in words), words[0].start if words else token.start,
                    tokens[closing].end, token.end, tokens[closing].start, children,
                ))
                words = []
                index = closing
                require(index + 1 == len(tokens) or tokens[index + 1].text == "\n",
                        "Caddy blocks must end on their own line.")
            else:
                words.append(token)
            index += 1
        require(depth == 0, "Unclosed Caddy block.")
        if words:
            nodes.append(Directive(tuple(item.text for item in words), words[0].start, words[-1].end))
        return nodes, index

    return sequence(0, 0)[0]


def canonical_caddy(text):
    return tuple(token.text for token in caddy_tokens(text) if token.text != "\n")


def parse_http_redirect_hosts(value):
    """Only exact DNS names/IPv4 addresses; never wildcard, scheme, path or port."""
    require(isinstance(value, str) and 0 < len(value) <= 4096, "Provide explicit HTTP redirect hosts.")
    hosts = value.split(",")
    require(1 <= len(hosts) <= 16, "Too many HTTP redirect hosts.")
    normalized = []
    for host in hosts:
        require(host and host == host.strip() and len(host) <= 253
                and re.fullmatch(r"[A-Za-z0-9.-]+", host), "HTTP redirect host must be a plain DNS name or IPv4 address.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            require(not all(part.isdigit() for part in host.split(".")),
                    "Invalid IPv4 redirect address.")
            require(all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                        for part in host.split(".")), "Invalid DNS redirect host.")
            normalized.append(host.lower())
        else:
            require(address.version == 4, "Only IPv4 redirect addresses are supported.")
            normalized.append(str(address))
    require(len(set(normalized)) == len(normalized), "Duplicate HTTP redirect host.")
    return tuple(sorted(normalized))


def prepared_redirect_hosts(state, option=None):
    saved = state.get("httpRedirectHosts", [])
    require(isinstance(saved, list) and all(isinstance(host, str) for host in saved),
            "Invalid saved HTTP redirect configuration.")
    previous = parse_http_redirect_hosts(",".join(saved)) if saved else ()
    requested = parse_http_redirect_hosts(option) if option is not None else previous
    require("httpRedirectHosts" not in state or requested == previous,
            "HTTP redirect hosts changed after prepare; use the original approved selection.")
    return requested


def http_redirect_additions(sites, globals_, hosts):
    """Mirror only operator-verified normal redirects for exact existing HTTPS hosts."""
    if not hosts:
        return ""
    hosts = parse_http_redirect_hosts(",".join(hosts))
    for global_ in globals_:
        for node in global_.children:
            if node.words and node.words[0] in ("http_port", "https_port", "auto_https"):
                require(node.words in (("http_port", "80"), ("https_port", "443")),
                        "Custom automatic HTTPS/port policy needs manual redirect review.")
    https_hosts, http_sites = set(), {}
    for site in sites:
        addresses = []
        for word in site.words:
            address = word.removesuffix(",")
            scheme = "https"
            if address.startswith(("http://", "https://")):
                scheme, address = address.split("://", 1)
            if ":" in address:
                host, port = address.rsplit(":", 1)
                require(port in ("80", "443"), "Custom site ports need manual redirect review.")
                require(not word.startswith("https://") or port == "443",
                        "Unexpected HTTPS port configuration.")
                require(not word.startswith("http://") or port == "80",
                        "Unexpected HTTP port configuration.")
                scheme, address = ("http" if port == "80" else "https"), host
            host = parse_http_redirect_hosts(address)[0]
            addresses.append((scheme, host))
        require(len({scheme for scheme, _ in addresses}) == 1,
                "Mixed HTTP/HTTPS site blocks need manual redirect review.")
        if addresses[0][0] == "https":
            https_hosts.update(host for _, host in addresses)
            continue
        names = {host for _, host in addresses}
        directives = [node for node in site.children if node.words != ("import", "website_access")]
        require(len(directives) == 1 and directives[0].children is None,
                "Existing HTTP route needs manual review; it was not overwritten.")
        redirect = directives[0].words
        targets = {"https://{host}{uri}"}
        if len(names) == 1:
            targets.add("https://" + next(iter(names)) + "{uri}")
        require(len(redirect) == 3 and redirect[0] == "redir" and redirect[1] in targets
                and redirect[2] == "308", "Existing HTTP redirect differs from the verified normal 308.")
        for host in names:
            require(host not in http_sites, "Duplicate explicit HTTP listener.")
            http_sites[host] = site
    require(set(hosts) <= https_hosts, "HTTP redirect hosts must already have exact app-owned HTTPS sites.")
    return "".join(
        "\n\nhttp://" + host + " {\n    import website_access\n"
        "    redir https://{host}{uri} 308\n}\n"
        for host in hosts if host not in http_sites
    )


def merge_caddy(text, template, http_redirect_hosts=()):
    """Return the minimally edited main file and snippet-only companion."""
    examples = parse_caddy(template)
    require(len(examples) == 2 and examples[0].words == ()
            and examples[1].words == ("(website_access)",), "Unexpected repository logging template.")
    runtime = template[examples[0].opening:examples[0].closing].strip()
    companion = template[examples[1].start:examples[1].end] + "\n"
    nodes = parse_caddy(text)
    globals_ = [node for node in nodes if not node.words]
    require(len(globals_) <= 1 and (not globals_ or nodes[0] is globals_[0]),
            "The Caddy global block must be unique and first.")
    imports = [node for node in nodes if node.words and node.words[0] == "import"]
    require(len(imports) <= 1 and all(
        node.words == ("import", "website-logging.caddy") and node.children is None for node in imports
    ), "Unreviewed top-level Caddy imports.")
    edits = []
    if globals_:
        global_ = globals_[0]
        loggers = [node for node in global_.children if node.words and node.words[0] in ("log", "import")]
        require(not loggers or (len(loggers) == 1 and
                canonical_caddy(text[loggers[0].start:loggers[0].end]) == canonical_caddy(runtime)),
                "Existing global logging/import configuration needs manual review.")
        if not loggers:
            edits.append((global_.closing, "\n    " + runtime.replace("\n", "\n    ") + "\n"))
        if not imports:
            edits.append((global_.end, "\n\nimport website-logging.caddy"))
    else:
        edits.append((0, "{\n    " + runtime.replace("\n", "\n    ") + "\n}\n"
                      + ("" if imports else "\nimport website-logging.caddy\n\n")))
    sites = [node for node in nodes if node not in globals_ and node not in imports]
    require(sites, "No explicit Caddy sites found.")

    def check_children(children, top=True):
        managed = 0
        for node in children:
            if node.words and node.words[0] == "import":
                require(top and node.words == ("import", "website_access") and node.children is None,
                        "Unreviewed site imports.")
                managed += 1
            require(not node.words or not node.words[0].startswith("log"),
                    "Existing site logging needs manual review.")
            if node.children is not None:
                check_children(node.children, False)
        require(managed <= 1, "Duplicate website logging imports.")
        return managed

    for site in sites:
        require(site.children is not None and site.words and all(
            re.fullmatch(r"(?:https?://)?[A-Za-z0-9.*_:\[\]-]+,?", word) for word in site.words
        ), "Unsupported Caddy site/snippet shape.")
        if not check_children(site.children):
            edits.append((site.opening, "\n    import website_access"))
    redirects = http_redirect_additions(sites, globals_, http_redirect_hosts)
    for position, addition in sorted(edits, reverse=True):
        text = text[:position] + addition + text[position:]
    text += redirects
    parse_caddy(text)
    return text, companion


def merge_environment(text):
    require("\x00" not in text and not any(line.rstrip().endswith("\\") for line in text.splitlines()),
            "Unsupported environment continuations.")
    settings = {"STYL_WEBSITE_LOG_DIR": LOGS.as_posix(), "STYL_RECORDS_DIR": RECORDS.as_posix()}
    seen, result = set(), []
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(STYL_WEBSITE_LOG_DIR|STYL_RECORDS_DIR)\s*=", line)
        if match:
            key = match[1]
            require(key not in seen, "Duplicate managed environment setting.")
            seen.add(key)
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            result.append(f"{key}={settings[key]}{ending}")
        else:
            require(not re.match(r"^\s*export\s+(STYL_WEBSITE_LOG_DIR|STYL_RECORDS_DIR)\b", line),
                    "Unsupported environment assignment.")
            result.append(line)
    merged = "".join(result)
    for key, value in settings.items():
        if key not in seen:
            merged += ("" if not merged or merged.endswith("\n") else "\n") + f"{key}={value}\n"
    return merged


def check_journal_policy(text):
    section, settings = None, {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("#", ";")) or not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif section == "Journal" and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    require(all(settings.get(key) == value for key, value in {
        "Storage": "persistent", "MaxRetentionSec": "14day", "MaxFileSec": "1day",
        "SystemMaxUse": "250M", "RuntimeMaxUse": "250M",
    }.items()), "Effective journal policy is overridden; review journal configuration before activation.")


def history_records(value):
    require(isinstance(value, dict) and value.get("version") == 1, "Invalid release history manifest.")
    entries = value.get("histories")
    require(isinstance(entries, list) and len(entries) == 2, "Both initial and tail history are required.")
    require({item.get("stage") for item in entries if isinstance(item, dict)} == {"initial", "tail"},
            "Both initial and tail history are required.")
    expected = {}
    for item in entries:
        name = item.get("name", "")
        require(isinstance(name, str) and SAFE_NAME.fullmatch(name) and name.endswith(".gz"),
                "History must be a sealed gzip file.")
        require(type(item.get("bytes")) is int and 0 < item["bytes"] <= MAX_BYTES
                and HASH.fullmatch(str(item.get("sha256", ""))), "Invalid history checksum metadata.")
        require(name not in expected, "History names must be unique.")
        timestamp(item.get("capturedAt"))
        expected[name] = item
    return expected


def allowed_archive_name(name):
    if name in ("analytics.sqlite3", "restore_records.py"):
        return True
    parts = name.split("/")
    return len(parts) == 2 and bool(SAFE_NAME.fullmatch(parts[1])) and (
        parts[0] == "inquiries" and parts[1].endswith(".json")
        or parts[0] == "website-logs" and parts[1].endswith((".log", ".jsonl", ".gz", ".active"))
    )


def verify_download_proof(path, metadata, history):
    """Verify server index acknowledgement, complete ZIP integrity, and both exports."""
    expected_history = history_records(history)
    identifier = metadata.get("id", "")
    require(isinstance(identifier, str) and re.fullmatch(r"[a-f0-9]{32}", identifier),
            "Invalid Records archive identifier.")
    require(not metadata.get("archiveDeletedAt") and metadata.get("filename") == path.name,
            "Records archive is missing or deleted.")
    verified = timestamp(metadata.get("verifiedAt"))
    require(timestamp(metadata.get("createdAt")) <= verified <= datetime.now(timezone.utc),
            "Invalid download verification time.")
    require(file_digest(path) == (metadata.get("bytes"), metadata.get("sha256")),
            "Records ZIP differs from its verified index.")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(entries) <= 100_000 and len(set(name.casefold() for name in names)) == len(names),
                "Duplicate or excessive ZIP entries.")
        require("manifest.json" in names and archive.getinfo("manifest.json").file_size <= 16 * CHUNK,
                "Missing or oversized ZIP manifest.")
        manifest = load_json(archive.read("manifest.json"))
        require(isinstance(manifest, dict) and manifest.get("format") == "styl-private-records"
                and manifest.get("version") == 1 and manifest.get("id") == identifier
                and manifest.get("websiteLogsConfigured") is True, "Unexpected Records ZIP manifest.")
        require(timestamp(manifest.get("createdAt")) == timestamp(metadata.get("createdAt")),
                "Records creation times differ.")
        require(all(timestamp(manifest["createdAt"]) >= timestamp(item["capturedAt"])
                    for item in expected_history.values()), "Records ZIP predates the preserved history.")
        records = manifest.get("files")
        require(isinstance(records, list) and len(records) + 1 == len(entries), "Incomplete ZIP manifest.")
        expected, total = {}, 0
        for record in records:
            require(isinstance(record, dict) and isinstance(record.get("path"), str)
                    and allowed_archive_name(record["path"]), "Unsafe ZIP path.")
            require(type(record.get("bytes")) is int and 0 <= record["bytes"] <= MAX_BYTES
                    and HASH.fullmatch(str(record.get("sha256", "")))
                    and type(record.get("removable")) is bool, "Invalid ZIP file metadata.")
            require(record["path"] not in expected, "Duplicate manifest file.")
            expected[record["path"]] = record
            total += record["bytes"]
        require(total <= MAX_BYTES and set(expected) == set(names) - {"manifest.json"}
                and {"analytics.sqlite3", "restore_records.py"} <= set(expected), "Incomplete Records ZIP.")
        for entry in entries:
            require(not entry.is_dir() and not entry.flag_bits & 1
                    and stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG),
                    "Unsupported ZIP entry type.")
            if entry.filename != "manifest.json":
                record = expected[entry.filename]
                require(entry.file_size == record["bytes"], "ZIP file size differs.")
                with archive.open(entry) as source:
                    require(digest(source, record["bytes"]) == (record["bytes"], record["sha256"]),
                            "ZIP file checksum differs.")
        for name, record in expected_history.items():
            archived = expected.get("website-logs/" + name)
            require(archived is not None and archived["removable"] is True
                    and (archived["bytes"], archived["sha256"]) == (record["bytes"], record["sha256"]),
                    "Verified ZIP must contain both complete sealed journal exports.")
    return identifier


def run(command, *, timeout=60, stdout=subprocess.PIPE):
    return subprocess.run(command, check=True, stdout=stdout, stderr=subprocess.PIPE, timeout=timeout)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_directory(path, mode=0o700, uid=0, gid=0):
    real_path(path)
    if not path.exists():
        require(path.parent.is_dir(), "Required parent directory is missing.")
        path.mkdir(mode=mode)
    require(path.is_dir(), "Expected a real directory.")
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def atomic_write(path, data, mode=0o600, uid=0, gid=0):
    real_path(path)
    if path.exists():
        regular(path)
    candidate = path.with_name(path.name + "." + uuid.uuid4().hex + ".active")
    fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fchown(output.fileno(), uid, gid)
        os.fchmod(output.fileno(), mode)
        os.fsync(output.fileno())
    os.replace(candidate, path)
    sync_directory(path.parent)


def save_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + "\n").encode())


def snapshot(path):
    real_path(path)
    if not path.exists():
        return None
    info = regular(path)
    return (path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)


@contextmanager
def configuration_transaction(paths):
    originals = {path: snapshot(path) for path in paths}
    try:
        yield
    except BaseException:
        for path, saved in originals.items():
            if saved is not None:
                atomic_write(path, *saved)
            elif path.exists():
                regular(path)
                path.unlink()  # Only newly created configuration, never records/history.
                sync_directory(path.parent)
        raise


def protected_release(path):
    require(path.parent == Path("/var/backups/styl")
            and re.fullmatch(r"release-[a-f0-9]{7,40}", path.name),
            "Use an existing /var/backups/styl/release-<sha> directory.")
    real_path(path)
    for parent in (path, *path.parents):
        info = parent.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                and not stat.S_IMODE(info.st_mode) & 0o022, "Release path is not root-protected.")
    require(stat.S_IMODE(path.stat().st_mode) == 0o700, "Release directory must be root-only 0700.")


class Installer:
    def __init__(self, release, wait_seconds):
        protected_release(release)
        self.release = release
        self.work = release / "logging-installer"
        private_directory(self.work)
        self.state_path = self.work / "state.json"
        self.history_path = self.work / "history.json"
        self.wait_seconds = wait_seconds
        self.state = load_json(self.state_path.read_bytes()) if self.state_path.exists() else {}

    def save(self):
        save_json(self.state_path, self.state)

    def unit_state(self, name):
        result = run(["systemctl", "show", name, "--property=ActiveState",
                      "--property=UnitFileState", "--property=LoadState", "--no-pager"])
        values = dict(line.split("=", 1) for line in result.stdout.decode().splitlines() if "=" in line)
        require(values.get("LoadState") == "loaded", "A required installed unit is not loaded.")
        return values

    def protect_originals(self):
        if self.state.get("originalsSaved"):
            for item in load_json((self.work / "originals.json").read_bytes()):
                if item["present"]:
                    require(file_digest(self.work / item["backup"]) == (item["bytes"], item["sha256"]),
                            "Original configuration backup changed.")
            return
        originals = []
        for index, path in enumerate(CONFIGS):
            saved = snapshot(path)
            item = {"path": str(path), "present": saved is not None}
            if saved is not None:
                data, mode, uid, gid = saved
                name = f"original-{index:02d}"
                destination = self.work / name
                require(not destination.exists(), "Incomplete initial snapshot needs operator review.")
                atomic_write(destination, data)
                item.update(backup=name, mode=mode, uid=uid, gid=gid,
                            bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            originals.append(item)
        states = {}
        for name in UNITS:
            states[name] = self.unit_state(name)
            result = run(["systemctl", "cat", name, "--no-pager"])
            atomic_write(self.work / ("effective-" + name), result.stdout)
        save_json(self.work / "originals.json", originals)
        self.state.update(originalsSaved=True, units=states,
                          sources={name: file_digest(SOURCE / name)[1] for name in SOURCE_FILES})
        self.save()

    def check_sources(self):
        require(self.state.get("originalsSaved"), "Run prepare first.")
        require(self.state["sources"] == {name: file_digest(SOURCE / name)[1] for name in SOURCE_FILES},
                "Reviewed deployment sources changed; do not mix release candidates.")

    def pause_jobs(self):
        for timer in TIMERS:
            run(["systemctl", "stop", timer])
        deadline = time.monotonic() + self.wait_seconds
        for timer in TIMERS:
            service = timer.replace(".timer", ".service")
            while self.unit_state(service)["ActiveState"] in ("active", "activating", "deactivating", "reloading"):
                require(time.monotonic() < deadline, "Timed out waiting for an existing job; no job was killed.")
                time.sleep(1)

    def resume_jobs(self):
        for timer in TIMERS:
            require(self.unit_state(timer)["UnitFileState"] == self.state["units"][timer]["UnitFileState"],
                    "Timer enablement changed during migration; review before resuming.")
        for timer in TIMERS:
            if self.state["units"][timer]["ActiveState"] == "active":
                run(["systemctl", "start", timer])

    def capture_history(self, stage, refresh=False):
        history = load_json(self.history_path.read_bytes()) if self.history_path.exists() else {
            "version": 1, "release": self.release.name, "histories": [],
        }
        require(history.get("release") == self.release.name, "History belongs to a different release.")
        for item in history["histories"]:
            if item["stage"] == stage:
                require(file_digest(LOGS / item["name"]) == (item["bytes"], item["sha256"]),
                        "Preserved journal export changed.")
                if not refresh:
                    return
        require(shutil.disk_usage(LOGS).free >= 512 * CHUNK, "Insufficient free space for history capture.")
        run(["journalctl", "--sync"])
        name = f"journal-{stage}-{uuid.uuid4().hex}.gz"
        active = LOGS / (name + ".active")
        with active.open("xb") as output:
            os.fchmod(output.fileno(), 0o640)
            run(["/bin/bash", "-o", "pipefail", "-c",
                 "journalctl --namespace='*' --output=export --all --no-pager | gzip -c"],
                timeout=self.wait_seconds, stdout=output)
            output.flush()
            os.fsync(output.fileno())
        with gzip.open(active, "rb") as exported:
            size, _ = digest(exported)
            require(size > 0, "Journal export was empty.")
        with active.open("r+b") as source:
            os.fchmod(source.fileno(), 0o440)
            os.fsync(source.fileno())
        sealed = LOGS / name
        os.link(active, sealed)
        sync_directory(LOGS)
        active.unlink()  # Remove only the alias after durable no-overwrite publication.
        sync_directory(LOGS)
        size, checksum = file_digest(sealed)
        previous = [item for item in history["histories"] if item["stage"] == stage]
        if previous:
            history.setdefault("supersededHistories", []).extend(previous)
            history["histories"] = [item for item in history["histories"] if item["stage"] != stage]
        history["histories"].append({
            "stage": stage, "name": name, "bytes": size, "sha256": checksum, "capturedAt": utcstamp(),
        })
        save_json(self.history_path, history)

    def install_source(self, name, target, mode=0o644):
        atomic_write(target, (SOURCE / name).read_bytes(), mode)

    def prerequisites(self):
        run(["/usr/bin/python3", str(SOURCE / "check_logging_install.py"), "--require"])

    def effective_capture(self):
        for name in (*SERVICES, "styl-analytics-report.service"):
            result = run(["systemctl", "show", name, "--property=ExecStart", "--property=ExecReload",
                          "--property=KillMode", "--property=NotifyAccess", "--property=Type",
                          "--property=UMask", "--property=ReadWritePaths", "--no-pager"])
            values = dict(line.split("=", 1) for line in result.stdout.decode().splitlines() if "=" in line)
            start = values.get("ExecStart", "")
            require(start.count("argv[]=") == 1
                    and "/usr/local/lib/styl/capture_website_logs.py --directory /var/log/styl-website" in start
                    and values.get("KillMode") == "mixed", "Effective service override bypasses capture.")
            require(values.get("UMask") == ("0077" if name == "styl-analytics-report.service" else "0027"),
                    "Effective service umask differs from the reviewed capture configuration.")
            if name == "caddy.service":
                require(values.get("Type") == "notify" and values.get("NotifyAccess") == "all"
                        and "/usr/local/lib/styl/capture_website_logs.py" in values.get("ExecReload", "")
                        and "/var/log/styl-website" in values.get("ReadWritePaths", "").split(),
                        "Effective Caddy notification/reload configuration is unsupported.")
            if name == "styl-analytics-report.service":
                require({"/var/lib/styl-analytics", "/var/log/styl-website"} <=
                        set(values.get("ReadWritePaths", "").split()), "Report sandbox write paths are missing.")
        result = run(["systemctl", "show", "styl-backup.service", "--property=ExecStart", "--no-pager"])
        command = result.stdout.decode()
        require(command.count("argv[]=") == 1 and "/usr/local/lib/styl/backup.sh" in command
                and "/opt/styl/deploy/backup.sh" not in command, "Effective backup override bypasses no-expiry tool.")

    def verify_capture_state(self):
        self.prerequisites()
        self.effective_capture()
        require(self.state.get("captureConfigs") and all(
            file_digest(Path(path))[1] == checksum for path, checksum in self.state["captureConfigs"].items()
        ), "Installed capture configuration changed after cutover.")
        environment = ENV.read_bytes().decode("utf-8")
        require(merge_environment(environment) == environment, "Capture environment paths changed.")
        for name in SERVICES:
            require(self.unit_state(name)["ActiveState"] == "active", "Capture service is not active.")

    def check_baseline(self):
        require(self.state.get("cutoverBaseline") and all(
            (file_digest(Path(path))[1] if Path(path).exists() else None) == checksum
            for path, checksum in self.state["cutoverBaseline"].items()
        ), "Configuration changed after prepare; review protected originals before retrying.")

    def prepare(self, http_redirect_hosts=None):
        require(not self.state.get("cutover"), "Cutover is complete; do not prepare again.")
        import grp
        import pwd

        self.protect_originals()
        self.check_sources()
        if self.state.get("prepared"):
            self.check_baseline()
        hosts = prepared_redirect_hosts(self.state, http_redirect_hosts)
        merge_caddy(CADDY.read_bytes().decode("utf-8"),
                    (SOURCE / "website-logging.caddy").read_bytes().decode("utf-8"), hosts)
        self.state["httpRedirectHosts"] = list(hosts)
        self.save()
        self.pause_jobs()
        run(["groupadd", "--system", "--force", "styl-logs"])
        for user in ("styl", "caddy"):
            run(["usermod", "-a", "-G", "styl-logs", user])
        styl, logs = pwd.getpwnam("styl"), grp.getgrnam("styl-logs")
        private_directory(LOGS, 0o2770, 0, logs.gr_gid)
        private_directory(RECORDS, 0o700, styl.pw_uid, styl.pw_gid)
        private_directory(TOOLS, 0o755)
        self.install_source("capture_website_logs.py", TOOLS / "capture_website_logs.py")
        self.install_source("backup.sh", TOOLS / "backup.sh", 0o755)
        self.prerequisites()
        # Retain these no-expiry backup components even if a later phase fails.
        self.install_source("styl-backup.service", SYSTEMD / "styl-backup.service")
        run(["systemctl", "daemon-reload"])
        self.capture_history("initial")
        with configuration_transaction((ENV,)):
            atomic_write(ENV, merge_environment(ENV.read_bytes().decode("utf-8")).encode())
            self.state["prepared"] = True
            self.state["cutoverBaseline"] = {
                str(path): file_digest(path)[1] if path.exists() else None for path in CUTOVER_CONFIGS
            }
            self.save()
        print("Prepared: history preserved; backup/report timers paused. Activate reviewed application, then cutover.")

    def cutover(self):
        self.check_sources()
        require(self.state.get("prepared"), "Run prepare before cutover.")
        if self.state.get("cutover"):
            self.verify_capture_state()
            self.capture_history("tail")
            self.resume_jobs()
            print("Cutover already complete; history verified and previous timer activity restored.")
            return
        self.pause_jobs()
        self.prerequisites()
        self.check_baseline()
        self.capture_history("initial")
        main, companion = merge_caddy(CADDY.read_bytes().decode("utf-8"),
                                      (SOURCE / "website-logging.caddy").read_bytes().decode("utf-8"),
                                      prepared_redirect_hosts(self.state))
        dropin = SYSTEMD / "caddy.service.d"
        private_directory(dropin, 0o755)
        changed = CUTOVER_CONFIGS
        attempted_restart = False
        try:
            with configuration_transaction(changed):
                caddy_info = regular(CADDY)
                atomic_write(CADDY, main.encode(), stat.S_IMODE(caddy_info.st_mode),
                             caddy_info.st_uid, caddy_info.st_gid)
                atomic_write(SNIPPET, companion.encode(), 0o644)
                run(["caddy", "validate", "--config", str(CADDY), "--adapter", "caddyfile"])
                self.install_source("caddy-website-logs.conf", dropin / "website-logs.conf")
                for name in ("styl-api.service", "styl-web.service", "styl-analytics-report.service"):
                    self.install_source(name, SYSTEMD / name)
                self.prerequisites()
                run(["systemctl", "daemon-reload"])
                self.effective_capture()
                attempted_restart = True
                run(["systemctl", "restart", *SERVICES], timeout=180)
                for name in SERVICES:
                    require(self.unit_state(name)["ActiveState"] == "active", "A restarted service is not active.")
                self.capture_history("tail", refresh=True)
                self.state["captureConfigs"] = {
                    str(path): file_digest(path)[1] for path in (
                        *changed, TOOLS / "capture_website_logs.py", TOOLS / "backup.sh",
                        SYSTEMD / "styl-backup.service",
                    )
                }
                self.state["cutover"] = True
                self.save()
        except BaseException:
            # Configuration was restored; helpers/no-expiry backup and history remain.
            run(["systemctl", "daemon-reload"])
            if attempted_restart:
                run(["caddy", "validate", "--config", str(CADDY), "--adapter", "caddyfile"])
                original_active = [name for name in SERVICES
                                   if self.state["units"][name]["ActiveState"] == "active"]
                if original_active:
                    run(["systemctl", "restart", *original_active], timeout=180)
            raise
        self.resume_jobs()
        print("Cutover complete. Verify live privacy/coverage, download Records ZIP, and re-upload to verify it.")
        print("Approved HTTP redirects were made explicit where requested; verify every listener's access-log coverage.")

    def retention(self, identifier, confirmed):
        self.check_sources()
        require(self.state.get("cutover") and confirmed,
                "Complete cutover and explicitly confirm operator-verified capture coverage first.")
        require(identifier and re.fullmatch(r"[a-f0-9]{32}", identifier), "Provide a verified Records archive ID.")
        self.verify_capture_state()
        history = load_json(self.history_path.read_bytes())
        require(history.get("release") == self.release.name, "History release mismatch.")
        for name, item in history_records(history).items():
            require(file_digest(LOGS / name) == (item["bytes"], item["sha256"]), "Local history changed or is missing.")
        database = RECORDS / "index.sqlite3"
        regular(database)
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
            row = connection.execute("SELECT payload,state FROM archives WHERE id=?", (identifier,)).fetchone()
        require(row is not None and row[1] == "ready", "Records archive is missing or has an operation in progress.")
        metadata = load_json(row[0])
        require(isinstance(metadata, dict) and metadata.get("id") == identifier, "Archive index identity mismatch.")
        verify_download_proof(RECORDS / f"styl-records-{identifier}.zip", metadata, history)
        private_directory(JOURNAL.parent, 0o755)
        if self.state.get("retention"):
            require(file_digest(JOURNAL) == file_digest(SOURCE / "journald-operational.conf"),
                    "Journal configuration changed after retention activation.")
            check_journal_policy(run(["systemd-analyze", "cat-config", "systemd/journald.conf"]).stdout.decode())
            print("Journal-only retention already installed; non-journal operational inventory remains required.")
            return
        attempted_restart = False
        try:
            with configuration_transaction((JOURNAL,)):
                self.install_source("journald-operational.conf", JOURNAL)
                check_journal_policy(run(["systemd-analyze", "cat-config", "systemd/journald.conf"]).stdout.decode())
                attempted_restart = True
                run(["systemctl", "restart", "systemd-journald"], timeout=90)
                self.state["retention"] = {"verifiedArchive": identifier, "activatedAt": utcstamp()}
                self.save()
        except BaseException:
            if attempted_restart:
                run(["systemctl", "restart", "systemd-journald"], timeout=90)
            raise
        print("Journal-only retention installed: 14 days / 250 MB. Non-journal operational log inventory remains required.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "cutover", "retention"))
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("--verified-archive")
    parser.add_argument("--http-redirect-hosts",
                        help="PREPARE only: comma-separated exact DNS/IPv4 hosts whose normal HTTPS 308 redirects the operator verified.")
    parser.add_argument("--confirm-capture-coverage", action="store_true",
                        help="Operator verified all listeners/runtime/error paths, permissions and reload/signals.")
    args = parser.parse_args()
    try:
        require(sys.platform == "linux" and os.geteuid() == 0, "Run this installer as root on Linux.")
        require(args.phase == "prepare" or args.http_redirect_hosts is None,
                "HTTP redirect hosts may only be selected during prepare.")
        require(30 <= args.wait_seconds <= 3600, "Job/export timeout must be between 30 and 3600 seconds.")
        protected_release(args.release_dir)
        import fcntl

        lock = args.release_dir.parent / ".records-logging.lock"
        real_path(lock)
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            installer = Installer(args.release_dir, args.wait_seconds)
            if args.phase == "retention":
                installer.retention(args.verified_archive, args.confirm_capture_coverage)
            elif args.phase == "prepare":
                installer.prepare(args.http_redirect_hosts)
            else:
                installer.cutover()
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError, sqlite3.Error,
            subprocess.SubprocessError, zipfile.BadZipFile) as error:
        if isinstance(error, Refused):
            print(str(error), file=sys.stderr)
        print("Logging migration refused/failed. Preserved history files were not deleted. "
              "Journal limits may already have taken effect if retention was attempted. Timers may remain paused; "
              "inspect protected release state and resolve prerequisites before retrying. "
              "Never enable journal retention without both exports and verified download proof.", file=sys.stderr)
        return 78


if __name__ == "__main__":
    sys.exit(main())
