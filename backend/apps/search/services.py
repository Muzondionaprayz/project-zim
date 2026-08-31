"""
Cross-domain search/aggregation logic.

Isolated from views, same convention as apps.businesses.services,
apps.services.services, apps.jobs.services, apps.marketplace.services
— even though this module reads rather than mutates. Each per-domain
search function re-derives the *exact* public-visibility filter the
domain's own PublicXListView already enforces; it never loosens it.
If a domain's visibility rule ever changes, that change happens in
one place (the domain's own view) and must be mirrored here — this
module does not invent a parallel definition of "public".

No rating field exists anywhere in Phases 1-6, so `min_rating` is
accepted as a parameter but never filters anything (see views.py) —
this deliberately avoids inventing a Reviews/Ratings system as part
of Search.
"""

from django.db.models import ExpressionWrapper, F, FloatField, Q, Value
from django.db.models.functions import ACos, Cast, Cos, Greatest, Least, Radians, Sin
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.jobs.models import Job
from apps.marketplace.models import MarketplaceListing
from apps.services.models import Service

# Bounds how many already-DB-filtered candidates per domain are
# pulled into Python for the final cross-domain sort/merge. Keeps
# memory bounded without needing a shared search table/index.
MAX_CANDIDATES_PER_DOMAIN = 500

ALLOWED_TYPES = {"businesses", "services", "jobs", "marketplace"}
EARTH_RADIUS_KM = 6371.0


def _result(
    *,
    entity_type,
    obj,
    title,
    description,
    category_name,
    city,
    province,
    price,
    detail_path,
):
    return {
        "entity_type": entity_type,
        "id": obj.id,
        "title": title,
        "description": description or "",
        "category": category_name,
        "city": city or "",
        "province": province or "",
        "price": price,
        "rating": None,  # no rating system exists yet (see module docstring)
        "detail_path": detail_path,
        "created_at": obj.created_at,
    }


def _apply_business_filters(qs, f):
    if f.get("q"):
        qs = qs.filter(Q(name__icontains=f["q"]) | Q(description__icontains=f["q"]))
    if f.get("category"):
        qs = qs.filter(category__slug=f["category"])
    if f.get("city"):
        qs = qs.filter(city__iexact=f["city"])
    if f.get("province"):
        qs = qs.filter(province__iexact=f["province"])
    if f.get("area"):
        qs = qs.filter(address__icontains=f["area"])
    return qs


def _business_result(b):
    return _result(
        entity_type="business",
        obj=b,
        title=b.name,
        description=b.description,
        category_name=b.category.name if b.category else None,
        city=b.city,
        province=b.province,
        price=None,
        detail_path=reverse("businesses:public-detail", kwargs={"pk": b.pk}),
    )


def search_businesses(f):
    qs = Business.objects.filter(status=Business.Status.APPROVED).select_related(
        "category"
    )
    qs = _apply_business_filters(qs, f)
    qs = qs.order_by("-created_at")[:MAX_CANDIDATES_PER_DOMAIN]
    return [_business_result(b) for b in qs]


def businesses_near(latitude, longitude, radius_km, f):
    """
    Business is the only model in Phases 1-6 that stores coordinates,
    so true lat/long radius search applies to Businesses only (see
    apps.search.views.NearbySearchView docstring for the documented
    limitation on Jobs/Services/Marketplace).

    Uses the standard spherical law-of-cosines great-circle distance
    formula via Django's built-in trig ORM functions — no PostGIS or
    other extension required. The inner cosine expression is clamped
    to [-1, 1] to guard against acos() domain errors caused by
    floating-point rounding at (near-)identical coordinates.
    """
    qs = Business.objects.filter(
        status=Business.Status.APPROVED,
        latitude__isnull=False,
        longitude__isnull=False,
    ).select_related("category")
    qs = _apply_business_filters(qs, f)

    lat_value = Value(latitude, output_field=FloatField())
    lng_value = Value(longitude, output_field=FloatField())
    db_lat = Cast(F("latitude"), FloatField())
    db_lng = Cast(F("longitude"), FloatField())

    angular_distance = (
        Cos(Radians(lat_value)) * Cos(Radians(db_lat))
        * Cos(Radians(db_lng) - Radians(lng_value))
        + Sin(Radians(lat_value)) * Sin(Radians(db_lat))
    )
    clamped = Least(
        Value(1.0, output_field=FloatField()),
        Greatest(Value(-1.0, output_field=FloatField()), angular_distance),
    )

    qs = qs.annotate(
        distance_km=ExpressionWrapper(
            ACos(clamped) * EARTH_RADIUS_KM, output_field=FloatField()
        )
    ).filter(distance_km__lte=radius_km).order_by("distance_km")[
        :MAX_CANDIDATES_PER_DOMAIN
    ]

    results = []
    for b in qs:
        result = _business_result(b)
        result["distance_km"] = round(b.distance_km, 2)
        results.append(result)
    return results


def search_services(f):
    qs = Service.objects.filter(
        is_active=True, business__status=Business.Status.APPROVED
    ).select_related("category", "business")
    if f.get("q"):
        qs = qs.filter(Q(title__icontains=f["q"]) | Q(description__icontains=f["q"]))
    if f.get("category"):
        qs = qs.filter(category__slug=f["category"])
    if f.get("city"):
        qs = qs.filter(business__city__iexact=f["city"])
    if f.get("province"):
        qs = qs.filter(business__province__iexact=f["province"])
    if f.get("area"):
        qs = qs.filter(business__address__icontains=f["area"])
    if f.get("price_min") is not None:
        qs = qs.filter(price__gte=f["price_min"])
    if f.get("price_max") is not None:
        qs = qs.filter(price__lte=f["price_max"])

    qs = qs.order_by("-created_at")[:MAX_CANDIDATES_PER_DOMAIN]

    return [
        _result(
            entity_type="service",
            obj=s,
            title=s.title,
            description=s.description,
            category_name=s.category.name if s.category else None,
            city=s.business.city,
            province=s.business.province,
            price=s.price,
            detail_path=reverse("services:public-detail", kwargs={"pk": s.pk}),
        )
        for s in qs
    ]


def search_jobs(f):
    qs = Job.objects.filter(status=Job.Status.OPEN).filter(
        Q(deadline__isnull=True) | Q(deadline__gt=timezone.now())
    ).select_related("category")
    if f.get("q"):
        qs = qs.filter(Q(title__icontains=f["q"]) | Q(description__icontains=f["q"]))
    if f.get("category"):
        qs = qs.filter(category__slug=f["category"])
    if f.get("city"):
        qs = qs.filter(city__iexact=f["city"])
    if f.get("province"):
        qs = qs.filter(province__iexact=f["province"])
    # Job has no address/area field (see known limitations) — "area"
    # is intentionally not applied here.
    if f.get("price_min") is not None:
        qs = qs.filter(budget__gte=f["price_min"])
    if f.get("price_max") is not None:
        qs = qs.filter(budget__lte=f["price_max"])

    qs = qs.order_by("-created_at")[:MAX_CANDIDATES_PER_DOMAIN]

    return [
        _result(
            entity_type="job",
            obj=j,
            title=j.title,
            description=j.description,
            category_name=j.category.name if j.category else None,
            city=j.city,
            province=j.province,
            price=j.budget,
            detail_path=reverse("jobs:public-detail", kwargs={"pk": j.pk}),
        )
        for j in qs
    ]


def search_marketplace(f):
    qs = MarketplaceListing.objects.filter(
        status=MarketplaceListing.Status.PUBLISHED,
        moderation_status=MarketplaceListing.ModerationStatus.APPROVED,
    ).select_related("category")
    if f.get("q"):
        qs = qs.filter(Q(title__icontains=f["q"]) | Q(description__icontains=f["q"]))
    if f.get("category"):
        qs = qs.filter(category__slug=f["category"])
    if f.get("city"):
        qs = qs.filter(city__iexact=f["city"])
    if f.get("province"):
        qs = qs.filter(province__iexact=f["province"])
    if f.get("area"):
        qs = qs.filter(address__icontains=f["area"])
    if f.get("price_min") is not None:
        qs = qs.filter(price__gte=f["price_min"])
    if f.get("price_max") is not None:
        qs = qs.filter(price__lte=f["price_max"])

    qs = qs.order_by("-created_at")[:MAX_CANDIDATES_PER_DOMAIN]

    return [
        _result(
            entity_type="marketplace",
            obj=m,
            title=m.title,
            description=m.description,
            category_name=m.category.name if m.category else None,
            city=m.city,
            province=m.province,
            price=m.price,
            detail_path=reverse("marketplace:public-detail", kwargs={"pk": m.pk}),
        )
        for m in qs
    ]


_DOMAIN_SEARCHERS = {
    "businesses": search_businesses,
    "services": search_services,
    "jobs": search_jobs,
    "marketplace": search_marketplace,
}


def unified_search(filters, types):
    """
    Runs the requested per-domain searches (each already filtered at
    the DB level to that domain's own public-visibility rule) and
    merges the results, most recent first.
    """
    results = []
    for entity_type in types:
        results.extend(_DOMAIN_SEARCHERS[entity_type](filters))
    results.sort(key=lambda r: r["created_at"], reverse=True)
    return results


def nearby_search(filters, types, latitude=None, longitude=None, radius_km=None):
    """
    Location-only search. If latitude/longitude/radius_km are all
    provided, Businesses are matched by true great-circle distance
    (see businesses_near) and other domain types fall back to
    province/city/area filtering only (they have no coordinates to
    compute a radius against — see NearbySearchView docstring).
    Otherwise every requested type is filtered by province/city/area
    alone, same as unified_search with no `q`.
    """
    if latitude is not None and longitude is not None and radius_km is not None:
        business_results = (
            businesses_near(latitude, longitude, radius_km, filters)
            if "businesses" in types
            else []
        )
        other_results = []
        for entity_type in types:
            if entity_type == "businesses":
                continue
            other_results.extend(_DOMAIN_SEARCHERS[entity_type](filters))
        other_results.sort(key=lambda r: r["created_at"], reverse=True)
        # Distance ordering (closest first) is the point of a radius
        # search, so business results keep their distance order and
        # are listed first; other types (no coordinates) follow by
        # recency.
        return business_results + other_results

    return unified_search(filters, types)
