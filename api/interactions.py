# api/interactions.py - Discord Interactions (slash commands) via webhook.
# Responde a /add /remove /list /status direto da Vercel — sem gateway,
# sem PC ligado. Comandos só para administradores do servidor.
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import kv

PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")      # hex
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

def _verify_sig(request, body):
    """Verifica assinatura Ed25519 do Discord (X-Signature-Ed25519 / Timestamp).
    Usa pynacl se disponivel; sem PUBLIC_KEY configurada (dev), aceita."""
    if not PUBLIC_KEY:
        return True
    def _hdr(name):
        h = getattr(request, "headers", None) or {}
        try:
            return h.get(name) or h.get(name.upper()) or h.get(name.title()) or ""
        except Exception:
            return ""
    sig = _hdr("x-signature-ed25519")
    ts = _hdr("x-signature-timestamp")
    if not sig or not ts:
        return False
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        vk = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        vk.verify(ts.encode() + body, bytes.fromhex(sig))
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False

def _is_admin(member):
    perms = int(member.get("permissions", "0") or 0)
    return bool(perms & 0x8) or bool(perms & 0x20)  # ADMINISTRATOR ou MANAGE_GUILD

def _reply(content, eph=False):
    return {"type": 4, "data": {"content": content,
            "flags": 64 if eph else 0}}

def _register_commands():
    """Registra os slash commands (chamado 1x manual ou on-cold-start)."""
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
    ]
    url = ("https://discord.com/api/v10/applications/"
           + os.environ.get("DISCORD_APPLICATION_ID", "") + "/commands")
    req = urllib.request.Request(url, method="PUT",
        data=json.dumps(cmds).encode(),
        headers={"Authorization": f"Bot {BOT_TOKEN}",
                 "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass

def handler(request):
    body = getattr(request, "body", None) or b""
    if isinstance(body, str):
        body = body.encode()
    if not _verify_sig(request, body):
        return ("{\"error\":\"bad signature\"}", 401,
                {"Content-Type": "application/json"})
    data = json.loads(body.decode("utf-8", "replace") or "{}")
    # ping do Discord ao registrar a URL
    if data.get("type") == 1:
        _register_commands()
        return {"type": 1}
    if data.get("type") != 2:   # só APPLICATION_COMMAND
        return {"type": 5}      # THINKING fallback

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
