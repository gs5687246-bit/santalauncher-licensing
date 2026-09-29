# app.py - SantaLauncher Licensing (API auth-api ZeroAuth-compatible +
# Discord Interactions) — FastAPI, entrypoint único da Vercel.
import json, os, sys, time, base64, urllib.request

UA = "Mozilla/5.0 (compatible, DiscordBot)"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import kv
from lib import zeroauth as za

from fastapi import FastAPI, Request, Response

app = FastAPI(title="SantaLauncher Licensing", docs_url=None, redoc_url=None)

def J(data, status=200):
    # data pode ser dict (serializa) ou str JSON pronta (usa direto)
    body = data if isinstance(data, str) else json.dumps(
        data, ensure_ascii=False, separators=(",", ":"))
    return Response(content=body, status_code=status, media_type="application/json")

async def _json_body(request: Request):
    try:
        raw = await request.body()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        return json.loads(raw or "{}")
    except Exception:
        return {}

# ── API auth-api (protocolo do launcher) ─────────────────────────
@app.get("/api/auth-api/health")
async def health(appDatabase: str = ""):
    body, status, _ = za.r_health(appDatabase)
    return J(body, status)

@app.post("/api/auth-api/check-app-status")
async def check_app_status(request: Request):
    return J(*_pair(za.r_check_app_status(await _json_body(request))))

@app.post("/api/auth-api/login")
async def login(request: Request):
    body = await _json_body(request)
    key = (body.get("key") or body.get("usernameOrKey") or "").strip()
    hwid = (body.get("hwid") or "").strip()
    if not key or not hwid or not body.get("appid") or not body.get("appDatabase"):
        return J({"message": "key, hwid, appid e appDatabase são obrigatórios"}, 400)
    if body.get("appDatabase") != za.APP_DATABASE or body.get("appid") != za.APP_ID:
        return J({"message": "AppID inválido!"}, 400)
    lic = kv.lic_ativa(key)
    if not lic:
        return J({"message": "Key inválida!"}, 404)
    salvo = lic.get("hwid") or ""
    if salvo and salvo != hwid:
        return J({"message": "HWID mismatch!"}, 403)
    kv.set_lic(key, {**lic, "hwid": hwid, "last_login": time.time()})
    return J(*_pair(za.r_login(body, lic)))

@app.post("/api/auth-api/log-login")
async def log_login(request: Request):
    return J(*_pair(za.r_log_login()))

@app.post("/api/auth-api/get-expiration")
async def get_expiration(request: Request):
    body = await _json_body(request)
    key = (body.get("key") or "").strip()
    lic = kv.lic_ativa(key)
    if not lic:
        return J({"message": "Key inválida!"}, 404)
    return J(*_pair(za.r_get_expiration(lic)))

def _pair(t):
    """Converte (body, status, headers) ou (body, status) em (body, status)."""
    return (t[0], t[1])

@app.get("/")
async def root():
    return J({"name": "SantaLauncher Licensing (ZeroAuth-compatible)", "ok": True})

# ── Discord Interactions (slash commands) ────────────────────────
PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
APP_ID_ENV = os.environ.get("DISCORD_APPLICATION_ID", "")

def _verify_sig(request: Request, body: bytes) -> bool:
    if not PUBLIC_KEY:
        return True  # dev sem key configurada
    sig = request.headers.get("x-signature-ed25519", "")
    ts = request.headers.get("x-signature-timestamp", "")
    if not sig or not ts:
        return False
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        VerifyKey(bytes.fromhex(PUBLIC_KEY)).verify(ts.encode() + body, bytes.fromhex(sig))
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False

def _is_admin(member):
    perms = int((member or {}).get("permissions", "0") or 0)
    return bool(perms & 0x8) or bool(perms & 0x20)

def _reply(content, eph=False):
    return {"type": 4, "data": {"content": content, "flags": 64 if eph else 0}}

def _register_commands():
    if not BOT_TOKEN or not APP_ID_ENV:
        return
    cmds = [
        {"name": "add", "description": "Adiciona licença do SantaLauncher",
         "options": [
            {"name": "discord_id", "description": "ID do Discord", "type": 3, "required": True},
            {"name": "dias", "description": "Dias (0 = vitalícia)", "type": 4, "required": False}]},
        {"name": "remove", "description": "Remove licença",
         "options": [{"name": "discord_id", "description": "ID do Discord", "type": 3, "required": True}]},
        {"name": "list", "description": "Lista todas as licenças"},
        {"name": "status", "description": "Status de uma licença",
         "options": [{"name": "discord_id", "description": "ID do Discord", "type": 3, "required": True}]},
        {"name": "pingbot", "description": "Testa a API de licenças"},
    ]
    url = f"https://discord.com/api/v10/applications/{APP_ID_ENV}/commands"
    req = urllib.request.Request(url, method="PUT", data=json.dumps(cmds).encode(),
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json",
                 "User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass

@app.post("/api/interactions")
async def interactions(request: Request):
    body = await request.body()
    if not _verify_sig(request, body):
        return Response(content='{"error":"bad signature"}', status_code=401,
                        media_type="application/json")
    data = json.loads(body.decode("utf-8", "replace") or "{}")
    if data.get("type") == 1:            # PING
        _register_commands()
        return {"type": 1}
    if data.get("type") != 2:
        return {"type": 5}
    name = data["data"]["name"]
    opts = {o["name"]: o.get("value") for o in data["data"].get("options", [])}
    member = data.get("member") or {}
    user = (member.get("user") or data.get("user") or {}).get("username", "?")
    did = str(opts.get("discord_id") or "").strip()

    if name == "pingbot":
        return _reply("🤖 API de licenças online (Vercel)")
    if not _is_admin(member):
        return _reply("❌ Apenas administradores.", eph=True)

    if name == "add":
        if not did:
            return _reply("Uso: `/add discord_id:123 dias:30`", eph=True)
        dias = int(opts.get("dias") or 0)
        kv.set_lic(did, {
            "ativa": True,
            "expira": 0 if dias <= 0 else time.time() + dias * 86400,
            "criada_por": user, "criada_em": time.time(), "hwid": "",
        })
        return _reply(f"✅ Licença adicionada para `{did}`"
                      + (f" ({dias} dias)" if dias > 0 else " (vitalícia)"))

    if name == "remove":
        if not did:
            return _reply("Uso: `/remove discord_id:123`", eph=True)
        return _reply(("🗑️ Licença de `%s` removida." % did) if kv.del_lic(did)
                      else ("⚠️ `%s` não existe." % did), eph=True)

    if name == "list":
        d = kv.all_lic()
        if not d:
            return _reply("Nenhuma licença.", eph=True)
        linhas = []
        for k, lic in sorted(d.items()):
            exp = lic.get("expira", 0)
            exps = "vitalícia" if not exp else time.strftime("%d/%m/%Y", time.gmtime(exp))
            linhas.append(f"`{k}` — {exps}")
        return _reply("**Licenças (%d):**\n" % len(d) + "\n".join(linhas[:40]), eph=True)

    if name == "status":
        if not did:
            return _reply("Uso: `/status discord_id:123`", eph=True)
        lic = kv.lic_ativa(did)
        if not lic:
            return _reply(f"❌ `{did}` sem licença ativa.")
        exp = lic.get("expira", 0)
        exps = "vitalícia" if not exp else time.strftime("%d/%m/%Y %H:%M", time.gmtime(exp))
        hw = lic.get("hwid") or "livre"
        return _reply(f"✅ `{did}` — ativa até {exps} | HWID: `{hw[:18]}…`")

    return _reply("Comando desconhecido.", eph=True)

@app.get("/api/debug")
async def debug(register: int = 0):
    """Diagnóstico: estado das env vars e dos comandos (sem expor segredos)."""
    reg_status = None
    if register and BOT_TOKEN and APP_ID_ENV:
        try:
            _register_commands()
            reg_status = "registrado (ou já existia)"
        except Exception as e:
            reg_status = f"erro: {e!r}"[:120]
    return J({**{k: v for k, v in {
        "public_key": bool(PUBLIC_KEY), "bot_token": bool(BOT_TOKEN),
        "application_id_set": bool(APP_ID_ENV),
        "application_id": APP_ID_ENV or None, "kv": bool(os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")),
        "reg_status": reg_status}.items()},
        "commands": _list_commands()})

def _list_commands():
    if not (BOT_TOKEN and APP_ID_ENV):
        return None
    try:
        req = urllib.request.Request(
            f"https://discord.com/api/v10/applications/{APP_ID_ENV}/commands",
            headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as x:
            return [c["name"] for c in json.loads(x.read().decode())]
    except Exception as e:
        return f"erro: {e!r}"[:120]
    st = {
        "public_key": bool(PUBLIC_KEY),
        "bot_token": bool(BOT_TOKEN),
        "application_id_set": bool(APP_ID_ENV),
        "application_id": APP_ID_ENV or None,
        "kv": bool(os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")),
    }
    if BOT_TOKEN:
        st["token_shape"] = {"len": len(BOT_TOKEN),
                             "prefix": BOT_TOKEN[:6],
                             "sufix": BOT_TOKEN[-4:],
                             "tem_espaco": (" " in BOT_TOKEN.strip()),
                             "tem_quebra": ("\n" in BOT_TOKEN or "\r" in BOT_TOKEN),
                             "comeca_bot_": BOT_TOKEN.startswith("Bot ")}
        try:
            req = urllib.request.Request("https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {BOT_TOKEN.strip()}", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=10) as x:
                me = json.loads(x.read().decode())
            st["token_app_id"] = me.get("id")
            st["token_bot_name"] = me.get("username")
        except Exception as e:
            st["token_app_id"] = f"erro: {e!r}"[:120]
    return J(st)
