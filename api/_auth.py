# api/_auth.py - endpoint handler comum para a API auth-api (protocolo ORI)
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib import kv
from lib import zeroauth as za

def read_body(request):
    try:
        raw = request.body
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        return json.loads(raw or "{}")
    except Exception:
        return {}

def handler(request, kind):
    if kind == "health":
        return za.r_health(request.args.get("appDatabase", ""))
    body = read_body(request)
    if kind == "check-app-status":
        return za.r_check_app_status(body)
    if kind == "log-login":
        return za.r_log_login()
    if kind == "login":
        key = (body.get("key") or body.get("usernameOrKey") or "").strip()
        hwid = (body.get("hwid") or "").strip()
        if not key or not hwid or not body.get("appid") or not body.get("appDatabase"):
            return ("{\"message\":\"key, hwid, appid e appDatabase são obrigatórios\"}",
                    400, {"Content-Type": "application/json"})
        if body.get("appDatabase") != za.APP_DATABASE or body.get("appid") != za.APP_ID:
            return ("{\"message\":\"AppID inválido!\"}", 400,
                    {"Content-Type": "application/json"})
        lic = kv.lic_ativa(key)
        if not lic:
            return ("{\"message\":\"Key inválida!\"}", 404,
                    {"Content-Type": "application/json"})
        salvo = lic.get("hwid") or ""
        if salvo and salvo != hwid:
            return ("{\"message\":\"HWID mismatch!\"}", 403,
                    {"Content-Type": "application/json"})
        kv.set_lic(key, {**lic, "hwid": hwid, "last_login": time_now()})
        return za.r_login(body, lic)
    if kind == "get-expiration":
        key = (body.get("key") or "").strip()
        lic = kv.lic_ativa(key)
        if not lic:
            return ("{\"message\":\"Key inválida!\"}", 404,
                    {"Content-Type": "application/json"})
        return za.r_get_expiration(lic)
    return ("{\"message\":\"endpoint desconhecido\"}", 404,
            {"Content-Type": "application/json"})

def time_now():
    import time
    return time.time()
