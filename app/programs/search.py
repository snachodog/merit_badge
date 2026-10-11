"""Catalog search using PostgreSQL full-text search plus plain substring matching.

No extra infrastructure. Full-text finds word forms ("walks" for "walk");
substring matching finds partial words. Both run on the live tables, which
is fast enough for a single-user catalog.
"""
from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db.models import Q

from requirements.models import RequirementNode

from .models import Award

MAX_QUERY = 200


def _query(q):
    return SearchQuery(q, config="english", search_type="websearch")


def matching_nodes(q):
    """Requirement nodes whose text matches."""
    return RequirementNode.objects.annotate(
        sv=SearchVector("text", config="english")
    ).filter(Q(sv=_query(q)) | Q(text__icontains=q))


def search_awards(q):
    """Return (awards queryset, set of version ids whose requirement text matched)."""
    awards = Award.objects.select_related("program", "program__owner").prefetch_related("versions")
    q = (q or "").strip()[:MAX_QUERY]
    if not q:
        return awards.order_by("program__name", "name"), set()
    node_hits = matching_nodes(q)
    version_ids = set(node_hits.values_list("award_version_id", flat=True))
    award_ids_from_text = node_hits.values("award_version__award_id")
    awards = awards.annotate(
        sv=SearchVector("name", "description", "category", "program__name", config="english")
    ).filter(
        Q(sv=_query(q))
        | Q(name__icontains=q)
        | Q(description__icontains=q)
        | Q(category__icontains=q)
        | Q(program__name__icontains=q)
        | Q(id__in=award_ids_from_text)
    )
    return awards.order_by("program__name", "name"), version_ids
