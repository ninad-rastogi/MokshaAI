"""Request correlation for API logs and client troubleshooting."""

import logging
import uuid

logger = logging.getLogger("moksha.request")


class RequestIDMiddleware:
    """Attach an opaque request ID to each request and response."""

    header_name = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get(self.header_name, str(uuid.uuid4()))
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        logger.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra={"request_id": request.request_id},
        )
        return response
