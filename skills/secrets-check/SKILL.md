---
name: secrets-check
description: Scan a diff, repo, or file for committed secrets (tokens, webhooks, DSNs, keys) and handle findings safely. Use before every commit/MR (invoked by /mr), when touching config/TF/helm values, or when the user asks "any secrets in this?".
---

# Secrets check — assume the pattern exists until proven otherwise

Common committed-secret classes: OAuth client secrets (`GOCSPX-*`), chat bot tokens (`xox*-`)
and webhook URLs, cloud access keys (`AKIA*`, `AIza*`), platform tokens (`glpat-*`, `ghp_*`),
private keys, Sentry DSNs, plaintext passwords in values files. Check every diff.

## Scan

On the diff (staged + unstaged) or target path:

```bash
grep -rniE "(xox[bpsoa]-[0-9a-z-]+|GOCSPX-[A-Za-z0-9_-]+|hooks\.slack\.com/services/[A-Za-z0-9/]+|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AIza[0-9A-Za-z_-]{35}|glpat-[0-9A-Za-z_-]{20,}|gh[pousr]_[0-9A-Za-z_]{20,}|https://[0-9a-f]+@o[0-9]+\.ingest\.sentry\.io|password\s*[:=]\s*['\"][^'\"$]{8,}|token\s*[:=]\s*['\"][^'\"$\{]{16,})" \
  --exclude-dir=.git <target>
```

Plus judgment beyond regex: base64 blobs in values files, `sensitive` fields in terraform,
anything named `*secret*`/`*credential*` with a literal value, kubeconfig/service-account JSON.

## On finding something — order matters

1. **In MY uncommitted diff** → remove before commit; use a secret manager / external-secrets /
   masked CI variables instead. Never commit "temporarily".
2. **Already in git history (pre-existing)** → it is COMPROMISED regardless of whether we remove
   it now. Removing the file is not remediation:
   - Log in the project's security findings doc + worklog (🔒).
   - Rotation ticket (/ticket): rotate at source → move consumer to a secret store → THEN scrub
     git (history rewrite is optional cleanup, rotation is the fix).
   - Do NOT paste the secret value into chat, docs, or tickets — reference by location only.
3. **Needed for new work** → cloud secret manager (infra side), external-secrets (K8s side),
   masked CI variables (CI side). A new plaintext secret in git is never the answer.

## Rules

- Run on every MR (wired as an /mr checklist item) and on any file being moved/copied — moving a
  secret-bearing file spreads the exposure.
- Rotation of a live credential can break consumers → map consumers first, treat as a
  /preflight change.
- False positives (example values, test fixtures) → note why it's safe rather than silently ignoring.

## Project adaptation

- **Pattern list:** extend the regex with the org's own token formats (internal API keys, DSN shapes).
- **Findings doc:** where security findings are recorded (default: a `docs/security.md` findings section).
