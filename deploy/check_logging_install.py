"""Read-only preflight for the installed logging/backup service prerequisites."""

import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys


UNITS = (
    "styl-api.service", "styl-web.service", "caddy.service",
    "styl-analytics-report.service", "styl-backup.service",
)
CAPTURE = "/usr/local/lib/styl/capture_website_logs.py"
BACKUP = "/usr/local/lib/styl/backup.sh"


class IncompleteInstallation(Exception):
    pass


def installed_requirements():
    capture, backup = False, False
    for unit in UNITS:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=LoadState",
             "--property=ExecStart", "--property=ExecReload", "--no-pager"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if result.returncode and "LoadState=not-found" not in result.stdout.splitlines():
            raise IncompleteInstallation("Cannot inspect installed units.")
        capture = capture or CAPTURE in result.stdout
        backup = backup or BACKUP in result.stdout
    return capture, backup


def service_ids():
    import grp
    import pwd

    logs_gid = grp.getgrnam("styl-logs").gr_gid
    styl = pwd.getpwnam("styl")
    for name in ("styl", "caddy"):
        user = pwd.getpwnam(name)
        if logs_gid not in os.getgrouplist(name, user.pw_gid):
            raise IncompleteInstallation("Service group membership is missing.")
    return styl.pw_uid, styl.pw_gid, logs_gid


def metadata(path):
    info = path.stat()
    return info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)


def check_installation(root, capture, backup):
    if not capture and not backup:
        return
    expected = [
        ("usr/local/lib/styl", True, (0, 0, 0o755)),
    ]
    if backup:
        expected.append((BACKUP.lstrip("/"), False, (0, 0, 0o755)))
    if capture:
        styl_uid, styl_gid, logs_gid = service_ids()
        expected.extend([
            (CAPTURE.lstrip("/"), False, (0, 0, 0o644)),
            ("var/log/styl-website", True, (0, logs_gid, 0o2770)),
            ("var/lib/styl-records", True, (styl_uid, styl_gid, 0o700)),
        ])
    for relative, is_directory, required in expected:
        path = root / relative
        if path.resolve() != path or (
            not path.is_dir() if is_directory else not path.is_file()
        ):
            raise IncompleteInstallation("A required path is missing or not a real file/directory.")
        if metadata(path) != required:
            raise IncompleteInstallation("Required ownership/private permissions do not match.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require", action="store_true",
                        help="Require all prerequisites BEFORE installing updated service units.")
    args = parser.parse_args()
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise IncompleteInstallation("Run on Linux as root.")
        capture, backup = (True, True) if args.require else installed_requirements()
        check_installation(Path("/"), capture, backup)
    except (OSError, KeyError, subprocess.SubprocessError, IncompleteInstallation):
        # systemctl output can contain argv/environment; never echo it.
        print(
            "STYL logging preflight failed. Complete the root-owned tooling, "
            "private directories and group setup in deployment guide section 6 "
            "before installing/restarting updated units. No changes were made.",
            file=sys.stderr,
        )
        return 78
    return 0


if __name__ == "__main__":
    sys.exit(main())
