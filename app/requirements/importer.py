"""JSON import of a program, award, draft version and requirement tree.

Rules (PLAN.md 14.1, ADR 0003):
- The file is untrusted. Size, depth, node count and every field are checked.
- `plan_import` makes no database changes. `commit_import` writes.
- Imports always make a draft version. A published, review or archived
  version is never changed.
- The same import key with the same content does nothing.
- Errors name the exact place in the file, such as requirements[2].children[0].text.

The schema file is docs/schemas/program-import.schema.json. Allowed values
come from the model choices, and a test keeps both in step.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from programs.models import Award, AwardVersion, Program, ProgramOwner

from . import tree_rules
from .models import ImportRecord, RequirementActionTag, RequirementNode, SourceRecord

SCHEMA_VERSION = "1.0"
SLUG_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
MAX_BYTES = 1024 * 1024
MAX_NODES = 2000
MAX_DEPTH = 8
MAX_SOURCES = 100
MAX_TEXT = 5000
MAX_SHORT = 300

OWNER_TYPES = [c[0] for c in ProgramOwner.OwnerType.choices]
AWARD_TYPES = [c[0] for c in Award.AwardType.choices]
SOURCE_STATUSES = [c[0] for c in AwardVersion.SourceStatus.choices]
RIGHTS_STATUSES = [c[0] for c in AwardVersion.RightsStatus.choices]
NODE_TYPES = [c[0] for c in RequirementNode.NodeType.choices]
TEXT_ORIGINS = [c[0] for c in RequirementNode.TextOrigin.choices]
ACTION_TAGS = [c[0] for c in RequirementActionTag.Tag.choices]
SOURCE_TYPES = [c[0] for c in SourceRecord.SourceType.choices]
SOURCE_REVIEW = [c[0] for c in SourceRecord.ReviewStatus.choices]
LOGIC_TYPES = list(tree_rules.LOGIC_TYPES)


@dataclass
class Report:
    errors: list = field(default_factory=list)  # (path, message)
    warnings: list = field(default_factory=list)
    creates: list = field(default_factory=list)
    updates: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    unchanged: bool = False
    import_key: str = ""
    node_count: int = 0

    @property
    def can_commit(self):
        return not self.errors and not self.conflicts and not self.unchanged

    @property
    def outcome(self):
        if self.errors:
            return "invalid"
        if self.conflicts:
            return "conflict"
        if self.unchanged:
            return "unchanged"
        return "ready"

    def error(self, path, message):
        self.errors.append((path, message))


class ImportRefused(Exception):
    """Raised by commit_import when the report has errors or conflicts."""

    def __init__(self, report):
        self.report = report
        super().__init__("The import was refused: " + report.outcome)


# Reading the file -------------------------------------------------------------

def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"The key {key!r} appears twice in the same object.")
        out[key] = value
    return out


def _reject_constant(name):
    raise ValueError(f"{name} is not allowed in JSON.")


def parse_json(raw):
    """Turn uploaded bytes into data. Returns (data, Report). Data is None on error."""
    report = Report()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > MAX_BYTES:
        report.error("", f"The file is larger than {MAX_BYTES // 1024} KiB.")
        return None, report
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        report.error("", "The file is not valid UTF-8 text.")
        return None, report
    try:
        data = json.loads(
            text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except RecursionError:
        report.error("", "The file is nested too deeply.")
        return None, report
    except ValueError as exc:
        report.error("", f"The file is not valid JSON: {exc}")
        return None, report
    return data, report


def content_hash(data):
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Validation -------------------------------------------------------------------

class _Checker:
    def __init__(self, report):
        self.report = report

    def error(self, path, message):
        self.report.error(path, message)

    def obj(self, value, path, allowed, required=()):
        if not isinstance(value, dict):
            self.error(path, "Must be an object.")
            return False
        for key in value:
            if key not in allowed:
                self.error(_join(path, key), "This field is not allowed.")
        for key in required:
            if key not in value:
                self.error(_join(path, key), "This field is required.")
        return True

    def text(self, value, path, max_len=MAX_SHORT, required=False, blank=False):
        if value is None:
            return None
        if not isinstance(value, str):
            self.error(path, "Must be text.")
            return None
        if len(value) > max_len:
            self.error(path, f"Must be at most {max_len} characters.")
            return None
        if required and not value.strip() and not blank:
            self.error(path, "Must not be empty.")
            return None
        return value

    def choice(self, value, path, allowed):
        if value is None:
            return None
        if not isinstance(value, str) or value not in allowed:
            self.error(path, "Must be one of: " + ", ".join(allowed) + ".")
            return None
        return value

    def slug(self, value, path):
        if self.text(value, path, 100, required=True) is None:
            return
        if not SLUG_RE.fullmatch(value):
            self.error(path, "Must be a slug: lower-case letters and digits, joined by - or _.")

    def date_(self, value, path, with_time=False):
        if value is None:
            return
        if not isinstance(value, str):
            self.error(path, "Must be a date text such as 2025-01-31.")
            return
        try:
            date.fromisoformat(value) if not with_time else _parse_when(value)
        except ValueError:
            self.error(path, "Must be a valid ISO date such as 2025-01-31.")


def _join(path, key):
    return f"{path}.{key}" if path else key


def _parse_when(value):
    if "T" in value or " " in value:
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime.combine(date.fromisoformat(value), datetime.min.time())
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def validate_data(data, report):
    """Fill report.errors and report.warnings. Makes no database queries."""
    c = _Checker(report)
    top = ("schema_version", "import_key", "program", "award", "version", "sources", "requirements")
    if not c.obj(data, "", top, ("schema_version", "program", "award", "version", "requirements")):
        return
    if data.get("schema_version") != SCHEMA_VERSION:
        c.error("schema_version", f'Must be "{SCHEMA_VERSION}".')
    if "import_key" in data:
        c.text(data["import_key"], "import_key", 200, required=True)

    _check_program(c, data.get("program"))
    _check_award(c, data.get("award"))
    version = data.get("version")
    _check_version(c, version)
    source_keys = _check_sources(c, data.get("sources", []))

    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        if "requirements" in data:
            c.error("requirements", "Must be a list.")
        return
    if not requirements:
        c.error("requirements", "Must contain at least one requirement.")
        return
    specs = []
    counter = {"n": 0, "official": 0, "unsourced_official": 0}
    for i, node in enumerate(requirements):
        _check_node(c, node, f"requirements[{i}]", 1, None, i, source_keys, specs, counter)
        if counter["n"] > MAX_NODES:
            c.error("requirements", f"The file has more than {MAX_NODES} requirements.")
            return
    report.node_count = counter["n"]

    # Tree rules shared with publishing. Keys are paths, so issues name the place.
    if not report.errors:
        for issue in tree_rules.validate_tree(specs):
            report.error(str(issue.key), issue.message)

    if isinstance(version, dict) and counter["official"]:
        status = version.get("source_status")
        if status != "unverified":
            if counter["unsourced_official"]:
                c.error(
                    "version.source_status",
                    f"{counter['unsourced_official']} official-source requirement(s) have no source. "
                    'Add a source to each, or set source_status to "unverified".',
                )
            if version.get("rights_status", "unknown") == "unknown":
                c.error(
                    "version.rights_status",
                    "Official-source text needs a rights status other than unknown, "
                    'or set source_status to "unverified".',
                )


def _check_program(c, p):
    path = "program"
    allowed = ("slug", "name", "owner", "program_type", "description", "is_custom")
    if not c.obj(p, path, allowed, ("slug", "name", "owner")):
        return
    if "slug" in p:
        c.slug(p["slug"], "program.slug")
    if "name" in p:
        c.text(p["name"], "program.name", 200, required=True)
    c.text(p.get("program_type"), "program.program_type", 100)
    c.text(p.get("description"), "program.description", MAX_TEXT)
    if "is_custom" in p and not isinstance(p["is_custom"], bool):
        c.error("program.is_custom", "Must be true or false.")
    owner = p.get("owner")
    if owner is None:
        return
    if owner == "self":
        return
    if isinstance(owner, str):
        c.error("program.owner", 'Must be "self" or an owner object.')
        return
    if c.obj(owner, "program.owner", ("slug", "name", "owner_type", "website_url"), ("slug", "name")):
        if "slug" in owner:
            c.slug(owner["slug"], "program.owner.slug")
        if "name" in owner:
            c.text(owner["name"], "program.owner.name", 200, required=True)
        c.choice(owner.get("owner_type"), "program.owner.owner_type", OWNER_TYPES)
        url = c.text(owner.get("website_url"), "program.owner.website_url", 200)
        if url and not url.startswith(("http://", "https://")):
            c.error("program.owner.website_url", "Must start with http:// or https://.")


def _check_award(c, a):
    allowed = (
        "slug", "name", "award_type", "description", "category",
        "official_identifier", "eligibility_notes",
    )
    if not c.obj(a, "award", allowed, ("slug", "name")):
        return
    if "slug" in a:
        c.slug(a["slug"], "award.slug")
    if "name" in a:
        c.text(a["name"], "award.name", 200, required=True)
    c.choice(a.get("award_type"), "award.award_type", AWARD_TYPES)
    c.text(a.get("description"), "award.description", MAX_TEXT)
    c.text(a.get("category"), "award.category", 100)
    c.text(a.get("official_identifier"), "award.official_identifier", 100)
    c.text(a.get("eligibility_notes"), "award.eligibility_notes", MAX_TEXT)


def _check_version(c, v):
    allowed = (
        "label", "status", "source_status", "rights_status", "effective_from",
        "effective_until", "source_checked_at", "change_summary",
    )
    if not c.obj(v, "version", allowed, ("label", "source_status")):
        return
    if "label" in v:
        c.text(v["label"], "version.label", 100, required=True)
    if "status" in v and v["status"] != "draft":
        c.error("version.status", 'Imports always create drafts. Use "draft" or leave it out.')
    c.choice(v.get("source_status"), "version.source_status", SOURCE_STATUSES)
    c.choice(v.get("rights_status"), "version.rights_status", RIGHTS_STATUSES)
    c.date_(v.get("effective_from"), "version.effective_from")
    c.date_(v.get("effective_until"), "version.effective_until")
    c.date_(v.get("source_checked_at"), "version.source_checked_at", with_time=True)
    if (
        isinstance(v.get("effective_from"), str)
        and isinstance(v.get("effective_until"), str)
        and not any(p.startswith("version.effective") for p, _ in c.report.errors)
        and v["effective_until"] < v["effective_from"]
    ):
        c.error("version.effective_until", "Must not be before effective_from.")
    c.text(v.get("change_summary"), "version.change_summary", MAX_TEXT)


def _check_sources(c, sources):
    keys = set()
    if not isinstance(sources, list):
        c.error("sources", "Must be a list.")
        return keys
    if len(sources) > MAX_SOURCES:
        c.error("sources", f"Must have at most {MAX_SOURCES} sources.")
        return keys
    allowed = (
        "key", "title", "publisher_or_creator", "url", "source_type",
        "license_or_permission_notes", "attribution_requirements", "review_status",
    )
    for i, s in enumerate(sources):
        path = f"sources[{i}]"
        if not c.obj(s, path, allowed, ("key", "title")):
            continue
        if "key" in s:
            key = c.text(s["key"], f"{path}.key", 100, required=True)
            if key is not None:
                if key in keys:
                    c.error(f"{path}.key", f"The source key {key!r} is used twice.")
                keys.add(key)
        if "title" in s:
            c.text(s["title"], f"{path}.title", 300, required=True)
        c.text(s.get("publisher_or_creator"), f"{path}.publisher_or_creator", 200)
        url = c.text(s.get("url"), f"{path}.url", 200)
        if url and not url.startswith(("http://", "https://")):
            c.error(f"{path}.url", "Must start with http:// or https://.")
        c.choice(s.get("source_type"), f"{path}.source_type", SOURCE_TYPES)
        c.text(s.get("license_or_permission_notes"), f"{path}.license_or_permission_notes", MAX_TEXT)
        c.text(s.get("attribution_requirements"), f"{path}.attribution_requirements", MAX_TEXT)
        c.choice(s.get("review_status"), f"{path}.review_status", SOURCE_REVIEW)
    return keys


NODE_KEYS = (
    "display_number", "node_type", "text", "text_origin", "source", "action_tags",
    "completion_logic", "completion_count", "condition_expression", "estimated_effort",
    "safety_notes", "children", "evidence_expectations", "constraints",
)


def _check_node(c, node, path, depth, parent_path, order, source_keys, specs, counter):
    counter["n"] += 1
    if counter["n"] > MAX_NODES:
        return
    if depth > MAX_DEPTH:
        c.error(path, f"Requirements are nested more than {MAX_DEPTH} levels deep.")
        return
    if not c.obj(node, path, NODE_KEYS, ("text",)):
        return
    c.text(node.get("display_number"), f"{path}.display_number", 50)
    c.choice(node.get("node_type"), f"{path}.node_type", NODE_TYPES)
    if "text" in node:
        c.text(node["text"], f"{path}.text", MAX_TEXT, required=True)
    origin = c.choice(node.get("text_origin"), f"{path}.text_origin", TEXT_ORIGINS)
    c.text(node.get("estimated_effort"), f"{path}.estimated_effort", 200)
    c.text(node.get("safety_notes"), f"{path}.safety_notes", MAX_TEXT)

    source = node.get("source")
    if source is not None:
        if not isinstance(source, str) or source not in source_keys:
            c.error(f"{path}.source", "Must match the key of an entry in sources.")
            source = None
    if origin == "official_source":
        counter["official"] += 1
        if source is None:
            counter["unsourced_official"] += 1

    tags = node.get("action_tags")
    if tags is not None:
        if not isinstance(tags, list):
            c.error(f"{path}.action_tags", "Must be a list.")
        else:
            seen = set()
            for j, tag in enumerate(tags):
                c.choice(tag, f"{path}.action_tags[{j}]", ACTION_TAGS)
                if tag in seen:
                    c.error(f"{path}.action_tags[{j}]", "This tag is listed twice.")
                seen.add(tag)

    if "evidence_expectations" in node:
        ev = node["evidence_expectations"]
        if not (isinstance(ev, list) and all(isinstance(x, str) and x.strip() for x in ev)):
            c.error(f"{path}.evidence_expectations", "Must be a list of non-empty text values.")
        elif any(len(x) > 200 for x in ev):
            c.error(f"{path}.evidence_expectations", "Each label must be 200 characters or fewer.")
    if "constraints" in node:
        c.report.warnings.append(f"{path}: constraints is accepted but not stored yet.")
        if not isinstance(node["constraints"], dict):
            c.error(f"{path}.constraints", "Must be an object.")

    children = node.get("children", [])
    if not isinstance(children, list):
        c.error(f"{path}.children", "Must be a list.")
        children = []

    logic = node.get("completion_logic")
    if logic is None:
        logic = tree_rules.ALL if children else tree_rules.SINGLE
    elif not isinstance(logic, str) or logic not in LOGIC_TYPES:
        c.error(f"{path}.completion_logic", "Must be one of: " + ", ".join(LOGIC_TYPES) + ".")
        logic = tree_rules.SINGLE
    count = node.get("completion_count")
    if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 1):
        c.error(f"{path}.completion_count", "Must be a whole number of 1 or more.")
        count = None
    condition = node.get("condition_expression")

    specs.append(
        tree_rules.NodeSpec(
            key=path,
            parent_key=parent_path,
            sort_order=order,
            display_number=node.get("display_number") or "",
            completion_logic=logic,
            completion_count=count,
            condition_expression=condition,
        )
    )
    for i, child in enumerate(children):
        _check_node(
            c, child, f"{path}.children[{i}]", depth + 1, path, i, source_keys, specs, counter
        )


# Planning (no writes) -----------------------------------------------------------

def default_import_key(data):
    program, award, version = data["program"], data["award"], data["version"]
    owner = program.get("owner")
    owner_slug = "self" if owner == "self" else (owner or {}).get("slug", "")
    return f"{owner_slug}/{program['slug']}/{award['slug']}/{version['label']}"


def _owner_values(owner):
    if owner == "self":
        return {"slug": "self", "name": "Me", "owner_type": ProgramOwner.OwnerType.INDIVIDUAL}
    return {
        "slug": owner["slug"],
        "name": owner["name"],
        "owner_type": owner.get("owner_type", ProgramOwner.OwnerType.ORGANIZATION),
        "website_url": owner.get("website_url", ""),
    }


def plan_import(raw_or_data):
    """Check a file and say what an import would do. Makes no database changes.

    Accepts bytes or text (parsed here) or already-parsed data.
    Returns (data, Report). Data is None if the file could not be read.
    """
    if isinstance(raw_or_data, (bytes, str)):
        data, report = parse_json(raw_or_data)
        if data is None:
            return None, report
    else:
        data, report = raw_or_data, Report()
    validate_data(data, report)
    if report.errors:
        return data, report

    key = data.get("import_key") or default_import_key(data)
    report.import_key = key
    digest = content_hash(data)
    existing = ImportRecord.objects.filter(import_key=key).select_related("award_version").first()

    owner_values = _owner_values(data["program"]["owner"])
    owner = ProgramOwner.objects.filter(slug=owner_values["slug"]).first()
    program = (
        Program.objects.filter(owner=owner, slug=data["program"]["slug"]).first() if owner else None
    )
    award = (
        Award.objects.filter(program=program, slug=data["award"]["slug"]).first()
        if program
        else None
    )
    label = data["version"]["label"]
    version_row = AwardVersion.objects.filter(award=award, version_label=label).first() if award else None

    if owner is None:
        report.creates.append(f"Program owner: {owner_values['name']}")
    if program is None:
        report.creates.append(f"Program: {data['program']['name']}")
    elif program.name != data["program"]["name"]:
        report.warnings.append(
            f"Program {program.slug!r} already exists as {program.name!r}. "
            "Its details are kept as they are."
        )
    if award is None:
        report.creates.append(f"Award: {data['award']['name']}")
    elif award.name != data["award"]["name"]:
        report.warnings.append(
            f"Award {award.slug!r} already exists as {award.name!r}. Its details are kept as they are."
        )

    if existing is not None:
        target = existing.award_version
        if existing.content_sha256 == digest and target is not None:
            report.unchanged = True
            report.warnings.append(
                f"Import key {key!r} was already imported with this exact content. Nothing to do."
            )
            return data, report
        if target is None:
            report.creates.append(f"Draft version {label!r} with {report.node_count} requirement(s)")
        elif target.status == AwardVersion.Status.DRAFT:
            report.updates.append(
                f"Draft version {target.version_label!r}: replace its requirements "
                f"with {report.node_count} from the file"
            )
        else:
            report.conflicts.append(
                f"Import key {key!r} made version {target.version_label!r}, which is now "
                f"{target.status}. Published, archived and in-review versions are never changed. "
                "Use a new version label (and import key), or create a revision in the app."
            )
    elif version_row is not None:
        report.conflicts.append(
            f"Version {label!r} already exists for this award ({version_row.status}) and was not "
            "made by this import key. It will not be overwritten. Use a new version label."
        )
    else:
        report.creates.append(f"Draft version {label!r} with {report.node_count} requirement(s)")
    return data, report


# Commit -------------------------------------------------------------------------

def _create_nodes(version, items, parent, sources):
    for index, item in enumerate(items):
        children = item.get("children", [])
        logic = item.get("completion_logic") or (
            tree_rules.ALL if children else tree_rules.SINGLE
        )
        node = RequirementNode.objects.create(
            award_version=version,
            parent=parent,
            sort_order=index,
            display_number=item.get("display_number", ""),
            node_type=item.get("node_type")
            or (RequirementNode.NodeType.GROUP if children else RequirementNode.NodeType.ATOMIC),
            text=item["text"],
            text_origin=item.get("text_origin", RequirementNode.TextOrigin.USER_PROVIDED),
            source=sources.get(item.get("source")),
            completion_logic=logic,
            completion_count=item.get("completion_count"),
            condition_expression=item.get("condition_expression"),
            estimated_effort=item.get("estimated_effort", ""),
            safety_notes=item.get("safety_notes", ""),
            evidence_expectations=[x.strip() for x in item.get("evidence_expectations", [])],
        )
        RequirementActionTag.objects.bulk_create(
            RequirementActionTag(node=node, tag=tag, reviewed=False)
            for tag in dict.fromkeys(item.get("action_tags", []))
        )
        _create_nodes(version, children, node, sources)


def _version_values(v):
    values = {
        "source_status": v["source_status"],
        "rights_status": v.get("rights_status", AwardVersion.RightsStatus.UNKNOWN),
        "effective_from": date.fromisoformat(v["effective_from"]) if v.get("effective_from") else None,
        "effective_until": date.fromisoformat(v["effective_until"]) if v.get("effective_until") else None,
        "source_checked_at": _parse_when(v["source_checked_at"]) if v.get("source_checked_at") else None,
        "change_summary": v.get("change_summary", ""),
    }
    return values


@transaction.atomic
def commit_import(raw_or_data):
    """Run the import. Raises ImportRefused if there are errors, conflicts or nothing to do.

    Returns the draft AwardVersion.
    """
    data, report = plan_import(raw_or_data)
    if not report.can_commit:
        raise ImportRefused(report)
    # Lock the import key row (if any) so two imports cannot interleave.
    key = report.import_key
    record = (
        ImportRecord.objects.select_for_update().filter(import_key=key).first()
    )

    owner_values = _owner_values(data["program"]["owner"])
    owner, _ = ProgramOwner.objects.get_or_create(
        slug=owner_values["slug"], defaults=owner_values
    )
    p = data["program"]
    program, _ = Program.objects.get_or_create(
        owner=owner,
        slug=p["slug"],
        defaults={
            "name": p["name"],
            "program_type": p.get("program_type", ""),
            "description": p.get("description", ""),
            "is_custom": p.get("is_custom", p["owner"] == "self"),
            "status": Program.Status.ACTIVE,
        },
    )
    a = data["award"]
    award, _ = Award.objects.get_or_create(
        program=program,
        slug=a["slug"],
        defaults={
            "name": a["name"],
            "award_type": a.get("award_type", Award.AwardType.CUSTOM),
            "description": a.get("description", ""),
            "category": a.get("category", ""),
            "official_identifier": a.get("official_identifier", ""),
            "eligibility_notes": a.get("eligibility_notes", ""),
            "status": Award.Status.ACTIVE,
        },
    )

    sources = {}
    for s in data.get("sources", []):
        fields = {
            "title": s["title"],
            "publisher_or_creator": s.get("publisher_or_creator", ""),
            "url": s.get("url", ""),
            "source_type": s.get("source_type", SourceRecord.SourceType.OTHER),
        }
        existing = SourceRecord.objects.filter(**fields).first()
        sources[s["key"]] = existing or SourceRecord.objects.create(
            **fields,
            license_or_permission_notes=s.get("license_or_permission_notes", ""),
            attribution_requirements=s.get("attribution_requirements", ""),
            review_status=s.get("review_status", SourceRecord.ReviewStatus.UNREVIEWED),
        )

    v = data["version"]
    values = _version_values(v)
    digest = content_hash(data)
    version = record.award_version if record else None
    if version is not None:
        # plan_import already confirmed this is a draft.
        version = AwardVersion.objects.select_for_update().get(pk=version.pk)
        for name, value in values.items():
            setattr(version, name, value)
        version.save()
        RequirementNode.objects.filter(award_version=version).delete()
    else:
        version = AwardVersion.objects.create(
            award=award, version_label=v["label"], status=AwardVersion.Status.DRAFT, **values
        )
    _create_nodes(version, data["requirements"], None, sources)

    if record is None:
        ImportRecord.objects.create(import_key=key, content_sha256=digest, award_version=version)
    else:
        record.content_sha256 = digest
        record.award_version = version
        record.save()
    return version
