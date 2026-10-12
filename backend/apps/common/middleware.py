import logging
import time
import uuid

logger = logging.getLogger("apps.common.requests")


class RequestObservabilityMiddleware:
    """Log bounded route metadata without request bodies, URLs, or identifiers."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex
        start = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        match = getattr(request, "resolver_match", None)
        route = getattr(match, "route", "unmatched") or "unmatched"
        logger.info("request completed", extra={"request_id": request.request_id, "method": request.method[:10], "route": route[:300], "status": response.status_code, "duration_ms": round((time.monotonic() - start) * 1000, 2)})
        if getattr(request, "user", None) and request.user.is_authenticated or any(segment in route for segment in ["auth/", "marketing/consent/", "management/", "full-checks/", "verification", "complaints", "free-checks/"]):
            response["Cache-Control"] = "no-store"
        return response
