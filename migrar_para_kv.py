# migrar_para_kv.py - sobe o licencas.json local para o Vercel KV
# Uso: set KV_REST_API_URL=... && set KV_REST_API_TOKEN=... && python migrar_para_kv.py
import json, os, urllib.request, sys

URL = os.environ.get("KV_REST_API_URL", "").rstrip("/")
TOK = os.environ.get("KV_REST_API_TOKEN", "")
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "licencas.json")

if not URL:
    sys.exit("Defina KV_REST_API_URL e KV_REST_API_TOKEN (painel Vercel -> Storage -> KV -> .env.local)")

data = json.load(open(os.path.abspath(LOCAL), encoding="utf-8"))
body = json.dumps(data, ensure_ascii=False)
req = urllib.request.Request(URL + "/set/licencas", data=body.encode(),
    headers={"Authorization": f"Bearer {TOK}",
             "Content-Type": "text/plain"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as r:
    print("resposta:", r.read().decode())
print(f"{len(data)} licencas enviadas ao KV.")
