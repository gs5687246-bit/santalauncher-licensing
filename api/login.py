from ._auth import handler

def handler(request):
    return handler(request, "login")
