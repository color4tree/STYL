# Minimal AWS Lightsail deployment

This deployment runs the Next.js frontend, FastAPI backend, Caddy, catalog JSON,
and uploaded images on one Lightsail instance. Use one backend worker because the
catalog is a local JSON file.

## Architecture and expected cost

One Ubuntu server runs every component:

```text
Internet -> Caddy :443 -> Next.js :3000
                -> FastAPI :8000 for /api/* and /health
FastAPI -> /var/lib/styl/products.json
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
YOUR_DOMAIN=example.com
LIGHTSAIL_STATIC_IP=203.0.113.10
```

Also confirm:

1. You control the domain's DNS records.
2. The repository contains the version to deploy.
3. Product data in `backend/app/data/products.json` is ready to publish.
4. Any existing files in `backend/app/uploads/` are available for separate copy.
5. You have an AWS account with MFA enabled on the root user.

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

## 2. Point the domain to Lightsail

At the domain's DNS provider, remove conflicting `A`, `AAAA`, or `CNAME` records
for the root and `www` names, then create:

```text
A  @    LIGHTSAIL_STATIC_IP  TTL 300
A  www  LIGHTSAIL_STATIC_IP  TTL 300
```

DNS updates can take time. Check from the local computer until the returned IP
matches the Lightsail static IP:

```powershell
Resolve-DnsName YOUR_DOMAIN
Resolve-DnsName www.YOUR_DOMAIN
```

Do not start Caddy certificate issuance until public DNS resolves correctly.
The deployment can be prepared while DNS propagates.

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
sudo -u styl git clone git@github.com:color4tree/STYL.git /opt/styl
```

GitHub's successful SSH test may say shell access is unavailable; that is normal.

## 5. Create persistent data and secrets

Replace `example.com` with the real domain. Record the generated admin token in
a password manager; it is the password used on `/admin`.

```bash
sudo install -d -m 0750 -o styl -g styl /var/lib/styl /etc/styl
sudo install -m 0640 -o styl -g styl \
  /opt/styl/backend/app/data/products.json /var/lib/styl/products.json
sudo install -d -m 0750 -o styl -g styl /var/lib/styl/uploads

ADMIN_TOKEN=$(openssl rand -hex 32)
sudo install -m 0600 -o styl -g styl \
  /opt/styl/deploy/styl.env.example /etc/styl/styl.env
sudo sed -i "s/replace-with-a-long-random-token/$ADMIN_TOKEN/" /etc/styl/styl.env
sudo sed -i "s/example.com/YOUR_DOMAIN/" /etc/styl/styl.env
echo "Save this admin token: $ADMIN_TOKEN"
```

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
scp -i C:\path\to\LightsailDefaultKey.pem -r .\backend\app\uploads\* ubuntu@LIGHTSAIL_STATIC_IP:/tmp/styl-uploads/
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
sudo grep -n 'replace-with\|example.com\|YOUR_' /etc/styl/styl.env
```

This command should print nothing. Never print the complete environment file in
logs or support messages because it contains the admin token.

## 6. Install services and HTTPS proxy

Replace both placeholder hostnames before installing the Caddyfile. Using both
names lets Caddy obtain certificates for the root and `www` domains:

```bash
sudo sed -i 's/example.com/YOUR_DOMAIN, www.YOUR_DOMAIN/' /opt/styl/deploy/Caddyfile
sudo install -m 0644 /opt/styl/deploy/styl-api.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-web.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-backup.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-backup.timer /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/Caddyfile /etc/caddy/Caddyfile
sudo chmod 0755 /opt/styl/deploy/backup.sh /opt/styl/deploy/deploy.sh

sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now styl-api styl-web styl-backup.timer caddy
```

Caddy obtains and renews the TLS certificate automatically after DNS resolves.
If only one hostname is wanted, remove the other hostname from the first line of
the installed Caddyfile.

## 7. Verify the deployment

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:3000/
curl --fail https://YOUR_DOMAIN/health
curl --fail https://www.YOUR_DOMAIN/health
sudo systemctl --no-pager --full status styl-api styl-web caddy
sudo journalctl -u styl-api -u styl-web -u caddy --since '10 minutes ago'
```

Open `https://YOUR_DOMAIN/admin` and sign in with the generated admin token.
Test one product update and one image upload.

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

## 8. Verify backups

Run the backup once and inspect the archive:

```bash
sudo systemctl start styl-backup.service
sudo systemctl status styl-backup.service --no-pager
sudo ls -lh /var/backups/styl
sudo systemctl list-timers styl-backup.timer
```

Archives are retained for 14 days. Also enable a weekly Lightsail automatic
snapshot from the instance's **Snapshots** tab and review the displayed monthly
snapshot cost before enabling it. Local backup archives protect against editing
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

## 9. Security and maintenance

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
sudo du -sh /var/lib/styl /var/backups/styl /opt/styl
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

## 10. Troubleshooting

Check service logs first:

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
  size with `sudo journalctl --disk-usage`. Do not delete production data casually.

## Deploy later updates

Before each update, create a data backup and note the currently deployed commit:

```bash
sudo systemctl start styl-backup.service
sudo -u styl git -C /opt/styl rev-parse HEAD
```

After pushing tested changes to `main`, deploy them:

```bash
sudo /opt/styl/deploy/deploy.sh
```

The script performs a fast-forward pull, installs locked dependencies, builds
the frontend, and restarts both application services. It never modifies
`/var/lib/styl`.

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
