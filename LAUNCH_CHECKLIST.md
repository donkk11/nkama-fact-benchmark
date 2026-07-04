# Nkama Launch Checklist

This checklist is evidence-gated: a check is only done when the linked account
or public artifact proves it.

## Current Verified State

- [x] GitHub repository is public: `https://github.com/donkk11/nkama-fact-benchmark`
- [x] PyPI package is public: `nkama-fact-benchmark`
- [x] PyPI `0.1.22` exists and includes Homepage, Repository, and Issues links.
- [x] Public install works:

```bash
uvx --no-cache --from nkama-fact-benchmark==0.1.22 nkama-fact-benchmark selftest
```

- [x] `0.1.23` source is prepared with blocked-run permission prompts.
- [ ] `0.1.23` is published to PyPI.

## Missing Chapter

### 1. `pypi_publisher_configured`

Status: not verified.

Manual project-token publishing works, but it does **not** configure Trusted
Publishing. Trusted Publishing means GitHub Actions can publish future releases
to PyPI using a short-lived PyPI token, without storing or pasting a PyPI API
token.

The PyPI publisher must match the GitHub Actions identity:

```text
Owner: donkk11
Repository: nkama-fact-benchmark
Workflow filename: publish.yml
Environment: pypi
```

Only the PyPI project owner can configure this in the PyPI web account.

### 2. `sponsors_enabled`

Status: not verified.

GitHub Sponsors requires account-level setup: joining GitHub Sponsors, profile
details, sponsorship tiers, payout/bank or fiscal-host setup, tax information,
2FA, and GitHub approval. Codex cannot complete those account-owner steps.

After approval, update `.github/FUNDING.yml` from:

```yaml
# github: [YOUR_GITHUB_USERNAME]
```

to:

```yaml
github: [donkk11]
```

### 3. `show_hn_posted`

Status: not verified.

Show HN should be posted only when:

- the package can be tried without private access
- the GitHub repo is public
- the README tells people exactly how to run it
- the sponsor path is ready, if the goal is to convert launch attention into support

Draft is in `SHOW_HN_DRAFT.md`.

## Evidence References

- PyPI Trusted Publishing: `https://docs.pypi.org/trusted-publishers/adding-a-publisher/`
- GitHub Sponsors setup: `https://docs.github.com/en/sponsors/receiving-sponsorships-through-github-sponsors/setting-up-github-sponsors-for-your-personal-account`
- GitHub sponsor button: `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository`
- Show HN guidelines: `https://news.ycombinator.com/showhn.html`
