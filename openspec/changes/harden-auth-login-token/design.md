# Design

## Contexto técnico relevante

- `auth/src/main/java/com/bcp/workshop/auth/AuthResource.java` arma la
  respuesta de `POST /auth/login` y delega la creación del token a
  `LegacyTokenUtil.create(username, role)`.
- `LegacyTokenUtil` construye `username|role|expiry|secret`, con
  `expiry = now + 3600s` y `secret = "WORKSHOP_SECRET_2026"` fijado en el
  código fuente, y lo codifica en Base64 (sin firma verificable). La
  respuesta añade `expiresIn = 3600` como constante independiente del
  `expiry` real calculado — hoy coinciden por casualidad, pero nada los
  mantiene sincronizados si uno de los dos cambia.
- `LoginRequest.java` **ya** declara un campo `client`, pero
  `AuthResource.login` nunca lo lee, valida ni usa: hoy se acepta (o se
  omite) sin ningún efecto observable.
- `web/src/app/login/login.component.ts` ya envía `client:
  'angular-workshop'` en cada login y trata el `token` como una cadena
  opaca: lo guarda en `localStorage` y lo reenvía como
  `Authorization: Bearer <token>` a `api/`. No decodifica ni depende del
  contenido interno del token.
- `api/app/security.py` (documentado en `docs/ENDPOINTS.md`) exige de forma
  independiente un JWT RS256 con `iss=BCP`, `aud=dev` y claims `exp`, `iss`,
  `aud`, `username`, `role`. El token Base64 que emite `auth/` hoy **ya** es
  rechazado por `api/`: ambos componentes no interoperan en el estado
  actual. Este cambio no introduce ni resuelve esa falta de interoperación;
  solo mejora la emisión del lado de `auth/`.
- El propio cuerpo del issue #37 describe la implementación objetivo como
  "firma HMAC" que "lee `AUTH_TOKEN_SECRET`" — se toma como la convención de
  nombre de variable de configuración a seguir, consistente con el patrón ya
  usado en `LegacyDatabase` (`System.getenv().getOrDefault("AUTH_DB_URL",
  ...)`) y con los perfiles de Quarkus ya presentes en
  `application.properties` (`%prod.quarkus.http.host=...`).
- `auth/pom.xml` no declara hoy ninguna dependencia de firma/JWT.
- `LegacyDatabase.findByCredentials` arma SQL por concatenación de strings
  (riesgo de inyección preexistente, no relacionado con HU-01).

## Goals / Non-Goals

**Goals:**
- Diseñar cómo `auth/` firma criptográficamente el token de `POST
  /auth/login` y cómo construye los claims `sub`, `client`, `iat`, `exp`.
- Diseñar cómo se deriva `expiresIn` de forma coherente con `exp`/`iat`.
- Diseñar el manejo del secreto de firma (nombre de variable, alcance por
  entorno) sin fijarlo en el código fuente fuera del laboratorio.
- Diseñar la secuencia incremental de cambios y las pruebas de
  caracterización previas, dentro de `auth/` únicamente.

**Non-Goals:**
- No se diseña la verificación del token del lado de `api/`, ni se intenta
  hacer que `auth/` y `api/` interoperen en este cambio (ver riesgo de
  incoherencia de claims ya registrado en `proposal.md`).
- No se corrige la concatenación SQL de `LegacyDatabase.findByCredentials`;
  es un riesgo preexistente no mencionado por el issue y se deja fuera para
  no ampliar el alcance aprobado.
- No se rediseña `LegacyDatabase`, `UserRecord`, el esquema de la base
  SQLite, ni ningún endpoint de `web/` o `api/`.
- No se decide ni se diseña aquí un futuro cambio de alineación de claims
  con `api/`; queda como pregunta abierta para una propuesta separada.

## Contratos protegidos

- Ruta y método: `POST /auth/login` sin cambios.
- Forma de la solicitud: cuerpo JSON `{username, password, client}` (el
  campo `client` ya existe en `LoginRequest`; pasa de ignorado a
  obligatorio y validado — ver "Riesgos").
- Forma de la respuesta exitosa (`200`): `{token, expiresIn, user:
  {username, displayName, role}, debug}` — se preserva también el campo
  `debug` actual (`"authenticated-with-legacy-flow"`); esta propuesta no
  pide quitarlo y no se retira de forma incidental.
- Respuestas de error y su forma: `400 {message}` (falta `username` o
  `password`), `401 {message}` (credenciales inválidas), `500 {message,
  exception}` (error no esperado) — códigos y forma del cuerpo sin cambios.
- Contrato de `LegacyDatabase.findByCredentials` y de `UserRecord` (id,
  username, displayName, role): sin cambios.

## Componentes afectados

Todos dentro de `auth/`:

- `AuthResource.java`: pasa a validar `client`, a pedir la construcción del
  token firmado con los claims mínimos, y a calcular `expiresIn` a partir
  de los mismos claims usados para firmar (no de una constante aparte).
- `LegacyTokenUtil.java`: deja de producir Base64 plano; pasa a construir
  un token firmado (ver Decisiones) con `sub`, `client`, `iat`, `exp`.
- `application.properties`: agrega el secreto de firma
  (`AUTH_TOKEN_SECRET`) con un valor por defecto acotado a perfiles de
  laboratorio/test, y un parámetro de vida del token, usando el mismo
  patrón de perfiles ya presente en el archivo.
- `LoginRequest.java`: sin cambios de forma (el campo `client` ya existe);
  solo cambia si se agrega una validación explícita o se formaliza como
  obligatorio.
- `AuthResourceTest.java`: gana pruebas de caracterización y pruebas nuevas
  (ver más abajo).
- **No afectados:** `LegacyDatabase.java`, `UserRecord.java`, `auth/pom.xml`
  (ver Decisiones: no se agrega dependencia nueva), `auth/Dockerfile`.

## Decisiones técnicas y alternativas consideradas

### 1. Firma: HMAC con utilidades del JDK, sin librería JWT nueva

**Decisión:** firmar el token con HMAC-SHA256 usando `javax.crypto.Mac` (ya
incluido en el JDK 21 que usa `auth/`), en vez de incorporar una librería
JWT (por ejemplo `quarkus-smallrye-jwt-build` o `io.jsonwebtoken`).

**Alternativas consideradas:**
- *Adoptar una librería JWT estándar* (`quarkus-smallrye-jwt-build` u otra):
  pro, menos código de firma escrito a mano y manejo de claims más
  estandarizado; contra, agrega una dependencia nueva que requiere revisión
  SCA (igual que `PyJWT[crypto]` en `H-API-01` de `api/`), aumenta la
  superficie para un servicio de laboratorio, y no resuelve por sí sola la
  incoherencia de claims con `api/` (que de todas formas queda pendiente).
- *HMAC con `javax.crypto.Mac` (elegida):* pro, cero dependencias nuevas,
  superficie pequeña y auditable, ya es lo que el propio issue describe
  como implementación objetivo ("usa firma HMAC"); contra, código de firma
  escrito a mano requiere sus propias pruebas dedicadas (ver
  caracterización) y no ofrece de fábrica todo lo que una librería
  madura ofrece (rotación de claves, múltiples algoritmos, etc. — no
  requeridos por el issue).
- Se mantiene una serialización compacta con forma de JWT
  (`header.payload.firma`, Base64URL) aunque la firma sea manual, para que
  una futura migración a una librería estándar (si se aprueba alinear con
  `api/`) sea un cambio de implementación interno, no de contrato
  observable.

### 2. Secreto de firma: variable de entorno `AUTH_TOKEN_SECRET` con default solo en perfiles de laboratorio/test

**Decisión:** leer el secreto desde `AUTH_TOKEN_SECRET` (nombre tomado del
propio issue), con un valor por defecto documentado como exclusivo de
laboratorio disponible solo bajo los perfiles `%dev`/`%test` de Quarkus; el
perfil `%prod` no declara default y debe fallar rápido si la variable no
está configurada, en vez de arrancar con un secreto conocido.

**Alternativas consideradas:**
- *Mantener un secreto fijo en el código para todos los entornos (actual):*
  descartada; es exactamente el hallazgo que reporta el issue.
- *Exigir la variable en todos los entornos, incluido local/test, sin
  default:* descartada por fricción para desarrollo y pruebas locales sin
  aportar seguridad real en laboratorio.
- *Default acotado por perfil (elegida):* mantiene la experiencia local
  simple y dificulta que el valor de laboratorio llegue, sin advertencia,
  a un entorno no controlado.

### 3. `expiresIn` derivado de los mismos claims, no de una constante aparte

**Decisión:** calcular `expiresIn` como `exp - iat` a partir de los claims
ya embebidos en el token que se está emitiendo, en el mismo punto de
construcción de la respuesta, en vez de una constante (`3600`) separada.
Esto elimina el desacople por construcción; la "tolerancia documentada"
que pide la spec se reserva para las aserciones de prueba (p. ej. al
comparar contra `exp - now()` medido en otro instante), no para el cálculo
de producción.

**Alternativas consideradas:**
- *Mantener una constante de configuración separada para `expiresIn` y
  otra para la vida del token:* descartada; es la causa raíz del problema
  de coherencia que señala el issue.
- *Derivar `expiresIn` de los claims (elegida):* una sola fuente de verdad
  (los claims firmados) para la vida del token y para el valor informado al
  cliente.

## Estrategia incremental

Cada paso se caracteriza y se prueba antes del siguiente, como cambios
revisables independientes (`AGENTS.md`, contrato `auth`, punto 6):

1. **Caracterización del comportamiento actual** (sin tocar código de
   producción): fijar con pruebas el formato Base64 vigente, el valor
   constante de `expiresIn`, y que `client` se acepte sin validar hoy.
2. **Validación de `client`** en `AuthResource`: rechazar con `400` una
   solicitud sin `client` válido. Cambio aislado, con sus propias pruebas,
   sin tocar aún la construcción del token.
3. **Externalización del secreto** (`AUTH_TOKEN_SECRET` por perfil) sin
   cambiar todavía el formato del token (sigue Base64 en este paso
   intermedio), para separar el riesgo de manejo de configuración del
   riesgo de cambiar el formato del token.
4. **Reemplazo del token** por la versión firmada con claims mínimos
   (`sub`, `client`, `iat`, `exp`) y `expiresIn` derivado de esos claims:
   el cambio de mayor impacto, al final, una vez validados los pasos
   previos.
5. **Pruebas de seguridad y de ausencia de registros sensibles**: token
   alterado no verifica, ni el token ni el secreto aparecen en logs,
   arranque sin `AUTH_TOKEN_SECRET` fuera de laboratorio falla de forma
   explícita.

## Pruebas de caracterización necesarias antes de modificar comportamiento crítico

Antes de tocar `LegacyTokenUtil` o la validación de `client` en
`AuthResource`, fijar con pruebas el comportamiento actual:

- Login válido hoy devuelve `200` con un `token` Base64 decodificable a
  `username|role|expiry|secret` y `expiresIn` siempre `3600`.
- Login válido hoy **no** exige `client`: una solicitud sin ese campo
  también devuelve `200` (esto es lo que el paso 2 de la estrategia
  incremental cambia deliberadamente).
- `username` o `password` ausentes devuelven `400` con el mensaje actual.
- Credenciales que no matchean ningún registro devuelven `401` con el
  mensaje actual (incluye el username recibido).
- La forma completa de la respuesta exitosa actual, incluido el campo
  `debug`, para poder comparar antes/después.

## Riesgos / Trade-offs

- [Riesgo] Exigir `client` rompe cualquier llamador que hoy lo omita →
  Mitigación: `web/` ya lo envía siempre; el cambio es **BREAKING** y ya
  está declarado como tal en `proposal.md`; se agrega caracterización del
  comportamiento actual antes de activar la validación.
- [Riesgo] Firma HMAC escrita a mano tiene más riesgo de error de
  implementación que una librería madura → Mitigación: función de firma
  aislada y con pruebas dedicadas (claims, firma, verificación, alteración
  de bytes); comparación de firmas con `MessageDigest.isEqual` si se agrega
  verificación en algún punto.
- [Riesgo] Un default de laboratorio mal configurado podría llegar a un
  entorno no controlado → Mitigación: default limitado a perfiles
  `%dev`/`%test`; `%prod` sin default, con fallo explícito al arrancar si
  falta `AUTH_TOKEN_SECRET`.
- [Riesgo] El conjunto de claims (`sub`, `client`, `iat`, `exp`) sigue sin
  coincidir con lo que `api/` exige (`iss`, `aud`, `username`, `role`,
  RS256) → Mitigación: fuera de alcance explícito de este cambio (ver
  Non-Goals); queda como pregunta abierta para una propuesta futura y
  coordinada entre componentes, no se decide aquí.
- [Riesgo] La concatenación SQL en `LegacyDatabase.findByCredentials` es un
  riesgo preexistente no cubierto por este cambio → Mitigación: se deja
  fuera de alcance explícitamente (Non-Goals); se documenta aquí como
  candidato a un hallazgo propio futuro.
- [Riesgo] Pruebas que comparan tiempos (`iat`/`exp`/`expiresIn`) pueden
  volverse inestables por el reloj → Mitigación: comparar con una
  tolerancia pequeña y documentada en las propias pruebas, sin dormir
  (`sleep`) hilos de prueba.

## Rollback

- El cambio completo vive dentro de `auth/`, un servicio Quarkus
  autocontenido sin estado persistente relacionado con el token (no se
  guarda el token ni el secreto en la base SQLite; `LegacyDatabase` no se
  modifica). Revertir no requiere migración ni limpieza de datos.
- Cada paso de la estrategia incremental es un commit/cambio revisable por
  separado: revertir el paso 4 (reemplazo del token firmado) restaura la
  emisión Base64 sin afectar los pasos 1–3 ni requerir cambios en `api/` o
  `web/`, que ya no dependían del contenido interno del token anterior.
- Rollback operativo: redesplegar la imagen/artefacto de `auth/` construido
  desde el commit previo a la firma; no hay cambios de esquema ni de datos
  que revertir por separado.
- Si el default de `AUTH_TOKEN_SECRET` por perfil causa fricción operativa
  inesperada, revertir únicamente el cambio de `application.properties`
  (paso 3) es independiente de revertir el formato del token (paso 4).

## Open Questions

- ¿Se aprueba, en una propuesta separada, alinear el conjunto de claims de
  `auth/` con lo que `api/` exige hoy (RS256, `iss`, `aud`, `username`,
  `role`), o se coordina un cambio en `api/` en sentido contrario? No
  cambia el enfoque ni las specs de este cambio; queda explícitamente
  diferido.
- Valor exacto de la tolerancia usada en las pruebas al comparar
  `expiresIn` con `exp - iat`/`exp - now` (por ejemplo, 1 segundo): se
  decide al escribir las pruebas, sin impacto en el enfoque de este diseño.
