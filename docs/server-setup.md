# Server setup

Target server:

- Ubuntu 22.04.4 LTS
- IP: `169.255.57.42`
- SSH user: `root`
- Production domain: `read.lifestoruhabstt.info`
- Staging domain: `stagingopsvitrinaru.lol`

Recommended paths:

- staging: `/opt/opsvitrina/staging`
- production: `/opt/opsvitrina/production`

## DNS

Create two `A` records:

- `stagingopsvitrinaru.lol` -> `169.255.57.42`
- `read.lifestoruhabstt.info` -> `169.255.57.42`

Wait until both records resolve before issuing HTTPS certificates.

## Base packages

Run on the server as `root`:

```bash
apt update
apt upgrade -y
apt install -y ca-certificates curl gnupg git ufw nginx certbot python3-certbot-nginx
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

## Nginx

Nginx is the public reverse proxy. Django containers listen only on localhost ports:

- staging: `127.0.0.1:8010`
- production: `127.0.0.1:8020`

On the current server, the staging nginx server block also binds explicitly to `169.255.57.42:80` as the default HTTP server. This prevents old/default PHP virtual hosts from handling ACME challenges for `stagingopsvitrinaru.lol`.

Copy `deploy/nginx.opsvitrina.conf` from the repository to nginx sites:

```bash
mkdir -p /var/www/letsencrypt
cp /opt/opsvitrina/staging/deploy/nginx.opsvitrina.conf /etc/nginx/sites-available/opsvitrina.conf
ln -sf /etc/nginx/sites-available/opsvitrina.conf /etc/nginx/sites-enabled/opsvitrina.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

Issue HTTPS certificates after DNS records point to this server:

```bash
certbot certonly --webroot -w /var/www/letsencrypt -d stagingopsvitrinaru.lol
certbot certonly --webroot -w /var/www/letsencrypt -d read.lifestoruhabstt.info
certbot renew --dry-run
```

After certificates are issued, enable HTTPS in nginx with certbot:

```bash
certbot --nginx -d stagingopsvitrinaru.lol
certbot --nginx -d read.lifestoruhabstt.info
```

## GitHub access from the server

This key lets the server pull code from GitHub. It is different from the GitHub Actions key used later to connect from GitHub to the server.

If the repository is private, create a read-only deploy key on the server:

```bash
ssh-keygen -t ed25519 -C "opsvitrina-server-github" -f /root/.ssh/opsvitrina_github
cat /root/.ssh/opsvitrina_github.pub
```

Add the public key to GitHub:

`Repository -> Settings -> Deploy keys -> Add deploy key`

Use:

- title: `opsvitrina-server-readonly`
- key: contents of `/root/.ssh/opsvitrina_github.pub`
- allow write access: disabled

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

Create an SSH key locally or on the server for GitHub Actions to connect to the server. This is the opposite direction from the server deploy key above.

```bash
ssh-keygen -t ed25519 -C "github-actions-opsvitrina-staging" -f opsvitrina_staging_actions
cat opsvitrina_staging_actions.pub >> /root/.ssh/authorized_keys
```

Add the private key `opsvitrina_staging_actions` to GitHub Actions secrets:

- `STAGING_SSH_KEY`

Add these secrets too:

- `STAGING_HOST`: `169.255.57.42`
- `STAGING_USER`: `root`
- `STAGING_APP_DIR`: `/opt/opsvitrina/staging`

After that, every successful CI run on `staging` will deploy staging automatically.

After adding `STAGING_SSH_KEY` to GitHub secrets, remove the private key file from the server if it was generated inside the project checkout:

```bash
rm -f /opt/opsvitrina/staging/opsvitrina_staging_actions /opt/opsvitrina/staging/opsvitrina_staging_actions.pub
```

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

Use these production values unless there is a reason to change them:

- `DJANGO_ALLOWED_HOSTS=read.lifestoruhabstt.info,169.255.57.42,127.0.0.1,localhost`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://read.lifestoruhabstt.info`
- `APP_PORT=127.0.0.1:8020`
- `APP_VERSION=production`

Create a production admin user:

```bash
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-production exec web python manage.py createsuperuser
```

Add these GitHub Actions secrets for manual production deploy:

- `PROD_HOST`: `169.255.57.42`
- `PROD_USER`: `root`
- `PROD_APP_DIR`: `/opt/opsvitrina/production`
- `PROD_SSH_KEY`: private key whose public key is present in `/root/.ssh/authorized_keys`

Production deploy is intentionally manual:

`GitHub -> Actions -> Deploy production -> Run workflow -> branch main -> confirm deploy`

Before every production deploy, create a database backup:

```bash
cd /opt/opsvitrina/production
mkdir -p backups
docker compose --env-file .env -f docker-compose.deploy.yml -p opsvitrina-production exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "backups/$(date +%Y%m%d-%H%M%S).sql"
```
