from rest_framework import serializers


class SearchResultSerializer(serializers.Serializer):
    """
    Uniform shape for a single search result, regardless of which
    domain it came from. Built from a plain dict (see
    apps.search.services._result), not a model instance — there is
    no SearchResult model.

    Deliberately excludes owner/employer/seller identity, moderation
    notes, private contact fields, and internal status fields — none
    of that is included in the dicts this serializer is fed, so
    there's nothing to accidentally leak.
    """

    entity_type = serializers.ChoiceField(
        choices=["business", "service", "job", "marketplace"]
    )
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    category = serializers.CharField(allow_null=True)
    city = serializers.CharField(allow_blank=True)
    province = serializers.CharField(allow_blank=True)
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True, required=False
    )
    rating = serializers.FloatField(allow_null=True, required=False)
    detail_path = serializers.CharField()
    distance_km = serializers.FloatField(required=False)
