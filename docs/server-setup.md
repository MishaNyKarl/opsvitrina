# Server setup

Target server:

- Ubuntu 22.04.4 LTS
- IP: `169.239.181.248`
- SSH user: `root`
- Production domain: `read.lifestoruhabstt.info`
- Staging domain: `stagingopsvitrinaru.lol`

Recommended paths:

- staging: `/opt/opsvitrina/staging`
- production: `/opt/opsvitrina/production`

## DNS

Create two `A` records:

- `stagingopsvitrinaru.lol` -> `169.239.181.248`
- `read.lifestoruhabstt.info` -> `169.239.181.248`

Wait until both records resolve before starting Caddy. Caddy will issue HTTPS certificates automatically.

## Base packages

Run on the server as `root`:

```bash
apt update
apt upgrade -y
apt install -y ca-certificates curl gnupg git ufw
```

## Firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

## Docker

```bash
install -m 0755 -d /etc/apt/keyrings
rm -f /etc/apt/keyrings/docker.asc /etc/apt/sources.list.d/docker.list
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version
docker compose version
```

If `apt` still cannot find Docker packages, verify that the repository was added:

```bash
cat /etc/os-release
cat /etc/apt/sources.list.d/docker.list
apt-cache policy docker-ce docker-compose-plugin
```

For Ubuntu 22.04 the Docker source line should contain `jammy`. As a temporary fallback, Ubuntu's packaged Docker also works for this project:

```bash
apt update
apt install -y docker.io docker-compose-v2
systemctl enable --now docker
docker version
docker compose version
```

## Caddy

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  > /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy
systemctl enable --now caddy
```

Copy `deploy/Caddyfile` from the repository to `/etc/caddy/Caddyfile`, then reload:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

## GitHub access from the server

If the repository is private, create a read-only deploy key on the server:

```bash
ssh-keygen -t ed25519 -C "opsvitrina-server-github" -f /root/.ssh/opsvitrina_github
cat /root/.ssh/opsvitrina_github.pub
```

Add the public key to GitHub:

`Repository -> Settings -> Deploy keys -> Add deploy key`

Use this SSH config:

```bash
cat > /root/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile /root/.ssh/opsvitrina_github
  IdentitiesOnly yes
EOF
chmod 600 /root/.ssh/config
ssh -T git@github.com
```

## Staging checkout

```bash
mkdir -p /opt/opsvitrina
git clone git@github.com:MishaNyKarl/opsvitrina.git /opt/opsvitrina/staging
cd /opt/opsvitrina/staging
git checkout staging
cp deploy/env.staging.example .env
nano .env
```

Generate a strong Django secret:

```bash
python3 - <<'PY'
from secrets import token_urlsafe
print(token_urlsafe(64))
PY
```

Start staging:

```bash
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-staging up -d --build
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-staging ps
```

Create the first admin user:

```bash
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-staging exec web python manage.py createsuperuser
```

## GitHub Actions staging deploy key

Create an SSH key locally or on the server for GitHub Actions to connect to the server:

```bash
ssh-keygen -t ed25519 -C "github-actions-opsvitrina-staging" -f opsvitrina_staging_actions
cat opsvitrina_staging_actions.pub >> /root/.ssh/authorized_keys
```

Add the private key `opsvitrina_staging_actions` to GitHub Actions secrets:

- `STAGING_SSH_KEY`

Add these secrets too:

- `STAGING_HOST`: `169.239.181.248`
- `STAGING_USER`: `root`
- `STAGING_APP_DIR`: `/opt/opsvitrina/staging`

After that, every successful CI run on `staging` will deploy staging automatically.

## Production

Production should be initialized only after staging is stable:

```bash
git clone git@github.com:MishaNyKarl/opsvitrina.git /opt/opsvitrina/production
cd /opt/opsvitrina/production
git checkout main
cp deploy/env.production.example .env
nano .env
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-production up -d --build
```

Before every production deploy, create a database backup:

```bash
cd /opt/opsvitrina/production
mkdir -p backups
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-production exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "backups/$(date +%Y%m%d-%H%M%S).sql"
```
