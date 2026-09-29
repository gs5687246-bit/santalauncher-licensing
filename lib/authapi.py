# lib/authapi.py - lógica comum dos endpoints auth-api (protocolo ZeroAuth)
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import kv
from lib import zeroauth as za


class Req:
    """Adaptador simples para o request da Vercel (handler(request))."""
    def __init__(self, request):
        self._r = request
        q = getattr(request, "query", None) or getattr(request, "args", None) or {}
        self._query = q
        self.body_raw = request.body or b""

    def get_query(self, name, default=""):
        try:
            return self._query.get(name, default)
        except Exception:
            return default

    def json(self):
        raw = self.body_raw
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def headers(self, name):
        return self._r.headers.get(name, "")


def handle(request, kind):
    if kind == "health":
        db = request.get_query("appDatabase", "")
        return za.r_health(db)
    body = request.json()
    if kind == "check-app-status":
        return za.r_check_app_status(body)
    if kind == "log-login":
        return za.r_log_login()
    if kind == "login":
        key = (body.get("key") or body.get("usernameOrKey") or "").strip()
        hwid = (body.get("hwid") or "").strip()
        if not key or not hwid or not body.get("appid") or not body.get("appDatabase"):
            return ('{"message":"key, hwid, appid e appDatabase são obrigatórios"}',
                    400, {"Content-Type": "application/json"})
        if body.get("appDatabase") != za.APP_DATABASE or body.get("appid") != za.APP_ID:
            return ('{"message":"AppID inválido!"}', 400,
                    {"Content-Type": "application/json"})
        lic = kv.lic_ativa(key)
        if not lic:
            return ('{"message":"Key inválida!"}', 404,
                    {"Content-Type": "application/json"})
        salvo = lic.get("hwid") or ""
        if salvo and salvo != hwid:
            return ('{"message":"HWID mismatch!"}', 403,
                    {"Content-Type": "application/json"})
        kv.set_lic(key, {**lic, "hwid": hwid, "last_login": time.time()})
        return za.r_login(body, lic)
    if kind == "get-expiration":
        key = (body.get("key") or "").strip()
        lic = kv.lic_ativa(key)
        if not lic:
            return ('{"message":"Key inválida!"}', 404,
                    {"Content-Type": "application/json"})
        return za.r_get_expiration(lic)
    return ('{"message":"endpoint desconhecido"}', 404,
            {"Content-Type": "application/json"})
