from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class LiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT PostGIS_Version()")
                postgis_version = cursor.fetchone()[0]
            cache.set("health:ready", "ok", timeout=5)
            redis_ready = cache.get("health:ready") == "ok"
        except Exception:
            return Response({"status": "not_ready"}, status=503)
        if not redis_ready:
            return Response({"status": "not_ready"}, status=503)
        return Response({"status": "ready", "database": "postgis", "postgis_version": postgis_version, "redis": "ok"})
