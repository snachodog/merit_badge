#!/usr/bin/env python3
"""Convert the merit badge section of the 1911 Boy Scouts Handbook to import JSON.

Source: Project Gutenberg eBook #29558, "Boy Scouts Handbook, First Edition, 1911".
Download the HTML yourself (it is not kept in this repo):

    curl -sL https://www.gutenberg.org/cache/epub/29558/pg29558-images.html -o /tmp/hb/hb.html
    python3 -I scripts/convert_1911_handbook.py /tmp/hb/hb.html app/programs/data/handbook_1911

Standard library only. It writes one program-import file per badge
(docs/schemas/program-import.schema.json). Requirement text is copied exactly:
only whitespace is normalised and the page markers such as {25} are removed.
Each file is checked for a clean structure. Anything unexpected stops the run.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

SOURCE_URL = "https://www.gutenberg.org/cache/epub/29558/pg29558-images.html"
RELEASE_DATE = "2009-08-01"
DEFAULT_CHECKED = "2026-10-11"
OWNER = {
    "slug": "boy-scouts-of-america-historical",
    "name": "Boy Scouts of America (historical)",
    "owner_type": "organization",
}
PROGRAM_SLUG = "boy-scouts-handbook-1911"
PROGRAM_NAME = "Boy Scouts Handbook 1911"
VERSION_LABEL = "1911 first edition"
HISTORICAL = "Historical 1911 text, not a current or official Scouting America requirement."
PROGRAM_DESCRIPTION = (
    "The merit badges in the Boy Scouts Handbook, First Edition, 1911 (Boy Scouts of America), "
    "as printed then. " + HISTORICAL + " "
    "Many of these badges are obsolete or unsafe today. You do not need to do anything unsafe. "
    "Ask a trusted adult before you try any requirement, and skip what you cannot do safely. "
    "The wording, spelling and punctuation are kept as printed. "
    "This app is unofficial and is not recognized by Scouting America. "
    "Source: Project Gutenberg eBook #29558. The book is in the US public domain because of its age. "
    "If you live outside the US, check your local law."
)
SAFETY = "Many 1911 badges are obsolete or unsafe today. You do not need to do anything unsafe."
SOURCE_NOTES = (
    "Published in 1911 (copyright notice: Copyright 1911 by Boy Scouts of America). "
    "In the public domain in the United States because of its age. "
    "Project Gutenberg says readers outside the US must check local law. "
    "This is a record of the project's research, not legal advice. See docs/decisions/0005-1911-handbook-source.md."
)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def to_blocks(fragment):
    """HTML fragment to a list of text paragraphs (images dropped)."""
    fragment = re.sub(r"<img[^>]*>", "\n\n", fragment)
    fragment = re.sub(r"</(p|div|h\d|li|tr|table|blockquote)>", "\n\n", fragment)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment)
    blocks = []
    for raw in re.split(r"\n\s*\n", fragment):
        # Page markers such as {25} are not part of the text.
        text = norm(re.sub(r"\{\d+\}", " ", raw))
        if text:
            blocks.append(text)
    return blocks


HEADING_RE = re.compile(
    r'<p style="text-align: center;">\s*<span style="font-weight: bold;">(.*?)</span>', re.S
)


def parse_badges(source_html):
    start = source_html.index("{24}")
    heads = [m for m in HEADING_RE.finditer(source_html, start)]
    names = [norm(html.unescape(m.group(1))) for m in heads]
    end_index = names.index("Life Scout")  # first heading after the merit badges
    badges = []
    for i, m in enumerate(heads[:end_index]):
        seg_end = heads[i + 1].start()
        blocks = to_blocks(source_html[m.end():seg_end])
        badge = parse_badge(names[i], blocks)
        if badge:
            badges.append(badge)
    return badges


def parse_badge(name, blocks):
    lead_in = None
    reqs = []
    for text in blocks:
        num = re.match(r"(\d+)\. (.+)$", text)
        if lead_in is None and text.startswith("To obtain a merit badge for"):
            lead_in = text
        elif num:
            if int(num.group(1)) != len(reqs) + 1:
                raise ValueError(f"{name}: requirement number gap at {num.group(1)}")
            reqs.append({"display_number": num.group(1), "text": num.group(2)})
        elif text.startswith("NOTE:") and not reqs:
            # Scholarship has only a printed note and no requirements. Skip it.
            return None
        else:
            raise ValueError(f"{name}: unexpected paragraph: {text[:80]!r}")
    if not reqs:
        raise ValueError(f"{name}: no requirements found")
    return {"name": name, "lead_in": lead_in, "requirements": reqs}


def build(badge, checked):
    slug = slugify(badge["name"])
    reqs = [dict(r, text_origin="other", source="gutenberg-29558") for r in badge["requirements"]]
    description = (badge["lead_in"] + "\n\n" if badge["lead_in"] else "") + HISTORICAL + " " + SAFETY
    return {
        "schema_version": "1.0",
        "import_key": f"{OWNER['slug']}/{PROGRAM_SLUG}/{slug}/{VERSION_LABEL}",
        "program": {
            "slug": PROGRAM_SLUG,
            "name": PROGRAM_NAME,
            "owner": OWNER,
            "program_type": "historical",
            "description": PROGRAM_DESCRIPTION,
            "is_custom": True,
        },
        "award": {
            "slug": slug,
            "name": badge["name"],
            "award_type": "merit_badge",
            "description": description,
            "category": "1911 merit badge",
        },
        "version": {
            "label": VERSION_LABEL,
            "status": "draft",
            "source_status": "unverified",
            "rights_status": "public_domain",
            "effective_from": "1911-01-01",
            "effective_until": "1911-12-31",
            "source_checked_at": checked,
            "change_summary": (
                "Converted by scripts/convert_1911_handbook.py from Project Gutenberg eBook #29558 "
                "(release date " + RELEASE_DATE + "). Awaits a badge-by-badge owner review. " + HISTORICAL
            ),
        },
        "sources": [
            {
                "key": "gutenberg-29558",
                "title": "Boy Scouts Handbook, First Edition, 1911 (Project Gutenberg eBook #29558, released "
                + RELEASE_DATE + ")",
                "publisher_or_creator": "Boy Scouts of America (1911); Project Gutenberg (2009 eBook)",
                "url": SOURCE_URL,
                "source_type": "other",
                "license_or_permission_notes": SOURCE_NOTES + " Edition: 1911 first edition. " + HISTORICAL,
                "attribution_requirements": "Source: Project Gutenberg eBook #29558. Copyright 1911 by Boy Scouts of America.",
                "review_status": "unreviewed",
            }
        ],
        "requirements": reqs,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("html_file", help="Downloaded Gutenberg HTML file.")
    ap.add_argument("out_dir", help="Directory for the JSON files.")
    ap.add_argument("--checked-date", default=DEFAULT_CHECKED, help="Date you checked the source (YYYY-MM-DD).")
    args = ap.parse_args(argv)
    source_html = Path(args.html_file).read_text(encoding="utf-8")
    badges = parse_badges(source_html)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    for badge in badges:
        doc = build(badge, args.checked_date)
        (out / f"{doc['award']['slug']}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(badges)} badge files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
