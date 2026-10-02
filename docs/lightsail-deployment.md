# Minimal AWS Lightsail deployment

This deployment runs the Next.js frontend, FastAPI backend, Caddy, catalog JSON,
and uploaded images on one Lightsail instance. Use one backend worker because the
catalog is a local JSON file.

## Architecture and expected cost

One Ubuntu server runs every component:

```text
Phase 1: Internet -> Caddy :80  by static IP
Phase 2: Internet -> Caddy :443 by domain with automatic HTTPS
Both phases: Caddy -> Next.js :3000
       -> FastAPI :8000 for /api/* and /health
FastAPI -> /var/lib/styl/products.json
      -> /var/lib/styl/accessories.json
      -> /var/lib/styl/hero.json (created on first home-banner save)
      -> /var/lib/styl/uploads/
```

Expected recurring costs are the Lightsail 1 GB instance, domain registration,
and optional snapshots. Check the current Lightsail price in the AWS console
before creating the instance. No database, load balancer, S3 bucket, or paid TLS
certificate is required for this deployment.

## Before starting

Have these values ready and use them consistently in every command:

```text
REPOSITORY_URL=https://github.com/color4tree/STYL.git
LIGHTSAIL_STATIC_IP=54.156.37.31
YOUR_DOMAIN=example.com  (not required until the DNS phase)
```

The commands in this guide retain placeholders where a value must be substituted.
For the current STYL instance, replace every `LIGHTSAIL_STATIC_IP` with
`54.156.37.31`.

Also confirm:

1. The repository contains the version to deploy.
2. Product data in `backend/app/data/products.json` and accessory data in
  `backend/app/data/accessories.json` are ready to publish.
3. Any existing files in `backend/app/uploads/` are available for separate copy.
4. You have an AWS account with MFA enabled on the root user.
5. You control a domain's DNS records before beginning the later HTTPS phase.

### Analytics activation is a separate release gate

The approved analytics replacement is **anonymous aggregate-only**, deployed and
enabled with the owner's separate `a611b4e` rollout authorization. Its maintenance
timer is active; daily email remains disabled because analytics recipients and a
real-mail test are not yet approved. For a new installation, do not enable these
switches merely by following the storefront guide; obtain the appropriate approval.

The revised storefront uses an ordinary **Privacy** link to `/privacy`, with
informative policy and a boolean measurement opt-out, not a consent banner/modal
or technical tracking-status footer. Collection starts automatically only with
enabled aggregate-only configuration and no opt-out/exclusion. Preserve prior
declines, DNT/GPC/admin/internal/bot exclusions and fail-closed privacy checks.
There is no fallback to browser/session identifiers or raw-event/journey storage.

Before activation, verify independent server-hour aggregates, rejected identified
payloads and the legacy session endpoint's 410 response. Website/business records
follow the no-automatic-expiry policy in §6.1, not the former 13-month aggregate
expiry rule. New reports must not read old session history. Existing legacy
private data is not purged or destructively migrated by these deployment changes;
audit active retention jobs before release.
Review infrastructure access logs and business inquiry/contact data separately:
they may contain personal data even though new analytics is aggregate-only.

The updated daily mail schedule is **00:15 America/Los_Angeles (12:15 AM Pacific)**
early the next day, covering the previous completed local calendar day. Before
00:15 the latest due date is still two days ago. The existing quarter-hour timer
already aligns; persisted per-recipient claims prevent redelivery on later ticks
or DST changes. This timing change is local only, **not deployed**; actual SMTP
and inbox delivery remain **uncertified**, requiring separate deployment/send
approval. Mail stays disabled outside production, and previews exclude the
incomplete hour. Served-market privacy review is required,
not replaced by a universal claim of consent exemption. Private storage,
consistent backups, retention jobs, timer/recipient setup and rollback are covered
in [analytics operations](traffic-analytics-operations.md). City/postal is deferred.

## 0. Push and verify the source repository

From PowerShell in the repository root, inspect what will be published:

```powershell
git status
git diff --check
git diff
```

Commit and push the deployment version:

```powershell
git add --all
git commit -m "Prepare minimal Lightsail deployment"
git push origin main
git status
```

The final status should say the branch is up to date with `origin/main` and the
working tree is clean. Open the repository on GitHub and confirm the commit and
the `deploy/` directory are visible.

Do not commit `/etc/styl/styl.env`, admin tokens, AWS credentials, `.env` files,
`node_modules`, `.next`, Python virtual environments, or uploaded customer files.

## AWS account cost safeguards

Before creating resources:

1. Open **AWS Billing and Cost Management**.
2. Enable billing alerts if the account has not used them before.
3. Create an AWS Budget with a monthly cost threshold appropriate for this site.
4. Add an email alert at 80% and 100% of that threshold.
5. Check **Free Tier** and **Bills** monthly; a budget alerts on spend but does
  not automatically stop resources.

## 1. Create the server

1. Open **AWS Console**, search for **Lightsail**, and choose the region nearest
  the expected visitors. Keep every Lightsail resource in this region.
2. Select **Create instance**.
3. Choose **Linux/Unix**, **OS Only**, and **Ubuntu 24.04 LTS**.
4. Select the smallest plan with 1 GB RAM. Start with one instance only.
5. Name it `styl-production`, then select **Create instance**.
6. Open the instance and wait until its state is **Running**.
7. Open **Networking**, create a static IP named `styl-production-ip`, and attach
  it to `styl-production`. Record the IP address.
8. Under the IPv4 firewall, keep TCP 22 for SSH and add TCP 80 and TCP 443.
  Do not expose ports 3000 or 8000. Restrict port 22 to your own IP when practical.
9. Delete any IPv6 firewall entries unless IPv6 DNS and Caddy are intentionally
  configured. This avoids exposing an unreviewed network path.

Open the instance's browser-based SSH terminal. Add a 2 GB swap file so the
Next.js production build fits on the 1 GB plan:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

`free -h` should show approximately 2 GB of swap. Do not repeat the `fstab`
command after it has already been added.

## 2. Choose the initial access mode

The first deployment uses the Lightsail static IPv4 address and does not require
a domain:

```text
http://54.156.37.31
```

This phase is useful for installation and storefront testing, but it is HTTP and
does not encrypt traffic. Do not enter the admin token, update products, upload
images, or accept real customer inquiries over the public IP. Complete the DNS
and HTTPS phase before public use involving credentials or customer information.

## 3. Install system packages

Connect with the Lightsail browser SSH terminal and run:

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git python3-venv python3-pip curl ca-certificates gnupg

curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy

node --version
npm --version
python3 --version
caddy version
```

The expected major Node.js version is 22. All four version commands must succeed.

## 4. Install the application

Replace `REPOSITORY_URL` with the HTTPS clone URL. A private repository requires
a GitHub deploy key as described below.

```bash
sudo useradd --system --create-home --home-dir /var/lib/styl-user --shell /bin/bash styl
sudo install -d -m 0755 -o styl -g styl /opt/styl
sudo -u styl git clone https://github.com/color4tree/STYL.git /opt/styl

sudo -u styl python3 -m venv /opt/styl/backend/.venv
sudo -u styl /opt/styl/backend/.venv/bin/pip install -r /opt/styl/backend/requirements.txt
sudo -u styl npm --prefix /opt/styl/frontend ci
sudo -u styl npm --prefix /opt/styl/frontend run build
```

If `useradd` says the user already exists, verify it with `id styl` and continue.
If `/opt/styl` already contains a failed clone, remove only that failed checkout
before retrying; never remove `/var/lib/styl` during a deployment.

### Private GitHub repository

Skip this subsection when the repository is public. For a private repository,
generate a read-only SSH deploy key on the server:

```bash
sudo -u styl mkdir -p /var/lib/styl-user/.ssh
sudo -u styl chmod 700 /var/lib/styl-user/.ssh
sudo -u styl ssh-keygen -t ed25519 -N '' -f /var/lib/styl-user/.ssh/github_deploy
sudo -u styl cat /var/lib/styl-user/.ssh/github_deploy.pub
```

In GitHub, open the repository, then **Settings > Deploy keys > Add deploy key**.
Paste the public key, name it `styl-production`, and leave write access disabled.
Then configure and test the server key:

```bash
sudo -u styl tee /var/lib/styl-user/.ssh/config >/dev/null <<'EOF'
Host github.com
  IdentityFile /var/lib/styl-user/.ssh/github_deploy
  IdentitiesOnly yes
EOF
sudo -u styl chmod 600 /var/lib/styl-user/.ssh/config
sudo -u styl ssh-keyscan github.com | sudo -u styl tee /var/lib/styl-user/.ssh/known_hosts >/dev/null
sudo -u styl chmod 600 /var/lib/styl-user/.ssh/known_hosts
sudo -u styl ssh -T git@github.com
sudo install -d -m 0755 -o styl -g styl /opt/styl
sudo -u styl git clone git@github.com:color4tree/STYL.git /opt/styl
```

GitHub's successful SSH test may say shell access is unavailable; that is normal.

## 5. Create persistent data and secrets

The block below is safe to rerun: it does not overwrite an existing production
catalog or environment file. Replace `LIGHTSAIL_STATIC_IP` with `54.156.37.31`.
Record a newly generated admin token in a password manager; do not use it in the
browser until HTTPS is enabled.

```bash
sudo install -d -m 0750 -o styl -g styl /var/lib/styl
sudo install -d -m 0750 -o root -g styl /etc/styl
sudo install -d -m 0750 -o styl -g styl /var/lib/styl/uploads

if [ ! -f /var/lib/styl/products.json ]; then
  sudo install -m 0640 -o styl -g styl \
    /opt/styl/backend/app/data/products.json \
    /var/lib/styl/products.json
else
  echo "/var/lib/styl/products.json already exists; it was not overwritten."
fi

if [ ! -f /var/lib/styl/accessories.json ]; then
  sudo install -m 0640 -o styl -g styl \
    /opt/styl/backend/app/data/accessories.json \
    /var/lib/styl/accessories.json
else
  echo "/var/lib/styl/accessories.json already exists; it was not overwritten."
fi

if [ ! -f /etc/styl/styl.env ]; then
  ADMIN_TOKEN=$(openssl rand -hex 32)

  sudo install -m 0640 -o root -g styl \
    /opt/styl/deploy/styl.env.example \
    /etc/styl/styl.env

  sudo sed -i \
    "s/replace-with-a-long-random-token/$ADMIN_TOKEN/" \
    /etc/styl/styl.env

  sudo sed -i \
    "s#https://example.com#http://54.156.37.31#" \
    /etc/styl/styl.env

  echo "SAVE THIS ADMIN TOKEN: $ADMIN_TOKEN"
  unset ADMIN_TOKEN
else
  echo "/etc/styl/styl.env already exists; it was not overwritten."
fi
```

Do not rerun a plain copy of the repository's `products.json` or
`accessories.json` after live edits; the guards above protect the production
catalogs from being reset accidentally. If `accessories.json` is missing, the API
creates it from the built-in placeholder catalog on first request.

Existing local uploads are ignored by Git. Copy any required files separately
from `backend/app/uploads/` into `/var/lib/styl/uploads/` before launch.

From local PowerShell, use the instance's SSH key and static IP to transfer them.
The exact default username and key location are shown on the Lightsail **Connect**
tab. First create a temporary destination from the server's SSH terminal:

```bash
mkdir -p /tmp/styl-uploads
```

Then run this example from local PowerShell:

```powershell
scp -i C:\path\to\LightsailDefaultKey.pem -r .\backend\app\uploads\* ubuntu@54.156.37.31:/tmp/styl-uploads/
```

Install the transferred files from the server's SSH terminal:

```bash
sudo cp -a /tmp/styl-uploads/. /var/lib/styl/uploads/
sudo chown -R styl:styl /var/lib/styl/uploads
sudo find /var/lib/styl/uploads -type d -exec chmod 0750 {} \;
sudo find /var/lib/styl/uploads -type f -exec chmod 0640 {} \;
rm -rf /tmp/styl-uploads
```

Confirm the production environment file has no placeholders:

```bash
sudo grep -n 'replace-with\|example.com\|LIGHTSAIL_STATIC_IP' /etc/styl/styl.env
sudo grep '^STYL_DATA_DIR=' /etc/styl/styl.env
sudo grep '^STYL_ALLOWED_ORIGINS=' /etc/styl/styl.env
```

The first command should print nothing. The final two should show:

```text
STYL_DATA_DIR=/var/lib/styl
STYL_ALLOWED_ORIGINS=http://54.156.37.31
```

Never print the complete environment file in logs or support messages because it
contains the admin token.

## 6. Install services and the IP-address HTTP proxy

**Existing production installations must complete the preservation and coverage
gates in §6.1 before changing journal retention.** The following installs capture
configuration only; it deliberately does not install the operational journal
drop-in. Do not overwrite the installed domain/IP routes with an example.

The Caddy configuration below already uses the current static IP `54.156.37.31`.
The `http://` prefix intentionally prevents certificate issuance during the
IP-only phase.

```bash
sudo groupadd --system --force styl-logs
sudo usermod -a -G styl-logs styl
sudo usermod -a -G styl-logs caddy
sudo install -d -m 2770 -o root -g styl-logs /var/log/styl-website
sudo install -d -m 0700 -o styl -g styl /var/lib/styl-records
sudo install -d -m 0755 -o root -g root /usr/local/lib/styl
sudo install -m 0644 -o root -g root /opt/styl/deploy/capture_website_logs.py /usr/local/lib/styl/capture_website_logs.py
sudo install -m 0755 -o root -g root /opt/styl/deploy/backup.sh /usr/local/lib/styl/backup.sh
if sudo /usr/bin/python3 /opt/styl/deploy/check_logging_install.py --require; then
sudo install -d -m 0755 /etc/systemd/system/caddy.service.d
sudo install -m 0644 /opt/styl/deploy/caddy-website-logs.conf /etc/systemd/system/caddy.service.d/website-logs.conf
sudo install -m 0644 /opt/styl/deploy/website-logging.caddy /etc/caddy/website-logging.caddy
sudo install -m 0644 /opt/styl/deploy/styl-api.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-web.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-backup.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-backup.timer /etc/systemd/system/
sudo chmod 0755 /opt/styl/deploy/backup.sh /opt/styl/deploy/deploy.sh

sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
import website-logging.caddy

http://54.156.37.31 {
  import website_access
  encode zstd gzip

  handle /health {
    reverse_proxy 127.0.0.1:8000 {
      header_up X-Forwarded-For {http.request.remote.host}
    }
  }

  handle /api/* {
    reverse_proxy 127.0.0.1:8000 {
      header_up X-Forwarded-For {http.request.remote.host}
    }
  }

  handle {
    reverse_proxy 127.0.0.1:3000
  }
}
EOF

sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now styl-api styl-web styl-backup.timer
sudo systemctl enable caddy
sudo systemctl restart caddy
sudo systemctl --no-pager --full status styl-api styl-web caddy styl-backup.timer
else
  echo "Prerequisites failed; no updated units were copied or started." >&2
fi
```

The explicit Caddy restart is required when the package's default welcome page
was already running. Merely enabling an already-running Caddy service does not
load the replacement Caddyfile.

Do not continue copying updated units if the `--require` preflight fails. It
checks the root-owned installed scripts, real private directories, required
ownership/modes and both service users' `styl-logs` membership **before** unit
installation. It changes nothing and does not configure journal retention.

### 6.1 Website records and operational log retention

**Retention policy:** OS/build/maintenance operational logs have a **14-day
maximum** (and a 250 MB journal cap, which can expire them earlier).
**All website access/runtime/error logs and business records, including their
backups, have no automatic age or size deletion.** Rotation is segmentation, not
retention. Never apply `logrotate` deletion, `copytruncate`, Caddy's default
file-rolling retention, backup expiry or storage lifecycle deletion to these
records. Protected admin cleanup may remove **only sealed, immutable website log
files with a verified backup**; it must not remove business data or live streams.
This supersedes the earlier 14-day business-backup rule.

Deployment tooling is not an application-retention migration. Audit existing
analytics/legacy-data retention jobs and off-server backup/snapshot lifecycles
against the approved policy before activating this release. Do not assume an
older analytics retention rule or a generic maintenance cleanup is authorized to
delete website/business records under this policy.

#### Storage and backend contract

- Set `STYL_WEBSITE_LOG_DIR=/var/log/styl-website` and
  `STYL_RECORDS_DIR=/var/lib/styl-records` in `/etc/styl/styl.env`, preserving all
  other settings/secrets. Both must be absolute, real directories, not symlinks.
  Records storage must be separate, outside the website-log tree and web roots.
  The installed service `--directory` arguments must match the log environment
  value; changing only the API variable does not move the writers.
- The shared, setgid log directory is root:`styl-logs` mode **2770**; `styl` and
  `caddy` are trusted members. The API can read Caddy files and, only after backup
  verification, unlink approved sealed files. No public/static route may serve
  either directory. The records directory is `styl:styl` mode **0700**.
- The writer makes a flat directory of
  `<stream>-<UTC YYYYMMDDTHHMMSSffffffZ>-<random run ID>-<sequence>.log.active`.
  Streams are `api`, `web`, `caddy`, `caddy-reload`, and `analytics-report`.
  A successful seal removes only the final `.active` suffix, yielding `.log`.
  Active files are **0640**, sealed files **0440**, subject to the private umask.
  "Immutable" means the writer never reopens or changes sealed bytes; it is not
  `chattr +i` and is not protection against a compromised service/root account.
- The backend may archive sealed **regular `.log` or `.jsonl` files only**, never
  symlinks, devices, sockets, directories or paths outside the configured root.
  This writer emits `.log`, not `.jsonl`: size boundaries may split lines, UTF-8
  or JSON records. Order chunks by run ID and sequence to reconstruct a stream.
  Preserve raw bytes and verify backup checksums before any permitted deletion.
- **Every name ending `.active` is incomplete and never admin-removable.**
  A bounded-prefix live snapshot, if supported by the backend, is labelled
  incomplete and never qualifies its source for removal. Restarts leave old
  `.active` files untouched. Following a crash, preserve them; prove no writer
  holds the inode open, make and verify a protected recovery copy, then handle
  sealing as a separate reviewed recovery action. Never rename a running stream.
- `deploy/backup.sh` retains catalog/upload tar backups indefinitely in
  `/var/backups/styl`; that directory is **not** the admin records store. It does
  not include website logs, `/var/lib/styl-records`, analytics SQLite, environment
  secrets or machine configuration. Back each of those up separately using a
  consistent, private procedure. Avoid recursively backing up backup stores.
  The backup unit also uses a root-owned `/usr/local/lib/styl/backup.sh` copy,
  preventing an application-code rollback from restoring the old age-deletion
  script. Install the updated backup unit and script together.

#### Capture behavior and privacy

`deploy/capture_website_logs.py` uses only Python's standard library. Install the
root-owned copy in `/usr/local/lib/styl/`, outside the application Git checkout,
so rolling application code back cannot remove the running capture tool. It starts
the original command directly (no shell), inherits its working directory and
environment, and captures **both stdout and stderr**, including startup and
shutdown output. Each chunk is appended and synced. Files seal at **16 MiB**,
on a **UTC date change** (including idle streams), or after the pipe drains on
exit. Unique exclusive creation and no-overwrite publication preserve old files;
there is no retention scanner, truncation or automatic deletion of history.

A bounded queue and pipe apply backpressure rather than sampling/discarding
output. SIGTERM/SIGINT/SIGHUP/SIGQUIT/SIGUSR1/SIGUSR2 are forwarded to the child's
process group on Linux; normal child exit status is returned (signal exits use
128 + signal).
`KillMode=mixed` prevents double delivery by systemd, with 30 seconds for graceful
shutdown and a 45-second systemd limit. The Caddy drop-in retains vendor
`Type=notify` and enables `NotifyAccess=all` for the wrapped child; reload output
also has its own wrapper. **Do not restore Caddy's `--environ` flag.**

Storage/write/sync/launch failures exit **74**, emit only a fixed operational
warning, stop the child, and preserve incomplete `.active` files. The installed
long-running units do not automatically restart status 74; fix the fault and
restart explicitly. No logger can guarantee recovery of unsaved bytes after
disk failure, SIGKILL, power loss or a child failure before it flushes. Previously
lost/expired logs **cannot be reconstructed**. Application-private file handlers,
remote outputs and browser-console-only errors are not magically captured.

The shared `website-logging.caddy` uses the stock
[Caddy access log directive](https://caddyserver.com/docs/caddyfile/directives/log)
and [global runtime logger](https://caddyserver.com/docs/caddyfile/options#log):
`output stdout`/`stderr`, `format filter`, `wrap json`, and `delete` filters.
It removes the **entire request object** (IP/client IP, headers, URI/query,
referrer, user agent and TLS details), response headers and user ID, retaining
status, sizes, duration, severity and time. No request-body logging, credentials
logging, debug logging, sampling or tracking identifiers are enabled.
Uvicorn's duplicate raw-IP/URL access logger is disabled with `--no-access-log`;
Caddy supplies the intentionally coarse request summaries.

Use `import website_access` in **every** applicable HTTPS, www redirect and IP
block, and explicit HTTP redirect blocks; do not assume automatically generated
HTTPS redirect servers have access logging. Preserve the installed domains,
redirects, health/API routes and trusted-client-IP headers. If the installed
Caddyfile already has a global block, merge the runtime logger into it instead
of importing a second global block. Caddy's stock filter cannot remove the
special `msg` field: free-text exception/startup messages from Caddy, Next.js or
Python may still contain emitter-supplied sensitive content. Review actual
synthetic error output and prevent sensitive logging at the emitter; the raw
byte wrapper is **not a redaction engine**.

#### Required migration gate — never apply retention first

1. Inventory effective systemd units/drop-ins, all Caddy listeners/log sinks,
   application file handlers, analytics/report workers, timers, logrotate rules,
   journal namespaces, backups and external lifecycle policies. Preserve current
   configuration privately. The normal `deploy.sh` does **not** install capture
   tooling, backup tooling, service, Caddy or journal changes. OS/security logs,
   package/build output and the
   GeoIP updater stay operational; report-worker output is conservatively
   classified as website output and wrapped too.
2. **Before any journal policy change**, preserve every available website log
   source and old backup. Make private, verified, durable copies off the instance
   with no automatic expiry. Old journal data may mix website and operational
   entries; when coverage is uncertain, preserve the entire existing journal,
   including rotated files, rather than filtering away unknown website units.
   For an authorized consistent handoff, stop website services/report timers,
   sync/export the journals (for example `journalctl --output=export --all
   --no-pager` into a private unique `.active` file), verify the export/copies,
   record checksums and seal only after successful completion. Do not put such
   potentially sensitive exports in public artifacts. Keep the old operational
   retention policy until this is complete; **do not run journal vacuum**.
3. Provision the two directories/group, root-owned capture/backup tools and
   environment settings above. Run the section 6 `check_logging_install.py
   --require` gate before copying any updated units/drop-ins. Install the updated
   backup unit as well. Stage
   and validate the actual Caddy configuration, install the API/web services and
   Caddy drop-in, and update `styl-analytics-report.service` if that timer is
   installed. Preserve its enabled/disabled state and email configuration.
   Run `systemctl daemon-reload`, restart the affected services, and resume only
   previously enabled approved timers. Do not enable analytics/mail as a side
   effect. The [official Caddy service](https://caddyserver.com/docs/running#using-the-service)
   explains notification, override and reload semantics.
4. Verify as the service users that the directory is writable and that `styl`
   can read a sealed Caddy log. Use synthetic requests to verify root, www, IP,
   HTTP redirects, API, frontend, 404 and controlled error paths; inspect private
   access/runtime/error files and confirm headers, query tokens and form values
   are absent from the configured request summaries. Verify startup, Caddy reload,
   graceful stop/start and report-worker output. Confirm fresh journal entries
   contain **only service lifecycle/fixed capture warnings**, not website output.
   Explicitly resolve every uncovered sink before continuing.
5. Copy/sync any journal/file tail from the handoff into preserved history,
   verify backups are restorable and record coverage gaps. Obtain operational
   sign-off that **all existing history is preserved and all future website
   output is separated**. Any missing access-log configuration means those past
   requests were never captured, not that this migration recovered them.
6. **Only after all gates pass**, install the following operational-only policy:

   ```bash
   sudo install -d -m 0755 /etc/systemd/journald.conf.d
   sudo install -m 0644 /opt/styl/deploy/journald-operational.conf /etc/systemd/journald.conf.d/60-styl-operational.conf
   sudo systemctl restart systemd-journald
   ```

   Restarting journald can enforce age/size limits immediately; this is not a
   harmless preview. The template sets `MaxRetentionSec=14day`,
   `MaxFileSec=1day`, `SystemMaxUse=250M` and `RuntimeMaxUse=250M`, not website-file
   limits. Active journal files and reserved space mean usage is not an exact
   quota; monitor actual usage.
   Inspect other drop-ins/namespaces and operational file logs separately:
   journald cannot expire `/var/log/apt`, audit files, build artifacts or logs
   owned by other daemons. Audit and configure those operational sources for
   the same 14-day maximum without including website/business paths. This
   template alone does **not** certify host-wide operational retention.

No part of the above migration has been performed merely by changing repository
files. Keep disk/inode monitoring and independent backups active: when capacity
runs low, add storage or use approved backed-up sealed-log cleanup, never delete
business records or live streams to free space.

#### Isolated deployment regression checks

From the repository root with its configured Python:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s deploy\tests -p 'test_website_logs.py'
```

`OPS-LOG` covers byte-preserving size/date rotation, old-file preservation,
incomplete recovery boundaries, collision/symlink rejection, short writes,
write/sync/launch failures, stdout+stderr draining, exit status and capture
configuration. Bash tests create isolated data beneath `deploy/tests` and verify
successful/failed business backups never expire old archives. Linux-only
ownership/mode provisioning is stubbed in those Bash tests on Windows, where
NTFS/OneDrive cannot enact it; tar/link/publication operations remain real.
Linux-only
process-group/shutdown tests must also pass on the target platform; a Windows
skip is not a Linux service verification. Caddy config validation, systemd
notification/reload/permissions, synthetic privacy checks, actual disk alarms,
historical preservation and restore tests remain mandatory operational gates,
not inferred from unit tests. Tests do not deploy, vacuum or touch production.
`OPS-012` additionally covers the fail-fast installation prerequisite checks:
missing scripts/directories, incorrect ownership/modes, missing group membership
and unreadable service configuration refuse deployment before pull/build/restart.

## 7. Verify the IP-address deployment

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail --head http://127.0.0.1:3000/
curl --fail http://54.156.37.31/health
curl --fail --head http://54.156.37.31/
sudo systemctl --no-pager --full status styl-api styl-web caddy
sudo journalctl -u styl-api -u styl-web -u caddy --since '10 minutes ago'
```

The health request should return `{"status":"ok","service":"styl-api"}`. Open
`http://54.156.37.31` and verify that the storefront and product pages
load. Browser warnings that the connection is not secure are expected in this
temporary phase. Do not sign in at `/admin` or submit real inquiry data yet.

If the Caddy welcome page still appears, reload the replacement configuration and
refresh the browser without cache:

```bash
sudo cat /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo journalctl -u caddy -n 100 --no-pager
```

Confirm ports 3000 and 8000 cannot be reached from the public internet. All public
requests should enter through Caddy on port 80.

## 8. Add DNS and enable automatic HTTPS

### Current STYL production configuration (verified 2026-09-27)

- Primary URL: `https://stylfitness.com`.
- `www.stylfitness.com` permanently redirects to the root domain, retaining path
  and query string. HTTP redirects to HTTPS.
- Caddy obtained trusted Let's Encrypt certificates for both names.
- DNS already points to attached static IP `54.156.37.31`; `www` aliases to the
  root domain. Google mail records were not changed.
- Existing HTTPS IP access is retained for now; the domain is the recommended
  public URL.
- Allowed origins include the root domain, www domain, and existing IP origin.
- Configuration backup: `/etc/styl/domain-backup-20260927T172943Z`, protected
  root-only. It contains the prior environment file; never copy its contents into
  a public issue or commit it.

The following sections are general initial-setup instructions. Do not blindly
replace the current installed Caddyfile with the repository template: preserve
the production www redirect, existing IP block, and any subsequently approved
settings. Inspect, back up, stage, and validate the actual changes first.
No DNS hosting migration or AWS Certificate Manager resource is required.

Complete this phase before using `/admin`, accepting inquiries, or announcing the
site publicly.

### 8.1 Create DNS records

At the domain's DNS provider, remove conflicting `A`, `AAAA`, or `CNAME` records
for the root and `www` names, then create:

```text
A  @    54.156.37.31  TTL 300
A  www  54.156.37.31  TTL 300
```

Do not add an `AAAA` record unless IPv6 is intentionally configured. Check from
local PowerShell until both names return the Lightsail static IPv4 address:

```powershell
Resolve-DnsName YOUR_DOMAIN -Type A
Resolve-DnsName www.YOUR_DOMAIN -Type A
```

DNS updates can take several minutes or longer. Do not continue until both names
resolve to the correct address from a public network.

### 8.2 Change the allowed browser origin

On the Lightsail SSH terminal, replace the IP origin with the HTTPS domain and
verify that no placeholder remains:

```bash
sudo sed -i 's#^STYL_ALLOWED_ORIGINS=.*#STYL_ALLOWED_ORIGINS=https://YOUR_DOMAIN,https://www.YOUR_DOMAIN#' /etc/styl/styl.env
sudo grep '^STYL_ALLOWED_ORIGINS=' /etc/styl/styl.env
```

### 8.3 Switch Caddy from the IP to the domain

Install the repository's HTTPS Caddy template, replace its placeholder, validate
it, and restart the proxy and API:

```bash
sudo install -m 0644 /opt/styl/deploy/Caddyfile /etc/caddy/Caddyfile
sudo install -m 0644 /opt/styl/deploy/website-logging.caddy /etc/caddy/website-logging.caddy
sudo sed -i 's/example.com/YOUR_DOMAIN/g' /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart styl-api caddy
sudo systemctl --no-pager --full status styl-api caddy
sudo journalctl -u caddy --since '10 minutes ago' --no-pager
```

Caddy automatically requests and renews TLS certificates. Ports 80 and 443 must
remain open while certificates are issued and renewed.

After this change, use the domain as the supported public URL. Direct requests to
the IP may no longer match a configured Caddy hostname; this is expected.

### 8.4 Verify HTTPS and administration

```bash
curl --fail https://YOUR_DOMAIN/health
curl --fail https://www.YOUR_DOMAIN/health
```

Open `https://YOUR_DOMAIN/admin`, verify that the browser shows a valid secure
connection, and sign in with the saved admin token. Test one product update and
one image upload only after HTTPS is working.

Verify that anonymous catalog writes are rejected and the configured token works:

```bash
curl -i -X POST https://YOUR_DOMAIN/api/products \
  -H 'Content-Type: application/json' \
  --data '{}'

sudo bash -c 'set -a; source /etc/styl/styl.env; set +a; \
  curl --fail https://YOUR_DOMAIN/api/admin/verify \
  -H "Authorization: Bearer $STYL_ADMIN_TOKEN"'
```

The anonymous request should return `401 Unauthorized`; the verification request
should return `{"status":"authorized"}`. Do not put the token into shell history
or a URL. The admin page stores it only in browser session storage, so closing the
browser session signs the user out.

Complete this browser checklist:

1. The root page and product detail pages load over HTTPS without warnings.
2. The cart works on mobile and desktop widths.
3. An inquiry can be submitted successfully.
4. `/admin` rejects an incorrect token.
5. Product edits survive `sudo systemctl restart styl-api`.
6. Uploaded images survive both service restart and application deployment.
7. Ports `3000` and `8000` cannot be reached from the public internet.

## 9. Verify backups

For catalog-only disaster recovery, admin can also download a self-contained ZIP
including both saved catalogs, private admin fields, banner and referenced
images/videos/posters. The archive contains a standalone offline restore tool.
Follow [catalog backup and recovery](catalog-backup-and-recovery.md), keep the
download securely off this server, and restore into a new isolated destination.
It does not replace the server backup below: customer inquiries, credentials,
application code, GeoIP and machine configuration are separate recovery concerns.
Browser upload/import is deferred.

Analytics SQLite is also excluded from the catalog recovery ZIP. If analytics is
later activated, verify its private storage is covered by a consistent SQLite
backup and the no-automatic-expiry policy in §6.1; do not assume the
catalog backup commands below include it. A full analytics backup can contain
legacy private records and mail delivery metadata, not just anonymous counters.
See [analytics backup guidance](traffic-analytics-operations.md#retention-deletion-and-backups).

Run the backup once and inspect the archive:

```bash
sudo systemctl start styl-backup.service
sudo systemctl status styl-backup.service --no-pager
sudo ls -lh /var/backups/styl
sudo systemctl list-timers styl-backup.timer
```

Business archives are retained indefinitely; no age/size cleanup runs.
Unique `.tar.gz.active` files identify failed/interrupted backups; only successful
archives are published as `.tar.gz`, without overwriting older copies. The backup
script supports `STYL_DATA_DIR` and `STYL_BACKUP_DIR` overrides for isolated tests;
the installed backup service defaults remain `/var/lib/styl` and
`/var/backups/styl`. A tar copy is not a transactional snapshot of concurrent
application writes: arrange a consistent/quiescent backup and verify restoration.
Website logs and the admin records store need separate coverage (§6.1).
For minimal cost, leave Lightsail automatic
snapshots disabled. After the site contains production data, take periodic manual
snapshots from the instance's **Snapshots** tab and preserve independent off-server
backups without automatic expiry. Rotating/expiring automatic snapshots do not
meet this records policy. Review storage pricing and capacity. Local backup archives protect against editing
mistakes; snapshots protect against instance or disk loss. A backup stored only
on the same disk is not a complete disaster-recovery copy.

To restore, stop the API, extract a selected archive into
`/var/lib/styl`, restore ownership, and start the API:

```bash
sudo systemctl stop styl-api
sudo rm -rf /var/lib/styl/uploads /var/lib/styl/products.json
sudo tar -C /var/lib/styl -xzf /var/backups/styl/SELECTED_BACKUP.tar.gz
sudo chown -R styl:styl /var/lib/styl
sudo systemctl start styl-api
```

After restoration, verify `/health`, the public catalog, and one uploaded image.

## 10. Security and maintenance

Perform these tasks after launch:

1. In Lightsail networking, confirm only ports 22, 80, and 443 are public.
2. Restrict SSH port 22 to trusted source IPs when possible.
3. Keep AWS root-user MFA enabled and use an IAM administrator for daily access.
4. Store the admin token in a password manager and share it only with administrators.
5. Apply Ubuntu security updates at least monthly:

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo systemctl reboot
```

6. After reboot, verify all services and HTTPS:

```bash
sudo systemctl --no-pager --full status styl-api styl-web caddy styl-backup.timer
curl --fail https://YOUR_DOMAIN/health
```

7. Review disk and memory use periodically:

```bash
df -h
free -h
sudo du -sh /var/lib/styl /var/backups/styl /var/log/styl-website /var/lib/styl-records /opt/styl
df -i
```

8. Rotate the admin token when access changes:

```bash
NEW_TOKEN=$(openssl rand -hex 32)
sudo sed -i "s/^STYL_ADMIN_TOKEN=.*/STYL_ADMIN_TOKEN=$NEW_TOKEN/" /etc/styl/styl.env
sudo systemctl restart styl-api
echo "Save this new admin token: $NEW_TOKEN"
unset NEW_TOKEN
```

Existing browser sessions stop working immediately after token rotation.

## 11. Troubleshooting

After the logging migration, website output is in the private log directory,
not journald. Inspect files locally without copying potentially sensitive
contents into tickets or chat; `.active` files may still be growing:

```bash
sudo ls -lt /var/log/styl-website
# Substitute a verified filename from the listing; do not use an unbounded glob.
sudo tail -n 100 /var/log/styl-website/SELECTED_FILE.log.active
```

The journal remains useful for service lifecycle and fixed capture-failure
warnings (and pre-migration history until preserved):

```bash
sudo journalctl -u styl-api -n 100 --no-pager
sudo journalctl -u styl-web -n 100 --no-pager
sudo journalctl -u caddy -n 100 --no-pager
```

Common failure checks:

- `502 Bad Gateway`: run `systemctl status styl-api styl-web` and test ports 8000
  and 3000 locally with `curl`.
- HTTPS certificate failure: confirm both DNS names resolve to the static IP and
  ports 80 and 443 are open, then inspect Caddy logs.
- Admin returns `503`: verify `STYL_ADMIN_TOKEN` exists in `/etc/styl/styl.env`
  and restart `styl-api`.
- Product edits disappear: verify `STYL_DATA_DIR=/var/lib/styl`, check ownership
  with `sudo ls -la /var/lib/styl`, and confirm the API runs as user `styl`.
- Frontend build is killed: check `free -h` and confirm the 2 GB swap file is active.
- Disk is full: inspect `/var/backups/styl`, `/var/lib/styl/uploads`, and journal
  size with `sudo journalctl --disk-usage`, plus `/var/log/styl-website`,
  `/var/lib/styl-records` and free inodes. Never use automatic age/size deletion
  for website logs/business records. Exit status 74 requires fixing capture
  storage/configuration and explicitly restarting the affected service.

## Deploy later updates

The live quote-email setup was enabled on 2026-09-27 using Gmail SMTP on port 587
with STARTTLS. Sender, From address, and comma-separated recipients are configured
in `/etc/styl/styl.env`; the app password was entered through a hidden terminal
prompt and the file is root-only (0600). Systemd reads it for the API service.
Do not overwrite SMTP settings when updating origins or GeoIP configuration.
Google password changes or app-password revocation can invalidate sending;
replace credentials privately and restart only `styl-api` when needed.
The SMTP setup backup is `/etc/styl/smtp-backup-20260927T183705Z`.
See [project history](project-history.md) for the test inquiry and delivery limits.

For regional pricing, also follow [the local GeoIP setup](geoip-pricing.md).
Production GeoLite2 Country was enabled on 2026-09-27 Pacific time: the API reads
`/var/lib/styl-geoip/GeoLite2-Country.mmdb`; root-only updater credentials are in
`/etc/styl/GeoIP.conf`. The `styl-geoip-update.timer` checks twice daily. Its
root-run service validates and atomically publishes the database without
restarting the API. Keep this data outside normal catalog backups, and never
overwrite the credential file during a code deployment. The activation backup
is `/var/backups/styl/geoip-activation-bc45b22`. Public US/USD detection and
forged-header resistance were verified; Canadian visitor checks remain pending.

Provision a country database and configure `STYL_GEOIP_DATABASE`; without it,
location remains unknown and CAD is used. Apply the updated API service's trusted
loopback proxy flags and the API reverse proxy's explicit client-IP overwrite to
the installed systemd/Caddy configuration, preserving your actual domain and
other settings. First provision the root-owned tools/private directories/group
from section 6 and pass `check_logging_install.py --require`; do not copy the
updated units without those prerequisites. Validate Caddy, run
`systemctl daemon-reload`, then restart the
affected services. The normal application deploy script does not replace installed
service or proxy configuration.

Review both country prices in admin before rollout. Legacy single prices stay in
their original currency; products with no price for a visitor's market are hidden.
Existing custom Home banner text/image settings remain supported. The removed
banner price label is ignored by the API and removed from saved configuration
on the next admin save; catalog regional pricing is unaffected.

Before each update, create a data backup and note the currently deployed commit:

```bash
sudo systemctl start styl-backup.service
sudo -u styl git -C /opt/styl rev-parse HEAD
```

After pushing tested changes to `main`, deploy them:

```bash
sudo /opt/styl/deploy/deploy.sh
```

The script first runs a read-only logging preflight, then performs a fast-forward
pull, installs locked dependencies, builds
the frontend, and restarts both application services. It never modifies
`/var/lib/styl`. When installed units reference `/usr/local/lib/styl` tools,
missing scripts, private directories, ownership/modes or group membership stop
the script **before pull/build/restart**. Legacy units remain unchanged until an
explicit migration; passing their preflight does not certify website capture or
authorize journal expiry. The deploy script never provisions or activates the
14-day journal policy.

Verify after every deployment:

```bash
curl --fail https://YOUR_DOMAIN/health
sudo systemctl --no-pager --full status styl-api styl-web
sudo journalctl -u styl-api -u styl-web --since '5 minutes ago' --no-pager
```

## Roll back application code

Use a previously recorded commit hash. This changes application code only and
does not touch `/var/lib/styl`:

```bash
sudo -u styl git -C /opt/styl fetch origin
sudo -u styl git -C /opt/styl checkout PREVIOUS_COMMIT_HASH
sudo -u styl /opt/styl/backend/.venv/bin/pip install -r /opt/styl/backend/requirements.txt
sudo -u styl npm --prefix /opt/styl/frontend ci
sudo -u styl npm --prefix /opt/styl/frontend run build
sudo systemctl restart styl-api styl-web
```

After diagnosing the issue, return to the tracked branch before the next normal
deployment:

```bash
sudo -u styl git -C /opt/styl checkout main
sudo -u styl git -C /opt/styl pull --ff-only
sudo /opt/styl/deploy/deploy.sh
```

## Remove the deployment and stop charges

When the site is no longer needed:

1. Download or otherwise preserve the latest data backup and required uploads.
2. Export DNS records that need to be retained.
3. Delete the Lightsail instance, static IP, and stored snapshots.
4. Remove or change the domain's `A` records.
5. Check AWS **Bills** after deletion to confirm no other resources remain.

Deleting only the instance may leave snapshots or an unattached static IP that
continue to incur charges.
