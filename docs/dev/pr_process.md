# GitHub Pull Request Process

This document describes the recommended workflow for contributing to this project via GitHub Pull Requests (PRs). It covers both the contributor's and maintainer's perspectives.

## Overview

1. Fork and branch
2. Make changes and commit
3. Push to your fork
4. Open a Pull Request
5. Maintainer review and local testing
6. Fix iterations
7. CI checks and merge

---

## Step 1: Fork and Branch

### Contributor Actions

1. Fork the repository on GitHub (if not already done)
2. Clone your fork locally
3. Add the original repository as `upstream` remote:

   ```bash
   git remote add upstream https://github.com/klausj1/homeassistant-statistics.git
   ```

4. Make `upstream` fetch-only for safety:

   ```bash
   git remote set-url --push upstream no_push
   ```

5. Create a feature branch from `upstream/main`:

   ```bash
   git fetch upstream
   git checkout -b your-feature-name upstream/main
   ```

---

## Step 2: Make Changes and Commit

### Development Guidelines

- Follow the project's coding standards (see `.ruff.toml`)
- Write tests for new functionality
- Update documentation as needed
- Commit with clear messages:

  ```bash
  git add .
  git commit -m "feat: add new export option for entities filter"
  ```

### Keeping Your Branch Updated

Periodically rebase onto `upstream/main` to avoid conflicts:

```bash
git fetch upstream
git rebase upstream/main
```

---

## Step 3: Push to Your Fork

Push your feature branch to your fork (`origin`):

```bash
git push -u origin your-feature-name
```

---

## Step 4: Open a Pull Request

1. Go to your fork on GitHub
2. Click "Compare & pull request"
3. Target: `upstream/main` (or the maintainer's branch if they asked)
4. Fill in the PR description:
   - Clear title
   - Description of changes
   - Testing performed
   - Any breaking changes

### PR Settings

- **Allow edits from maintainers**: Enable this so the maintainer can push fixes directly to your branch
- Location: In the PR sidebar on GitHub

---

## Step 5: Maintainer Review and Local Testing

### Maintainer Actions

1. Review the PR for code quality and functionality
2. Pull the branch locally for testing:

   ```bash
   git checkout -b reviewer-branch-name upstream/main
   git pull https://github.com/yourusername/homeassistant-statistics.git your-feature-name
   ```

3. Run tests and manual verification
4. May push fixes directly (if "Allow edits from maintainers" is enabled)

### Contributor Response Actions

- Be responsive to feedback
- Clarify questions promptly
- Provide additional testing information if requested

---

## Step 6: Fix Iterations

### If Maintainer Pushes Fixes

- Contributor pull the latest changes into your local branch:

  ```bash
  git fetch origin
  git pull origin your-feature-name
  ```

- Review the changes
- Push any additional fixes if needed

### If Contributor Need to Make Changes

1. Make the changes locally
2. Commit them:

   ```bash
   git commit -m "fix: address reviewer feedback"
   ```

3. Push to your fork:

   ```bash
   git push origin your-feature-name
   ```

- The PR will update automatically

---

## Step 7: CI Checks and Merge

### Before Merge

- All CI checks must pass
- Maintainer is satisfied with the implementation
- Documentation is updated

### Merge Strategies

- **Maintainer's choice**: merge commit, squash, or rebase
- The maintainer may merge directly or ask you to merge after final updates

### After Merge

1. Delete your feature branch locally and on GitHub:

   ```bash
   git branch -d your-feature-name
   git push origin --delete your-feature-name
   ```

2. Update your local `main`:

   ```bash
   git checkout main
   git fetch upstream
   git rebase upstream/main
   ```

---

## Best Practices

### For Contributors

- Keep PRs focused on a single feature/fix
- Write clear commit messages
- Test thoroughly before opening PR
- Enable "Allow edits from maintainers"
- Be responsive to feedback

### For Owner

- Provide clear, actionable feedback
- Test changes locally before merging
- Communicate timeline expectations
- Consider contributor's time and effort

### Common Scenarios

#### Maintainer Closes and Reopens PR

Sometimes a maintainer may:

1. Close your PR
2. Create a new PR with their changes + yours
3. Ask you to review their PR

**What to do**:

- Review their changes
- Test if possible
- Comment with any additional fixes
- Wait for them to merge

#### Working on Maintainer's Branch

If a maintainer gives you access to work on their branch:

- Pull their branch locally
- Make your changes
- Push to their branch (if permissions allow)
- Or push to your fork and open a new PR targeting their branch

---

## Troubleshooting

### Merge Conflicts

If `upstream/main` has diverged:

```bash
git fetch upstream
git rebase upstream/main
# Resolve conflicts
git add .
git rebase --continue
git push --force-with-lease origin your-feature-name
```

### Force Push Safety

Use `--force-with-lease` instead of `--force` to avoid overwriting others' work.

### PR Settings Issues

If you can't find "Allow edits from maintainers":

- It's in the PR sidebar on GitHub
- Only available after the PR is opened
- Can be toggled at any time

---

## Summary

This process ensures:

- Clean, reviewable contributions
- Minimal merge conflicts
- Clear communication between contributors and maintainers
- High-quality code merges

Following these guidelines helps maintain the project's quality and makes the contribution process smooth for everyone involved.
