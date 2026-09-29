# Endpoints auth-api (protocolo ZeroAuth do ORI, contrato do hook IAT)
from ._auth import handler

def handler(request):
    return handler(request, "check-app-status")
