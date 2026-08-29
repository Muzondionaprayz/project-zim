from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    Unauthenticated liveness/readiness probe for the Foundation phase.

    Confirms the API process is up and that it can reach the configured
    database. Intentionally has no domain logic — future feature apps
    (accounts, etc.) get their own endpoints under /api/v1/.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        database_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
        except Exception:
            database_ok = False

        return Response(
            {
                "status": "ok" if database_ok else "degraded",
                "database": database_ok,
            }
        )
