# SantaLauncher Licensing

Sistema de gerenciamento de licenciamento do SantaLauncher — API compatível com o protocolo **ZeroAuth** (`api.zeroauth.cc`) + bot de licenças do Discord, **100% serverless na Vercel**.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fgs5687246-bit%2Fsantalauncher-licensing&project-name=santalauncher-licensing&repository-name=santalauncher-licensing)

## Endpoints (protocolo auth-api do launcher)

| Endpoint | Descrição |
|---|---|
| `GET /api/auth-api/health?appDatabase=…` | Health check |
| `POST /api/auth-api/check-app-status` | Status do app (`appid` + `appDatabase`) |
| `POST /api/auth-api/login` | Login por Discord ID (`key`/`usernameOrKey` + `hwid`…) |
| `POST /api/auth-api/log-login` | Log de login (fire-and-forget) |
| `POST /api/auth-api/get-expiration` | Expiração da licença |

Mensagens de erro idênticas ao original: `Key inválida!`, `AppID inválido!`, `HWID mismatch!`, `key, hwid, appid e appDatabase são obrigatórios`.

## Comandos do bot (Discord → Interactions webhook)

| Comando | Ação |
|---|---|
| `/add discord_id:<id> dias:<n>` | Adiciona licença (sem dias = vitalícia) |
| `/remove discord_id:<id>` | Remove |
| `/list` | Lista todas |
| `/status discord_id:<id>` | Status de uma licença |
| `/pingbot` | Teste |

Somente administradores/gerenciadores do servidor.

## Deploy (5 passos)

1. **Vercel**: clique no botão **Deploy** acima (ou `vercel` CLI nesta pasta)
2. **KV**: painel do projeto → Storage → Create → **KV** (grátis; cria `KV_REST_API_URL`/`KV_REST_API_TOKEN`)
3. **Env vars** (Settings → Environment Variables):
   - `DISCORD_APPLICATION_ID` — Application ID do bot (Discord Developer Portal)
   - `DISCORD_PUBLIC_KEY` — Public Key do app
   - `DISCORD_BOT_TOKEN` — token do bot
4. **Discord Developer Portal** → General Information → Interactions Endpoint URL:
   `https://SEU-PROJETO.vercel.app/api/interactions`
   (o PING do Discord registra os slash commands automaticamente)
5. **Migrar licenças locais**: `set KV_REST_API_URL=… && set KV_REST_API_TOKEN=… && python migrar_para_kv.py`

## Apontar o launcher

```c
#define ZEROAUTH_HOST "SEU-PROJETO.vercel.app"
#define ZEROAUTH_PORT 443
#define ZEROAUTH_HTTPS 1
```

## Estrutura
```
api/
  health.py, check-app-status.py, login.py, log-login.py, get-expiration.py
  interactions.py   ← slash commands do Discord (Ed25519 verified)
lib/
  kv.py             ← Vercel KV via REST (fallback local p/ dev)
  zeroauth.py       ← contrato exato das respostas (capturado do exe oficial)
migrar_para_kv.py   ← sobe licencas.json local para o KV
vercel.json         ← rotas /api/auth-api/* → functions
```

## Segurança
- Interactions verificadas por assinatura **Ed25519** (pynacl)
- Primeiro login vincula o `hwid`; login de outra máquina → 403
- Comandos restritos a admins do servidor
