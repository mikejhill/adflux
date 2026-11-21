---
type: reference
status: active
authority: normative
criticality: normal
review:
  status: unreviewed
---

# Releasing

Releases are automatic. Versions follow [SemVer](https://semver.org/) and are computed
from [Conventional Commits](https://www.conventionalcommits.org/) on `main` by
[release-please](https://github.com/googleapis/release-please).

## How a release happens

1. Pull requests are squash-merged into `main`; the PR title (checked by CI) becomes the
   commit message.
2. On every push to `main`, the **Release** workflow opens or updates a release pull
   request titled `chore: release X.Y.Z`. It bumps the version in `pyproject.toml` and
   `uv.lock` and updates `CHANGELOG.md`. Pushes made with the default token start no
   pull-request workflows, so the workflow dispatches CI and CodeQL for the release
   branch itself. A `RELEASE_PLEASE_TOKEN` secret is optional.
3. Merging the release pull request tags `vX.Y.Z` and creates the GitHub release. The
   same workflow then:
   - runs the full CI suite against the release commit and refuses to publish a tag that
     points anywhere else,
   - builds the sdist and wheel once and checks that their versions match the tag,
   - creates build-provenance attestations,
   - publishes to PyPI with trusted publishing (no API tokens),
   - attaches the distributions to the GitHub release.

Before 1.0.0, breaking changes bump the minor version.

| Commit | Example | Next version from 0.4.2 |
| --- | --- | --- |
| `fix:` / `perf:` / `docs:` | `fix: keep panel titles` | 0.4.3 |
| `feat:` | `feat: add the jira profile` | 0.5.0 |
| `feat!:` / `BREAKING CHANGE:` | `feat!: new directive syntax` | 0.5.0 |
| others | `ci:`, `chore:`, `test:` … | no release |

To force a specific version, add a commit with a `Release-As: 1.0.0` footer.

## Repository setup

These are already configured; they are listed so they can be checked or restored.

1. **PyPI trusted publisher**: project `adflux`, owner `mikejhill`, repository `adflux`,
   workflow `release.yml`, environment `pypi`.
2. **Releases switch**: the repository variable `RELEASES_ENABLED` is `true`.
3. **Actions may open pull requests**: Settings → Actions → General → Workflow
   permissions, with the default token read-only.
4. **Rulesets on `main`**: pull requests required for everyone with linear history and
   resolved conversations; the **CI passed** check required (owner may bypass through a
   pull request only); CodeQL merge protection with no bypass. Version tags `v*` are
   immutable. Squash is the only merge method, using the PR title and body.
