# lib/zeroauth.py - Respostas no contrato EXATO da SDK ZeroAuth do ORI
# (capturado no hook IAT do exe oficial — sync_hook.c).
import json, time

APP_DATABASE = "199ww-swhrrx7k"
APP_ID = "SYNC PREMIUM"

def _resp(data, status=200):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (body, status, {"Content-Type": "application/json"})

def r_health(db):
    if not db:
        return _resp({"message": "appDatabase não fornecido"}, 400)
    return _resp({
        "success": True, "healthy": True, "version": "1.0.0",
        "message": "API saudável e operando normalmente!",
        "status": "API em operação", "online": True, "enabled": True,
        "initialized": True, "maintenance": False, "banned": False,
        "uptime": time.time(), "appDatabase": db,
    })

def r_check_app_status(body):
    if body.get("appDatabase") != APP_DATABASE or body.get("appid") != APP_ID:
        return _resp({"message": "AppID inválido!"}, 400)
    return _resp({
        "success": True,
        "sessionid": "SESSION_SYNC_0001",
        "token": "TOKEN_SYNC_0001",
        "initialized": True, "Initialized": True,
        "enabled": True, "status": "active", "version": "1.0.0",
        "appid": APP_ID, "appDatabase": APP_DATABASE,
        "forceUpdate": False, "message": "Initialized", "newSession": True,
    })

def r_login(body, lic):
    key = (body.get("key") or body.get("usernameOrKey") or "").strip()
    hwid = body.get("hwid") or ""
    exp = lic.get("expira", 0)
    expires = (time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(exp))
               if exp else "2099-01-01T00:00:00.000Z")
    days = max(0, int((exp - time.time()) / 86400)) if exp else 9999
    return _resp({
        "success": True, "message": "Login bem-sucedido!", "status": "ok",
        "healthy": True, "isKeyLogin": True,
        "usernameOrKey": key, "hwid": hwid,
        "appDatabase": APP_DATABASE, "appid": APP_ID, "ipInfo": {},
        "computerUsername": body.get("computerUsername") or "",
        "sessionToken": f"sess_{key}_{int(time.time())}",
        "token": f"sess_{key}_{int(time.time())}",
        "expiresAt": expires,
        "subscriptionDaysLeft": days,
        "isLifetime": exp == 0,
    })

def r_log_login():
    return _resp({"success": True, "message": "Logged"})

def r_get_expiration(lic):
    exp = lic.get("expira", 0)
    expires = (time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(exp))
               if exp else "2099-01-01T00:00:00.000Z")
    days = max(0, int((exp - time.time()) / 86400)) if exp else 9999
    return _resp({
        "success": True, "expiresAt": expires,
        "subscriptionDaysLeft": days, "isLifetime": exp == 0,
        "status": "ACTIVE",
    })
