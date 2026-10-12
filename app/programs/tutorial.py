"""The "How to use Merit Badge" tutorial. Written by this project, in plain language.

It is not Scouting America text and not an official program. It uses the generic
engine only. `seed_tutorial` loads it through the normal JSON importer.
Change the text only by adding a new LABEL. A published version is never edited.
"""

OWNER_SLUG = "merit-badge-project"
PROGRAM_SLUG = "merit-badge-help"
AWARD_SLUG = "how-to-use-merit-badge"
LABEL = "1.0"
PROJECT_URL = "https://github.com/snachodog/merit_badge"

UNOFFICIAL = (
    "Project-authored tutorial. Unofficial. It is not a Scouting America program "
    "and carries no recognition from any organization."
)


def _step(number, text, tags, evidence=(), effort="2 minutes"):
    node = {
        "display_number": number,
        "node_type": "atomic",
        "text": text,
        "text_origin": "app_authored",
        "source": "project",
        "action_tags": list(tags),
        "estimated_effort": effort,
    }
    if evidence:
        node["evidence_expectations"] = list(evidence)
    return node


def tutorial_data():
    return {
        "schema_version": "1.0",
        "import_key": f"{OWNER_SLUG}/{PROGRAM_SLUG}/{AWARD_SLUG}/{LABEL}",
        "program": {
            "slug": PROGRAM_SLUG,
            "name": "Merit Badge help",
            "owner": {
                "slug": OWNER_SLUG,
                "name": "Merit Badge project",
                "owner_type": "other",
                "website_url": PROJECT_URL,
            },
            "program_type": "tutorial",
            "description": UNOFFICIAL,
            "is_custom": True,
        },
        "award": {
            "slug": AWARD_SLUG,
            "name": "How to use Merit Badge",
            "award_type": "custom",
            "description": (
                "A short tour of this app. Finish it to see your first personal "
                "achievement record and unofficial certificate. " + UNOFFICIAL
            ),
            "category": "Tutorial",
        },
        "version": {
            "label": LABEL,
            "source_status": "user_authored",
            "rights_status": "user_authored",
            "change_summary": "First version of the project tutorial.",
        },
        "sources": [
            {
                "key": "project",
                "title": "How to use Merit Badge (project tutorial)",
                "publisher_or_creator": "Merit Badge project",
                "url": PROJECT_URL,
                "source_type": "user_authored",
                "license_or_permission_notes": "Written by this project for this app. " + UNOFFICIAL,
                "review_status": "reviewed",
            }
        ],
        "requirements": [
            _step("1", "Open the Catalog from the top menu. Browse the programs and awards, and try the search box.", ["research"]),
            _step("2", "Open any published award, then choose Start plan. A plan is your private copy of the work. It starts in the planned state; choose Start to make it active.", ["plan"]),
            _step("3", "Open one requirement from your plan. Read its text, its action tags and its guidance. Reading a requirement never completes it.", ["read"]),
            _step("4", "On a requirement page, write a short note about what you did or learned. Add evidence if you have some, such as a photo, a file, a link or a time log.", ["record", "log"], ["a short note", "a photo or file", "a time log entry"]),
            _step("5", "Mark a requirement done. The app only lets you do this when you have followed its rules, and it tells you what is missing if you have not.", ["reflect"]),
            _step("6", "Pause a plan and resume it. Use the plan page actions. Your notes and evidence stay as they are.", ["other"]),
            _step("7", "Complete a plan. When every required step is done, the plan page offers Record personal completion. The app checks the requirement logic before it allows this.", ["plan"]),
            _step("8", "Open Achievements. Find your personal record and its unofficial certificate. Print it with your browser if you like.", ["identify"]),
            _step("9", "Open Settings and download your data export. Keep a copy somewhere safe, because this app runs on your own server.", ["record"], ["the export file name and date"]),
            _step("10", f"Share Merit Badge with a friend. Send them the project page, {PROJECT_URL}, and point them to the self-hosting guide: the README and sample.docker-compose.yaml in that project. Merit Badge has no in-app sharing, invites, or accounts for others.", ["plan"]),
        ],
    }
