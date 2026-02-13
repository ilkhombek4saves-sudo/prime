import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["x-trace-id"] = request.state.trace_id
        return response
