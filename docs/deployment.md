# Deployment baseline

This project should use separate environments for development, staging, and production.

Current server plan is documented in `docs/server-setup.md`.

## Branch model

- `main`: production-ready code.
- `staging` or `develop`: code deployed to the staging server.
- `feature/*`: short-lived feature branches.

Production branches should be protected. Developers should merge through pull requests after CI passes.

## Environments

Use a separate `.env` file per environment. Do not reuse production secrets on staging.

Required variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Staging deployment

Staging can deploy automatically from `staging` or `develop`:

1. Build Docker image.
2. Push image to a registry.
3. Pull the image on the staging server.
4. Run migrations.
5. Run `collectstatic`.
6. Restart the web container.
7. Run a healthcheck.

The current GitHub Actions staging workflow deploys from the `staging` branch after CI passes. It expects these repository secrets:

- `STAGING_HOST`
- `STAGING_USER`
- `STAGING_SSH_KEY`
- `STAGING_APP_DIR`

## Production deployment

Production should deploy manually from `main` after staging validation:

1. Confirm CI passed on `main`.
2. Create a database backup.
3. Pull the approved Docker image.
4. Run migrations.
5. Run `collectstatic`.
6. Restart the web container.
7. Run a healthcheck.

Keep the previous image tag available for rollback.

The current GitHub Actions production workflow is manual. It expects these repository secrets:

- `PROD_HOST`
- `PROD_USER`
- `PROD_SSH_KEY`
- `PROD_APP_DIR`

Run it from GitHub Actions on the `main` branch and type `deploy` into the confirmation input.

## Reverse proxy, media, and static files

Static files are build/runtime artifacts and should not be committed.

Nginx is the public reverse proxy and should serve `/static/` and `/media/` directly from persistent host paths. The Django containers listen on localhost-only ports.

Media files are user/content uploads. For the first production setup they can live in persistent Docker bind mounts. Later, move media to S3-compatible storage when traffic and team size grow.
