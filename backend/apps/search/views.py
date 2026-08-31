from decimal import Decimal, InvalidOperation

from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import SearchResultSerializer


def _parse_types(raw_value):
    if not raw_value:
        return set(services.ALLOWED_TYPES)
    requested = {t.strip() for t in raw_value.split(",") if t.strip()}
    invalid = requested - services.ALLOWED_TYPES
    if invalid:
        raise ValidationError(
            {
                "types": (
                    f"Invalid type(s): {', '.join(sorted(invalid))}. "
                    f"Allowed: {', '.join(sorted(services.ALLOWED_TYPES))}."
                )
            }
        )
    return requested


def _parse_decimal(raw_value, field_name):
    if raw_value in (None, ""):
        return None
    try:
        return Decimal(raw_value)
    except InvalidOperation:
        raise ValidationError({field_name: f"'{raw_value}' is not a valid number."})


def _parse_float(raw_value, field_name):
    if raw_value in (None, ""):
        return None
    try:
        return float(raw_value)
    except ValueError:
        raise ValidationError({field_name: f"'{raw_value}' is not a valid number."})


def _build_filters(params):
    return {
        "q": params.get("q", "").strip(),
        "category": params.get("category", "").strip(),
        "city": params.get("city", "").strip(),
        "province": params.get("province", "").strip(),
        "area": params.get("area", "").strip(),
        "price_min": _parse_decimal(params.get("price_min"), "price_min"),
        "price_max": _parse_decimal(params.get("price_max"), "price_max"),
        # min_rating and is_verified are accepted but deliberately
        # unused: no rating field exists in any Phase 1-6 model, and
        # every result returned is already the domain's own definition
        # of "verified"/publicly visible — see services.py docstring.
    }


class UnifiedSearchView(APIView):
    """
    GET /api/v1/search/

    Searches across Businesses, Services, Jobs, and Marketplace
    listings, returning only records each domain's own rules already
    consider publicly visible (see apps.search.services). Results
    from all requested types are merged and sorted by recency, then
    paginated.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        params = request.query_params
        types = _parse_types(params.get("types"))
        filters = _build_filters(params)

        results = services.unified_search(filters, types)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(results, request, view=self)
        serializer = SearchResultSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NearbySearchView(APIView):
    """
    GET /api/v1/search/nearby/

    Location-based discovery. With only province/city/area supplied,
    behaves like the unified search but without text matching. If
    latitude, longitude, AND radius_km are all supplied, Businesses
    are additionally matched by true great-circle distance (see
    apps.search.services.businesses_near) — Business is the only
    model in Phases 1-6 that stores coordinates, so Jobs, Services,
    and Marketplace listings fall back to province/city/area
    filtering only in radius mode (documented limitation).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        params = request.query_params
        types = _parse_types(params.get("types"))
        filters = _build_filters(params)

        latitude = _parse_float(params.get("latitude"), "latitude")
        longitude = _parse_float(params.get("longitude"), "longitude")
        radius_km = _parse_float(params.get("radius_km"), "radius_km")

        provided = [v is not None for v in (latitude, longitude, radius_km)]
        if any(provided) and not all(provided):
            raise ValidationError(
                "latitude, longitude, and radius_km must all be provided together "
                "for a radius search."
            )
        if radius_km is not None and radius_km <= 0:
            raise ValidationError({"radius_km": "radius_km must be greater than 0."})
        if latitude is not None and not (-90 <= latitude <= 90):
            raise ValidationError({"latitude": "latitude must be between -90 and 90."})
        if longitude is not None and not (-180 <= longitude <= 180):
            raise ValidationError(
                {"longitude": "longitude must be between -180 and 180."}
            )

        results = services.nearby_search(
            filters, types, latitude=latitude, longitude=longitude, radius_km=radius_km
        )

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(results, request, view=self)
        serializer = SearchResultSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
