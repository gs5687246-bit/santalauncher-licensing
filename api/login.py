# login - /api/auth-api/login
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.authapi import Req, handle

def handler(request):
    return handle(Req(request), "login")
