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
    resp = za.r_login(body, lic)
    # bem-vindo com username Discord real (o ORI mostra o nome da conta):
    try:
        if key.isdigit() and BOT_TOKEN:
            _req = urllib.request.Request(
                f"https://discord.com/api/v10/users/{key}",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
            with urllib.request.urlopen(_req, timeout=6) as _x:
                _u = json.loads(_x.read().decode())
            _name = _u.get("username") or _u.get("global_name")
            if _name and isinstance(resp, (list, tuple)) and isinstance(resp[0], dict):
                resp[0]["usernameOrKey"] = _name
    except Exception:
        pass
    return J(*_pair(resp))

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

# Diagnostico da ultima interacao (visivel em /api/debug):
_last_sig_err = {"erro": None, "ts": None}

def _sig_fail(msg):
    _last_sig_err["erro"] = msg
    import time as _t
    _last_sig_err["ts"] = _t.strftime("%d/%m %H:%M:%S")
    return False

def _verify_sig(request: Request, body: bytes) -> bool:
    if not PUBLIC_KEY:
        return True  # dev sem key configurada
    sig = request.headers.get("x-signature-ed25519", "")
    ts = request.headers.get("x-signature-timestamp", "")
    if not sig or not ts:
        return _sig_fail("cabecalhos de assinatura ausentes")
    try:
        key_hex = "".join(PUBLIC_KEY.split())
        try:
            key_bytes = bytes.fromhex(key_hex)
        except Exception as e:
            return _sig_fail("PUBLIC_KEY nao e hex valido: %r" % e)
        if len(key_bytes) != 32:
            return _sig_fail("PUBLIC_KEY tem %d bytes (esperado 32)" % len(key_bytes))
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        VerifyKey(key_bytes).verify(ts.encode() + body, bytes.fromhex(sig))
        return True
    except BadSignatureError:
        return _sig_fail("assinatura invalida (key errada ou body alterado)")
    except ImportError as e:
        return _sig_fail("pynacl ausente no deploy: %r" % e)
    except Exception as e:
        return _sig_fail("erro validando: %r" % e)

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
        {"name": "nome", "description": "Define o nome exibido no launcher",
         "options": [
            {"name": "discord_id", "description": "ID do Discord", "type": 3, "required": True},
            {"name": "nome", "description": "Nome a exibir", "type": 3, "required": True}]},
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
    try:
        data = json.loads(body.decode("utf-8", "replace") or "{}")
    except Exception as e:
        _sig_fail("body nao e JSON: %r" % e)
        return Response(content='{"error":"bad json"}', status_code=400,
                        media_type="application/json")
    if data.get("type") == 1:            # PING
        _register_commands()
        return {"type": 1}
    if data.get("type") != 2:
        return {"type": 5}
    try:
        return _handle_command(data)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()[-600:]
        return _reply("Erro interno: `%r`\n```%s```" % (e, tb), eph=True)

def _handle_command(data):
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
        # nome de exibicao (mostrado no bem-vindo do launcher):
        nome = None
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{did}",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8) as x:
                m = json.loads(x.read().decode())
            nome = m.get("nick") or (m.get("user") or {}).get("global_name") \
                   or (m.get("user") or {}).get("username")
        except Exception:
            nome = None
        lic_prev = kv.get_lic(did) or {}
        kv.set_lic(did, {
            "ativa": True,
            "expira": 0 if dias <= 0 else time.time() + dias * 86400,
            "criada_por": user, "criada_em": time.time(), "hwid": "",
            "nome": lic_prev.get("nome") or nome or user,
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

    if name == "nome":
        if not did or not opts.get("nome"):
            return _reply("Uso: `/nome discord_id:123 nome:NovoNome`", eph=True)
        lic = kv.get_lic(did) or {}
        if not lic:
            return _reply(f"⚠️ `{did}` não tem licença. Use /add primeiro.", eph=True)
        kv.set_lic(did, {**lic, "nome": str(opts.get("nome"))[:32]})
        return _reply(f"✅ Nome de exibição de `{did}` = **{opts.get('nome')}**")

    return _reply("Comando desconhecido.", eph=True)

@app.get("/api/avatar")
async def avatar(did: str = "", debug: str = ""):
    """Avatar Discord do usuario em RGBA cru 64x64 (o launcher nao tem
    decoder de imagem). Resolve o avatar via API do bot; sem foto,
    usa o avatar default do Discord (indice did%6)."""
    did = "".join(ch for ch in did if ch.isdigit())[:20]
    if not did or not BOT_TOKEN:
        if debug:
            return Response(content="no_did_or_token", media_type="text/plain")
        return Response(content=b"\x00" * (64 * 64 * 4), media_type="application/octet-stream")
    png_bytes = None
    err = ""
    try:
        # retry 3x (cold start do Vercel + API do Discord falham 1x
        # as vezes — o launcher mostra avatar vazio se a rota falhar)
        u = None
        for _t in range(3):
            try:
                req = urllib.request.Request(
                    f"https://discord.com/api/v10/users/{did}",
                    headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
                with urllib.request.urlopen(req, timeout=8) as x:
                    u = json.loads(x.read().decode())
                break
            except Exception:
                if _t == 2: raise
        ah = u.get("avatar")
        if ah:
            ext = "gif" if ah.startswith("a_") else "png"
            url = f"https://cdn.discordapp.com/avatars/{did}/{ah}.{ext}?size=64"
        else:
            idx = int(did) % 6
            url = f"https://cdn.discordapp.com/embed/avatars/{idx}.png"
        for _t in range(3):
            try:
                req2 = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req2, timeout=8) as x:
                    png_bytes = x.read()
                break
            except Exception:
                if _t == 2: raise
    except Exception as e:
        png_bytes = None
        err = f"fetch: {type(e).__name__}: {e}"
    if not png_bytes:
        if debug:
            return Response(content=err or "no_png", media_type="text/plain")
        return Response(content=b"\x00" * (64 * 64 * 4), media_type="application/octet-stream")
    try:
        import io as _io
        from PIL import Image as _Img
        im = _Img.open(_io.BytesIO(png_bytes)).convert("RGBA")
        im = im.resize((64, 64))
        if debug:
            return Response(content=f"ok ah_bytes={len(png_bytes)}", media_type="text/plain")
        return Response(content=im.tobytes(), media_type="application/octet-stream")
    except Exception as e:
        if debug:
            return Response(content=f"pil: {type(e).__name__}: {e}", media_type="text/plain")
        return Response(content=b"\x00" * (64 * 64 * 4), media_type="application/octet-stream")

GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "1550988093681704991")

@app.get("/api/username")
async def username(did: str = ""):
    """Nome exibido no bem-vindo: nick/displayName no servidor (igual
    ORI, ex 'Samulindo'); fallback username Discord; fallback did."""
    did = "".join(ch for ch in did if ch.isdigit())[:20]
    if not did or not BOT_TOKEN:
        return Response(content=did.encode(), media_type="text/plain")
    name = ""
    try:
        lic = kv.get_lic(did) or {}
        name = lic.get("nome") or ""
    except Exception:
        name = ""
    if not name and GUILD_ID:
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{did}",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8) as x:
                m = json.loads(x.read().decode())
            name = m.get("nick") or (m.get("user") or {}).get("global_name")                    or (m.get("user") or {}).get("username") or ""
        except Exception:
            name = ""
    if not name:
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/users/{did}",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8) as x:
                u = json.loads(x.read().decode())
            name = u.get("username") or u.get("global_name") or did
        except Exception:
            name = did
    return Response(content=name.encode(), media_type="text/plain")

@app.get("/api/whoami")
async def whoami(did: str = ""):
    """Debug: username e global_name da conta (texto: username|global_name)."""
    did = "".join(ch for ch in did if ch.isdigit())[:20]
    if not did or not BOT_TOKEN:
        return Response(content="||", media_type="text/plain")
    try:
        req = urllib.request.Request(
            f"https://discord.com/api/v10/users/{did}",
            headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as x:
            u = json.loads(x.read().decode())
        return Response(content=f'{u.get("username","")}|{u.get("global_name","")}'.encode(),
                        media_type="text/plain")
    except Exception as e:
        return Response(content=f"ERR|{e}".encode()[:80], media_type="text/plain")

@app.get("/api/guilds")
async def guilds():
    """Debug: servidores onde o bot está (ids + nomes)."""
    if not BOT_TOKEN:
        return J({"guilds": []})
    try:
        req = urllib.request.Request(
            "https://discord.com/api/v10/users/@me/guilds?with_counts=false",
            headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as x:
            gs = json.loads(x.read().decode())
        return J({"guilds": [{"id": g.get("id"), "name": g.get("name")} for g in gs]})
    except Exception as e:
        return J({"erro": repr(e)[:200]})

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
    key_match = None
    key_shape = None
    if BOT_TOKEN and APP_ID_ENV:
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/applications/{APP_ID_ENV}/rpc",
                headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=10) as x:
                real = json.loads(x.read().decode()).get("verify_key", "")
            key_match = ("".join(PUBLIC_KEY.split()).lower() == real.lower()) if PUBLIC_KEY else None
            if PUBLIC_KEY:
                pk = "".join(PUBLIC_KEY.split())
                key_shape = {"len": len(pk), "hex_valido": _hex_ok(pk),
                             "primeiros8": pk[:8], "ultimos8": pk[-8:]}
        except Exception as e:
            key_match = "erro: %r" % e
    return J({**{k: v for k, v in {
        "public_key": bool(PUBLIC_KEY), "bot_token": bool(BOT_TOKEN),
        "application_id_set": bool(APP_ID_ENV),
        "application_id": APP_ID_ENV or None, "kv": bool(os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")),
        "reg_status": reg_status,
        "public_key_bate_com_app": key_match,
        "public_key_shape": key_shape,
        "ultima_falha_assinatura": _last_sig_err}.items()},
        "commands": _list_commands()})

def _hex_ok(s):
    try:
        b = bytes.fromhex("".join(s.split()))
        return len(b) == 32
    except Exception:
        return False

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
