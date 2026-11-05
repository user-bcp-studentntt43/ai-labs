# Proposal

## Why

GitHub Issue [#37](https://github.com/user-bcp-studentntt43/ai-labs/issues/37)
(`HU-01 - Token firmado con expiracion y claims minimos`) registra que
`POST /auth/login` emite un token sin firma criptográfica verificable: `auth/src/main/java/com/bcp/workshop/auth/LegacyTokenUtil.java`
concatena `username|role|expiry|secret` y lo codifica en Base64, con un
secreto (`WORKSHOP_SECRET_2026`) embebido en el código fuente. Cualquiera que
conozca el formato puede fabricar un token válido para cualquier usuario y
rol sin conocer credenciales, y el secreto no puede rotarse sin publicar
código nuevo. El issue fue evaluado como "usable con ajustes" y pide exigir
claims mínimos, firmar el token, y documentar o eliminar el secreto por
defecto.

## What Changes

- **BREAKING**: `POST /auth/login` deja de aceptar el token Base64 legado
  como formato de salida; el token emitido pasa a estar firmado
  criptográficamente y a incluir los claims `sub`, `client`, `iat` y `exp`.
- El claim `client` se obtiene y valida a partir de la solicitud de login
  (campo `client` del cuerpo), en vez de ser implícito o ausente.
- `expiresIn` en la respuesta debe ser coherente con `exp - iat` (o `exp -
  now`) dentro de una tolerancia documentada, en vez de ser una constante
  (`3600`) desconectada del valor real de expiración del token.
- El secreto de firma deja de estar fijado en el código fuente para cualquier
  entorno fuera del laboratorio, o queda documentado explícitamente como
  exclusivo de laboratorio si se conserva un valor por defecto.
- Se elimina cualquier registro (log) del token emitido o del secreto de
  firma.
- La decisión entre conservar HMAC (firmando el payload actual) o adoptar una
  librería JWT estándar queda como decisión técnica pendiente, a resolver en
  `design.md` de este mismo cambio; esta propuesta no la resuelve.

## Capabilities

### New Capabilities

- `auth-login-token`: emisión del token de sesión por `POST /auth/login`:
  firma criptográfica, claims mínimos (`sub`, `client`, `iat`, `exp`),
  coherencia de `expiresIn`, manejo del secreto de firma y ausencia de
  registros sensibles. No existe una capability previa bajo
  `openspec/specs/` que cubra la emisión de este token (`openspec/specs/`
  está vacío); esta es la primera.

### Modified Capabilities

- Ninguna. No hay specs existentes en `openspec/specs/` que esta propuesta
  modifique.

## Impact

- **Código afectado (solo `auth/`):** `auth/src/main/java/com/bcp/workshop/auth/AuthResource.java`
  (arma la respuesta de login) y
  `auth/src/main/java/com/bcp/workshop/auth/LegacyTokenUtil.java` (crea el
  token). Posiblemente `auth/src/main/java/com/bcp/workshop/auth/LoginRequest.java`
  si se formaliza el campo `client` recibido, y `auth/src/main/resources/application.properties`
  si el secreto o la tolerancia de expiración se externalizan a
  configuración.
- **Pruebas:** `auth/src/test/java/com/bcp/workshop/auth/AuthResourceTest.java`
  debe caracterizar el comportamiento Base64 actual antes de tocar la
  implementación, y ganar casos para claims, firma, `expiresIn` y manejo de
  configuración, conforme al contrato para agentes de `auth` en `AGENTS.md`
  (pruebas de caracterización antes de refactorizar, cobertura ≥85% del
  código modificado).
- **No afectado por esta propuesta:** `api/` y `web/` no se modifican. El
  endpoint `POST /auth/login` conserva su ruta, método y la forma general de
  su respuesta (`token`, `expiresIn`, `user`); solo cambia el contenido y la
  construcción del `token` y la base de cálculo de `expiresIn`.
- **Dependencias:** si la decisión técnica (en `design.md`) resulta en
  adoptar una librería JWT para `auth/` (hoy sin dependencias de firma, ver
  `auth/pom.xml`), se agrega una dependencia nueva sujeta a revisión SCA,
  igual que se hizo para `api/` en `H-API-01` (`PyJWT[crypto]`).
- **Riesgo de incoherencia con el contrato documentado:** `docs/ENDPOINTS.md`
  (baseline del Día 1) documenta que `api/` verifica tokens JWT RS256 con
  claims `exp`, `iss`, `aud`, `username` y `role` (`api/app/security.py:23-56`).
  El Issue #37 exige en cambio los claims `sub`, `client`, `iat` y `exp` para
  el token emitido por `auth/`. Estos dos conjuntos de claims no coinciden
  (`sub` frente a `username`, `client` sin equivalente documentado en `api/`,
  ausencia de `iss`/`aud`/`role` en el pedido del issue). Esta propuesta no
  resuelve esa incoherencia entre componentes: la especifica como riesgo
  abierto en la spec de la capability para que se decida explícitamente antes
  de implementar, en vez de asumir en silencio cuál contrato prevalece.
