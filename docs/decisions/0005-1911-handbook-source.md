# 0005 - 1911 Handbook as a source

Status: Accepted (rights check done; import stays draft until the owner reviews it)

## Context
`PLAN.md` Phase 3a allows a historical entry built from the merit badges in the *Boy Scouts Handbook*, First Edition, 1911. The owner decided to include every badge in that section. A rights check must pass first.

## Decision
- Source: Project Gutenberg eBook #29558, `https://www.gutenberg.org/cache/epub/29558/pg29558-images.html`. Gutenberg released it on 2009-08-01.
- The title page says "Copyright 1911 by Boy Scouts of America".
- A work published in 1911 is in the US public domain because of its age. We record the rights status as `public_domain`.
- Gutenberg tells readers outside the US to check their local law. The README repeats this. This ADR is a record of our research, not legal advice.
- We use the first edition only. Later editions are not covered by this check.
- Text is copied exactly, with old spelling and punctuation. Only whitespace is normalised, and page markers such as `{25}` are removed.
- The script `scripts/convert_1911_handbook.py` makes one import file per badge. The files are in `app/programs/data/handbook_1911/`. The downloaded HTML stays outside the repo.
- Each version is a draft with `source_status` unverified. A `SourceRecord` holds the URL, edition, release date and checked date.
- The program is "Boy Scouts Handbook 1911", owned by "Boy Scouts of America (historical)". It is separate from the Scouting America programs, so catalog coverage for those programs does not count it.
- Every entry says: "Historical 1911 text, not a current or official Scouting America requirement." Many badges are obsolete or unsafe today. A learner does not need to do anything unsafe.
- The command `import_handbook_1911` imports drafts only. It never publishes.

## Consequences
- The owner must check the text badge by badge against Gutenberg before publishing.
- Scholarship has no requirements in the book, only a printed note. It is stored as a note.
- Some lead-ins differ from the usual form and are kept as printed: Music ("a. scout must"), Seamanship (no "a scout must"), Chemistry ("must be able to pass the following test:"), and Firemanship, Gardening and Interpreting (comma before "a scout").
