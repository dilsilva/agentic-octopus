---
name: preflight
description: Safety check before ANY write to live systems (helm/kubectl apply, terraform apply, ArgoCD sync, CI run, repo settings, cloud CLI mutations). Run BEFORE proposing or executing a live change in any shared environment. Also invoke when the user asks "is this safe?" or before merging an MR/PR that triggers a deploy.
---

# Preflight — before touching live state

Assume git is drifted from live until proven otherwise. This checklist is the gate between
read-only work and any mutation.

## The checklist

1. **Classify the action.**
   - Target environment(s): dev / staging / prod — and whether the action *itself* mutates, or
     arms something that will (merging an MR, unpausing a runner, enabling a schedule count as writes).
   - **prod anywhere in the blast radius → STOP. Explicit, in-the-moment consent from the user
     required. Prior consent for a similar action does not carry over.**

2. **Verify the evidence supports THIS action.** The signal that prompted it may pattern-match a
   known failure but have a different cause. State in one sentence: what we observed → why this
   specific action fixes it.

3. **Prove no unintended diff.** For anything declarative (helm, terraform, GitOps):
   - `helm diff` / `helm upgrade --dry-run` / `terraform plan` / `argocd app diff` against
     **live**, not against what git says live should be.
   - Expected result stated *before* running the diff; unexplained hunks → stop and investigate.

4. **Know the rollback before acting.** Exact command or procedure (`helm rollback <release> <rev>`,
   revert MR + sync, restore from snapshot) and confirm the prior state is captured
   (current revision number, values export) so rollback is possible.

5. **Check for hitchhikers.** Will this action trigger anything else? Stale CI jobs on the same
   branch, GitOps auto-sync picking up unrelated drift, webhooks, pipeline schedules. Incidents
   are often caused by the hitchhiker, not the intended change.

6. **Announce, then act.** State the checklist outcome to the user in 3–5 lines (action, env, diff
   result, rollback, consent status). For non-prod: proceed after flagging. For prod: wait for
   the explicit yes.

7. **Afterwards: verify + log.** Confirm the expected end state live (`kubectl get`, app status,
   pipeline status), capture the new revision, and append a worklog entry (see /worklog).

## Shortcuts that are NOT allowed

- "Git says this is what's deployed" — git is not truth here; live is.
- "It's just staging" — staging is a shared environment; flag first anyway.
- "The pipeline will only build, not deploy" — read the pipeline definition and check its
  rules/tags before believing that.

## Project adaptation

- **Environment names:** map dev/staging/prod to the project's actual chain.
- **Consent gate:** default is prod-only; tighten to staging too if it's customer-visible.
- **Snapshot location:** where prior-state exports live (so rollback evidence has a home).
