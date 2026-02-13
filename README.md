# \# preject

# 

# \## Configuração de ambiente

# 

# A aplicação agora possui uma interface única para `app/main.py` via `settings` (adaptador em `app/config.py`).

# 

# \### Variáveis essenciais (produção)

# 

# > Em desenvolvimento todas possuem default seguro para subir localmente.

# 

# \- `ENVIRONMENT` (default: `development`) — `development`, `staging` ou `production`.

# \- `DATABASE\_URL` (default dev: `sqlite:///./dev.db`) — URL do banco principal.

# \- `REDIS\_URL` (default dev: `redis://localhost:6379/0`) — URL do Redis.

# \- `SECRET\_KEY` (default dev: `dev-secret-key-change-in-production`) — chave base de segurança da aplicação.

# \- `CRYPTO\_SECRET\_KEY` (default: valor de `SECRET\_KEY`) — chave usada pelo `CryptoManager`.

# \- `ADMIN\_API\_TOKEN` (default dev: `dev-admin-token-change-in-production`) — token para rotas administrativas.

# 

# \### Variáveis opcionais

# 

# \- `PORT` (default: `8000`) — porta HTTP da aplicação.

# \- `CORS\_ORIGINS` (default: `http://localhost:3000,http://127.0.0.1:3000`) — aceita JSON array (`\["http://..."]`) ou CSV.

# \- `DEBUG` (default automático: `true` em `development`, `false` nos demais ambientes).

# \- `DB\_POOL\_SIZE` (default: `20`)

# \- `DB\_MAX\_OVERFLOW` (default: `40`)

# \- `DB\_POOL\_RECYCLE` (default: `3600`)

# \- `DB\_POOL\_PRE\_PING` (default: `true`)

# \- `DB\_ECHO` (default: `false`)

# \- `REDIS\_SOCKET\_TIMEOUT` (default: `5`)

# \- `REDIS\_CONNECT\_TIMEOUT` (default: `5`)

# \- `REDIS\_RETRY\_ON\_TIMEOUT` (default: `true`)

# \- `REDIS\_HEALTH\_CHECK\_INTERVAL` (default: `30`)

# \- `JWT\_ALGORITHM` (default: `HS256`)

# \- `ACCESS\_TOKEN\_EXPIRE\_MINUTES` (default: `30`)

# \- `REFRESH\_TOKEN\_EXPIRE\_DAYS` (default: `7`)

# \- `HMAC\_KEY` (opcional)

# \- `ENCRYPTION\_KEY` (opcional)

# \- `ENABLE\_METRICS` (default: `true`)

# \- `ENABLE\_TRACING` (default: `true`)

# \- `OTLP\_ENDPOINT` (opcional)

# \- `PROMETHEUS\_PORT` (default: `9090`)

# \- `LOG\_LEVEL` (default: `INFO`)

# \- `STRUCTURED\_LOGGING` (default: `true`)

# \- `BOT\_REGISTRY\_TABLE` (default: `bots`)

# \- `MAX\_BOTS\_PER\_TENANT` (default: `100`)

# \- `BOT\_TOKEN\_ROTATION\_DAYS` (default: `90`)

# \- `DEFAULT\_FLOW` (default: `main\_flow`)

# \- `TENANT\_CONFIG\_CACHE\_TTL` (default: `300`)

# \- `FEATURE\_FLAGS` (default: `{}` JSON)

# \- `RATE\_LIMITS` (default: `{}` JSON)

