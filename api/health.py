# api/health.py - GET /api/health?appDatabase=...
from ._auth import handler

def handler_v(request):
    return handler(request, "health")
