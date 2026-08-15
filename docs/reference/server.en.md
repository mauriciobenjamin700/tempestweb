# `tempestweb.server`

The Mode B host: `create_app` builds the FastAPI app with its WebSocket and SSE routes, `SecurityConfig` turns on authentication, origin checks and load limits, and `RedisSessionRouter` removes the need for sticky sessions on SSE. This is what a deployment's `server.py` imports.

Guide with examples: [Deploy to production](../advanced/deploy.md) · [Security (Mode B)](../advanced/security.md).

::: tempestweb.server
