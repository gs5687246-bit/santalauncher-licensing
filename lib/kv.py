# lib/kv.py - Storage de licencas via Vercel KV (Upstash REST) — sem SDK.
# Env vars: KV_REST_API_URL, KV_REST_API_TOKEN (criadas ao adicionar Vercel KV).
import json, os, time, urllib.request, urllib.error

_URL = (os.environ.get("KV_REST_API_URL")
        or os.environ.get("UPSTASH_REDIS_REST_URL") or "").rstrip("/")
_TOKEN = (os.environ.get("KV_REST_API_TOKEN")
          or os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "")
_KEY = "licencas"   # hash: campo = discord_id, valor = json da licenca

def _rest(*parts):
    """GET/POST Upstash REST: /get/key, /set/key/value, /hset..."""
    url = _URL + "/" + "/".join(parts)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise RuntimeError(f"KV falhou: {e!r}")

def _local_fallback():
    """Sem KV configurado: arquivo local (dev na maquina)."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "licencas_dev.json")
    return p

def _load_all():
    if not _URL:
        p = _local_fallback()
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return {}
    r = _rest("get", _KEY)
    raw = r.get("result")
    if not raw:
        return {}
    return json.loads(raw)

def _save_all(d):
    if not _URL:
        p = _local_fallback()
        json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        return
    _rest("set", _KEY, json.dumps(d, ensure_ascii=False))

def lic_ativa(did):
    d = _load_all()
    lic = d.get(str(did))
    if not lic or not lic.get("ativa", True):
        return None
    exp = lic.get("expira", 0)
    if exp and time.time() > exp:
        return None
    return lic

def get_lic(did):
    return _load_all().get(str(did))

def set_lic(did, lic):
    d = _load_all()
    d[str(did)] = lic
    _save_all(d)

def del_lic(did):
    d = _load_all()
    if str(did) in d:
        del d[str(did)]
        _save_all(d)
        return True
    return False

def all_lic():
    return _load_all()
