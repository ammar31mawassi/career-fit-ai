# Third-party software and licensing gates

Status: provisional inventory; not a complete legal notice
Last reviewed: 2026-07-30

CareerFit does not yet publish a project `LICENSE`. No license should be inferred
from source availability. The legal/licensing owner in `docs/OWNERSHIP.md` must
select the project terms and approve a complete notice/SBOM process before
external distribution.

## Blocking decision

The OCR worker depends on PyMuPDF. Its published licensing model offers GNU
AGPL terms or an Artifex commercial license. The repository does not contain
evidence of a commercial entitlement or an approved AGPL compliance plan.

Before distributing or operating the OCR component beyond the currently
authorized scope, the legal/licensing owner must record one of:

1. the commercial entitlement, covered product/entity/environment, renewal
   date, and evidence location; or
2. an approved AGPL compliance plan covering source offer, modifications,
   network-use obligations, notices, and distribution.

Updating the PyMuPDF version does not resolve this decision.

## Current inventory evidence

- Frontend direct and transitive versions are fixed by
  `frontend/package-lock.json`; CI produces a CycloneDX production SBOM.
- Backend and OCR versions are fixed by their `requirements*.txt` locks; CI
  preserves `pip inspect` inventories. These inventories are not yet formal
  CycloneDX/SPDX SBOMs.
- The OCR image records Python, Tesseract, and installed Debian package versions
  in build logs, but apt sources are not yet snapshot-pinned.
- The official Python and PostgreSQL container layers, Debian packages,
  Tesseract language data, browser OCR assets, and native transitive libraries
  must be included in the final release inventory.

## Release checklist

- [ ] Project license approved and added.
- [ ] PyMuPDF decision and evidence recorded.
- [ ] SPDX/CycloneDX SBOM generated for frontend, backend, OCR, and final image.
- [ ] License policy checks transitive packages and container OS packages.
- [ ] Required license texts, copyright notices, attribution, and source offers
      are bundled or linked as counsel directs.
- [ ] SBOM and scan reports are tied to the released Git SHA/image digest and
      retained according to the approved operations evidence schedule.

This document is an engineering control record, not legal advice.
