# Dependency and build reproducibility policy

Status: exact-version baseline implemented; integrity hardening remains
Last reviewed: 2026-07-30

## Sources and locks

| Component | Direct dependency source | Install lock | CI install |
| --- | --- | --- | --- |
| Backend runtime | `backend/pyproject.toml` `[project.dependencies]` | `backend/requirements.txt` | exact runtime plus dev lock |
| Backend tests | `backend/pyproject.toml` `[project.optional-dependencies].dev` | `backend/requirements-dev.txt` | `pip install -r requirements-dev.txt` |
| OCR runtime | `ocr-worker/requirements.in` | `ocr-worker/requirements.txt` | exact runtime plus dev lock |
| OCR tests | `ocr-worker/requirements-dev.in` | `ocr-worker/requirements-dev.txt` | `pip install -r requirements-dev.txt` |
| Frontend | `frontend/package.json` | `frontend/package-lock.json` | `npm ci` |

Direct constraints express compatibility intent. Lock files are the only files
used for deployments and CI installs. Exact transitive versions must not be
silently regenerated during an unrelated change.

The Python locks were derived from the declared dependency closure in the
tested environment, excluding unrelated packages. They pin versions but do not
yet contain artifact hashes. This removes resolver drift but does not completely
protect against index/artifact substitution.

## Toolchain contract

- `.python-version`: Python `3.12.13`
- `backend/pyproject.toml`: supports Python `>=3.12,<3.13`
- `.nvmrc`: Node `22.16.0`
- `frontend/package.json`: Node 22.x, npm 10.x, package manager npm `10.9.2`
- OCR base: Python `3.12.13` on Debian bookworm slim
- CI runner: explicit Ubuntu 24.04 label

CI must print/verify tool versions. A toolchain change is a compatibility change,
not dependency housekeeping.

## Update workflow

Use a dedicated dependency pull request:

1. Start from a clean branch and record the advisory, compatibility, or
   maintenance reason.
2. Change the direct source only.
3. Resolve on clean Linux with Python `3.12.13`; regenerate runtime and dev
   locks together.
4. Review every added/removed/transitively changed package, wheel/source
   selection, license, and native library.
5. Rebuild from an empty environment; run `pip check`, all tests, the frontend
   production build, production-only npm audit, PostgreSQL contract tests, and
   the OCR container/readiness smoke.
6. Regenerate SBOM/inventory artifacts and compare them with the previous
   release.
7. Record rollout/rollback and update `CHANGELOG.md`.

Dependabot opens review candidates; it does not authorize automatic deployment.
Do not enable unattended merge for runtime, actions, native parser, auth,
database, or cryptography updates.

## Hash-lock completion gate

Before production promotion, select and pin one lock generator that can produce
portable Python 3.12/Linux artifacts with hashes (for example an approved
`pip-tools`, `uv`, or PEP 751 workflow). Then:

- commit generator version/configuration;
- include hashes for every selected wheel/source archive;
- install with hash verification;
- prove that backend and OCR locks regenerate without unexplained diff;
- use a controlled index or mirror policy;
- document emergency re-lock behavior if an artifact is withdrawn.

Do not check in the current Windows/Python 3.13 experimental `pip lock` output:
pip explicitly scopes that result to the current interpreter and platform, while
production and CI use Linux/Python 3.12.

## Containers and native packages

The OCR base pins the Python patch, Debian suite, and verified official manifest
digest. Apt packages still come from live Debian repositories. Build logs record
Tesseract package versions, but recording those versions is not immutability.

Remaining gate:

1. select a Debian snapshot or approved native-package lock strategy;
2. rebuild on the production architecture;
3. scan the final image and attach digest, packages, vulnerabilities, and SBOM
   to the release.

The PostgreSQL contract harness also uses a mutable `postgres:16-alpine`
reference. Pinning it requires updating both the workflow and harness together,
then validating fresh-install and upgrade tests. It was intentionally not
changed in this documentation/manifests-only pass.

## Supply-chain evidence

GitHub Actions are pinned to full commit SHAs with readable release comments.
Dependabot reviews action updates. The frontend job uploads a CycloneDX SBOM;
Python jobs upload dependency inventories.

Formal backend/OCR/container SBOMs, signature/provenance verification, container
scanning, and release artifact signing remain unimplemented. Track them as
release gates; do not describe dependency inventories as equivalent controls.
