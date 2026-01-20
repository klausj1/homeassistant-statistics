# Pull Request (PR) process (generic)

This document describes the generic workflow for contributing changes to a GitHub project via a Pull Request (PR), especially when the contributor works from a fork.

## Actors

- **Upstream / base repository**: the main project repository owned by `@owner`.
- **Contributor fork**: a fork of the upstream repository owned by `@contributor`.
- **Base branch**: the branch in upstream that will receive changes (often `main`).
- **Head branch**: the contributor branch that contains the changes (for example `my_feature`).

A PR is a request to merge commits from the **head branch** into the **base branch**.

---

## Step 1: Create a fork

1. The contributor forks the upstream repo (`@owner/repo`) into their account (`@contributor/repo`).

---

## Step 2: Clone locally and create a feature branch

1. The contributor clones their fork to their machine.
2. The contributor creates a dedicated feature branch (example: `my_feature`).

The branch should contain only the work for that feature/fix.

---

## Step 3: Implement, test, commit, push

1. Implement the changes locally.
2. Run formatting/linting/tests locally as appropriate.
3. Commit to the feature branch.
4. Push the feature branch to the contributor’s fork on GitHub.

At this point, GitHub has:

- upstream: `@owner/repo`
- fork: `@contributor/repo`
- branch: `@contributor/repo:my_feature` containing the new commits

---

## Step 4: Open the PR on GitHub

1. On GitHub, the contributor opens a PR with:
   - **Base**: `@owner/repo` (base branch: `main`)
   - **Head**: `@contributor/repo` (head branch: `my_feature`)

This creates an “open PR” on the upstream repository.

Important:

- The PR is not a separate branch stored in upstream.
- The PR points to the contributor’s branch in the fork.

---

## Step 5: Review and test (maintainer)

The maintainer reviews the PR on GitHub (diff view, comments, suggestions).

### How the maintainer tests locally

The maintainer can check out the PR branch locally in a few common ways.

#### Option A: GitHub CLI (simple)

- `gh pr checkout <PR_NUMBER>`

This automatically fetches and checks out the PR branch.

#### Option B: Fetch the PR reference from upstream

- `git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>`
- `git checkout pr-<PR_NUMBER>`

#### Option C: Add the contributor fork as a remote

- `git remote add contributor https://github.com/<contributor>/repo.git`
- `git fetch contributor my_feature`
- `git checkout -b pr-my_feature contributor/my_feature`

After checking out the PR branch, the maintainer can run tests locally like any other branch.

---

## Step 6: Fixes, iteration, and merging

A PR is rarely “one and done”. Iteration happens until both:

- review feedback is addressed
- automated checks pass (if configured)

### How fixes are typically applied

#### Pattern 1 (most common): maintainer requests changes, contributor pushes more commits

1. Maintainer requests changes in the PR review.
2. Contributor updates the same branch locally (`my_feature`).
3. Contributor commits and pushes again to `@contributor/repo:my_feature`.
4. The PR updates automatically with the new commits.

No new PR is needed.

#### Pattern 2: maintainer pushes commits to the contributor branch

This requires the PR to allow it (GitHub setting usually shown as **“Allow edits from maintainers”**).

- If enabled, the maintainer can push commits directly to `@contributor/repo:my_feature`.
- The PR updates automatically.

### How the contributor gets maintainer-made changes locally

If the maintainer pushed commits to the contributor’s PR branch, the contributor can pull them:

- `git checkout my_feature`
- `git pull origin my_feature`

### How GitHub automated checks fit in

Many repos run automated checks on PRs (GitHub Actions or other CI), such as:

- linting/formatting
- unit tests
- type checks
- build steps

Typical lifecycle:

1. Contributor pushes commits.
2. GitHub automatically runs checks.
3. The PR shows a status (passing/failing).
4. Maintainer often requires checks to pass before merging.

### Merge

Once approved (and checks are passing if required), the maintainer merges the PR.

Common merge strategies:

- **Merge commit**: preserves individual commits.
- **Squash merge**: combines PR commits into one.
- **Rebase merge**: replays commits on top of base branch.

After merge:

- The PR is closed as “Merged”.
- The changes are now in upstream `main`.
- The contributor branch may be deleted (optional).

---

## Notes / best practices

- Keep PRs focused (one feature/fix per PR).
- Prefer small incremental commits during review; squash merge can be used later if desired.
- Let CI run on every update; treat failures as actionable feedback.
- Use the PR discussion as the source of truth for review feedback and decisions.
