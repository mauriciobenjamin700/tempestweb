# `tempestweb.server`

O host do Modo B: `create_app` monta o app FastAPI com as rotas WebSocket e SSE, `SecurityConfig` liga autenticação, origem e limites de carga, e o `RedisSessionRouter` dispensa sticky session no SSE. É o que você importa no `server.py` de um deploy.

Guia com exemplos: [Deploy em produção](../advanced/deploy.md) · [Segurança (Modo B)](../advanced/security.md).

::: tempestweb.server
