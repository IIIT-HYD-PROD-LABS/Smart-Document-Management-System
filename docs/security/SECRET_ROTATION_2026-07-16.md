# Secret exposure incident + rotation plan (2026-07-16)

## What happened

Production secrets were committed to git and pushed to private remotes so
Jenkins / Product Labs deploy could work without a server-side secrets store.

Tracked files that held live values:

- `.env.prod` (full production env: JWT secret, DB passwords, Fernet key,
  Gemini API key, Resend SMTP key, OAuth client secrets, Kaggle key, …)
- `docker-compose.prod.yml` (hardcoded the same secrets into every service
  `environment:` block, even though `env_file: .env.prod` was already set)

Remotes known to have contained the files (history included):

- `gh-backend` (`https://github.com/IIITH-Product-Labs/Taxsync_Backend.git`)
  branch `staging` (and any branch that merged those commits)
- Local monorepo `origin` / `main` (10 commits ahead of origin at discovery;
  secrets landed in local deploy commits)

"Private repo = safe" is **false**:

1. Every collaborator, bot, Dependabot, CI runner, and fork with read access
   gets a full copy of secrets.
2. Git history keeps secrets forever until rewritten.
3. Accidental visibility change, laptop theft, or a single leaked PAT exposes
   every credential in the tree.
4. Logs, PR reviews, and issue bots can re-surface them.

## Immediate remediation (code — done in repo)

1. Removed hardcoded secrets from `docker-compose.prod.yml`. Services load
   secrets only via `env_file: .env.prod`.
2. Stopped tracking `.env.prod` (`git rm --cached`) and ignored
   `.env.prod` / `.env*.prod` in `.gitignore`.
3. Added `.env.prod.example` (placeholders only).
4. Hardened `deploy-prod.sh` to refuse deploy when `.env.prod` is missing.
5. Bound production Redis host publish to `127.0.0.1` only.
6. Added CI job `secret-scan` that fails if tracked files look like real
   secrets again.

A local backup of the pre-scrub files lives **outside** the repo at:

`../.secrets-backup/` (do not commit, do not sync to git remotes).

## Required: rotate every exposed credential

Treat every value that ever appeared in git as **compromised**. Rotate even
if the repo stays private. Do this on the **deploy host** after updating
code; keep the app working by writing new values into the server-local
`.env.prod` only.

| Secret | Why it matters | How to rotate |
|---|---|---|
| `SECRET_KEY` | JWT / signed tokens | Generate new urlsafe 64; users re-login |
| `FERNET_KEY` | MFA TOTP, PII, BYOK AI keys, Gmail tokens | See Fernet section below — do **not** just replace |
| DB passwords (`taxsync_app`, `app_runtime`, `app_migrator`, `POSTGRES_PASSWORD`) | Full DB access | `ALTER ROLE … PASSWORD` then update URLs in `.env.prod` |
| `GEMINI_API_KEY` | Paid LLM quota + data | Google AI Studio → revoke → create new |
| `SMTP_PASSWORD` (Resend `re_…`) | Transactional email | Resend dashboard → revoke key → create new |
| `GOOGLE_CLIENT_SECRET` / Microsoft secrets | OAuth account takeover risk | Cloud console → rotate client secret |
| `KAGGLE_KEY` | Dataset API | Kaggle account → regenerate API token |
| Gmail app password in local override (if ever pushed) | Mailbox access | Google Account → App passwords → revoke |

### Fernet rotation (careful)

Ciphertext already in Postgres was encrypted with the old key. Procedure:

1. Keep the old key as `FERNET_KEY_OLD=<old>`.
2. Set `FERNET_KEY=<new>`.
3. Redeploy.
4. Run a re-encrypt pass for: `users.totp_secret_enc`, `ai_credentials.api_key_enc`,
   email OAuth tokens / credential vault fields (see `credential_vault.py` and
   `pii_encryption.py`).
5. After verifying decrypt works with the new key only, clear `FERNET_KEY_OLD`.

If you skip re-encrypt and only swap `FERNET_KEY`, MFA enrollments and BYOK
keys will fail to decrypt (500s / lockouts).

## Git history scrub (after rotation)

Removing the file from the tip of the branch is **not enough** — clones and
GitHub still have the blobs. After every secret above is rotated:

```bash
# Option A — git filter-repo (preferred)
pip install git-filter-repo
git filter-repo --path .env.prod --invert-paths --force
# also rewrite any commit that embedded secrets in docker-compose.prod.yml
# (already sanitized at tip; filter older blobs if needed)

# Option B — BFG
# bfg --delete-files .env.prod
# bfg --replace-text passwords.txt   # list of exact secret strings

git push --force --all <remote>
git push --force --tags <remote>
```

Coordinate with the whole team: everyone must re-clone or hard-reset. Force
push requires admin rights on `Taxsync_Backend` / monorepo remotes.

Also:

- GitHub → Settings → Security → secret scanning / push protection (enable).
- Invalidate any GitHub PATs that may have been logged near the incident.
- Check GitHub Actions logs for jobs that printed env.

## Deploy checklist (post-fix)

On `10.2.8.73` (or wherever prod runs):

```bash
cd ~/Smart-Document-Management-System   # or deploy path
# Keep existing secrets on the server if not yet rotated:
test -f .env.prod || cp /safe/offline/backup/.env.prod .
chmod 600 .env.prod

git pull gh-backend staging   # once sanitized branch is pushed
./deploy-prod.sh

docker compose -f docker-compose.prod.yml ps
curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
```

Confirm no container env dump is committed:

```bash
git grep -nE 'AIza|re_[A-Za-z0-9]{10,}|SECRET_KEY: [A-Za-z0-9_-]{20,}' -- \
  ':!.env.prod.example' ':!backend/.env.example' || echo "clean"
```

## Policy going forward

1. **Never** commit `.env`, `.env.prod`, `docker-compose.override.yml`.
2. Compose files may only use `${VAR}` interpolation or `env_file:`.
3. Private ≠ secret store. Prefer host file + `chmod 600`, or a real secrets
   manager (Doppler / Vault / sealed-secrets) when available.
4. CI `secret-scan` job is fail-closed; do not delete it to "make deploy green".
5. If a lead says "safe to commit env" — push back with this document.

## Owner actions (human)

- [ ] Rotate Gemini / Resend / OAuth / DB / JWT secrets
- [ ] Plan Fernet re-encrypt or accept MFA re-enroll for all users
- [ ] Force-push history scrub on every remote that had the files
- [ ] Tell every collaborator to re-clone
- [ ] Enable GitHub secret scanning + push protection
- [ ] Confirm campus Redis is not reachable from non-localhost
