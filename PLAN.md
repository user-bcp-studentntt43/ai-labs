# Plan de corrección — API

## Alcance y selección

Se planifican todos los hallazgos `H-API-01` a `H-API-07` de
`HALLAZGOS.md`, en el orden solicitado. La persona usuaria aprobó en esta
sesión implementar los siete hallazgos en el orden del plan, sujeto a las
decisiones de contrato y dependencias externas indicadas en cada apartado.
H-API-01 a H-API-07 están Resueltos con pruebas.

`docs/ENDPOINTS.md` se creó posteriormente como contrato observado y acordado,
con ejemplos, campos y errores por endpoint. Las rutas, métodos y formas
actuales de respuesta se mantienen. Los cambios de autenticación y
autorización descritos abajo afectan
intencionalmente qué tokens y qué datos se aceptan, aunque conserven las rutas y
la estructura de las respuestas. Deben coordinarse antes de implementar.

### H-API-01 — Token Base64 con secreto embebido

- **Hallazgo y problema:** `H-API-01`, severidad alta. El token
  codificado en Base64 no verificaba una firma; antes del cambio, el secreto
  estaba declarado en `api/app/main.py:14` y el parseo/validación estaban en
  `api/app/main.py:17-26`.
- **Cambio propuesto:** reemplazar la aceptación del formato Base64 por
  verificación criptográfica de JWT, validando firma, algoritmo permitido,
  emisor, audiencia y expiración. Leer la configuración de verificación desde
  variables de entorno/configuración, nunca de un secreto añadido al código.
  Mantener el encabezado Bearer, las rutas y la representación de identidad
  usada por las rutas; el formato y la emisión del token deben coordinarse con
  el componente que lo emite antes de retirar compatibilidad. No aceptar en
  paralelo el token Base64 antiguo como alternativa, pues mantendría el riesgo.
- **Archivos a tocar:** `api/app/main.py`; módulo nuevo bajo `api/app/` para
  verificación de tokens si la separación de H-API-06 se implementa en la
  misma secuencia; `api/requirements.txt` solo si se aprueba una biblioteca
  JWT mantenida. La dependencia se justificaría para evitar implementar
  criptografía/protocolo manualmente y deberá pasar revisión SCA.
- **Caracterización antes de tocar esos archivos:** ampliar
  `api/tests/test_api.py` para fijar el formato de autorización actual y el
  `401` para token inválido; probar las rutas protegidas con una identidad de
  prueba aislada. Registrar que el token Base64 actual se acepta como
  comportamiento existente, sin preservar esa aceptación tras la corrección.
- **Caracterización previa (api, H-API-01):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "invalid_token or lists_seeded_tasks"` terminó con **2 passed** con la
  implementación Base64 original. Una primera invocación desde la raíz no
  encontró pytest y no ejecutó tests; el entorno se preparó después en
  `api/.venv/`.
- **Caracterización ampliada antes del cambio de producción (api, H-API-01):**
  se añadieron pruebas para JWT RS256 y antes de modificar `api/app/main.py` se
  ejecutaron los casos de autenticación: **11 failed**, como se esperaba con
  el código Base64 original (rechazaba JWT válido, aceptaba el formato antiguo
  y filtraba detalles internos).
- **Cambio/diff local (api, H-API-01):** `api/app/main.py` valida tokens JWT
  RS256, exige `exp`, `iss`, `aud`, `username` y `role`, comprueba issuer
  `BCP`/audience `dev` y lee la clave RSA pública de `devpub`. Tokens inválidos
  reciben `401` genérico; falta o invalidez de la clave genera error de
  configuración del servidor. La función de autenticación se llama
  `authenticated_identity`. `api/requirements.txt` añade
  `PyJWT[crypto]==2.15.1`; `api/tests/test_api.py` genera claves RSA ficticias
  locales y cubre firma/claims inválidos, formato legado y configuración.
- **Pruebas posteriores (api, H-API-01):** con cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py
  --cov=app.main --cov-branch --cov-report=term-missing --cov-report=html`
  terminó con **18 passed**. Cobertura global de `app/main.py`: **94%**
  (ramas incluidas; reporte `api/htmlcov/`). Para el bloque modificado del
  autenticador (sentencias ejecutables entre líneas 15-57): **27/27 = 100%**;
  es el cálculo específico del diff, separado de la cobertura global.
- **SCA (api, H-API-01/H-API-05):** `pip-audit --no-deps -r
  .h-api-01-audit.txt`, sobre PyJWT 2.15.1 y sus dependencias RSA
  (`cryptography 50.0.2`, `cffi 2.1.1`, `pycparser 3.12`), terminó con
  **No known vulnerabilities found**; el archivo temporal se eliminó. La
  auditoría completa `pip-audit -r requirements.txt` terminó con código 1 y
  reportó **32 findings** en `urllib3 2.5.0`, `python-multipart 0.0.21` y
  `starlette 0.50.0`; no se ocultaron ni corrigieron aquí, y quedan pendientes
  para H-API-05.
- **Estado de H-API-01:** Resuelto; caracterización, corrección, pruebas
  posteriores, cobertura del diff y SCA de la nueva dependencia constan arriba.
- **Aprobación y contrato coordinado:** aprobación explícita recibida para
  H-API-01 a H-API-07. La persona usuaria confirmó algoritmo RS256, issuer
  `BCP`, audience `dev`, variable de clave pública `devpub` y coordinación con
  el emisor. No se incluyeron claves reales.
- **Dependencia propuesta:** `PyJWT[crypto]==2.15.1`, para validación estándar
  de JWT y soporte RSA sin implementar criptografía manualmente. La consulta
  pública de PyPI mostró 2.15.1 como release del 28-sep-2026; la búsqueda de
  advisories no reportó vulnerabilidades conocidas abiertas para esa versión.
  El resultado del escaneo SCA está registrado arriba.

### H-API-02 — El cliente controla `owner`

- **Hallazgo y problema:** `H-API-02`, inicialmente Pendiente, severidad alta.
  Antes del cambio, el filtro de `/api/tasks` y `/api/summary`, y el
  propietario de una tarea creada, podían venir del cliente
  (`api/app/main.py:96-99,106-112,119-121` en la versión caracterizada);
  esto permitía pedir o atribuir datos a otra identidad.
- **Cambio propuesto:** derivar el owner exclusivamente de la identidad ya
  verificada. Mantener rutas, parámetros/campos aceptados y formas de respuesta
  para compatibilidad de transporte; si el cliente envía un owner distinto a
  la identidad, rechazar con `403` genérico en list, summary y create. Si el
  campo no se envía, usar la identidad autenticada. Esta es una modificación
  intencional de la semántica de autorización requerida por
  `docs/GOOD_PRACTICES.md`, no una conservación de acceso entre usuarios.
- **Archivos a tocar:** `api/app/main.py`; los módulos de rutas/servicio/
  repositorio de H-API-06 si se implementa junto con esa separación;
  `api/tests/test_api.py`.
- **Caracterización antes de tocar esos archivos:** con la base temporal
  sembrada por `create_app`, fijar las respuestas actuales para identidad
  `student`, identidad `trainer`, `owner` coincidente y `owner` distinto, tanto
  en listado como en resumen; fijar que el POST permite el owner del cuerpo.
  Usar tokens de prueba locales.
- **Decisión acordada:** la persona usuaria eligió rechazar con `403` las
  solicitudes cuyo `owner` explícito contradiga la identidad; no se ignora ni
  se cambia silenciosamente el owner solicitado.
- **Caracterización previa (api, H-API-02):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "characterizes_"` terminó con **3 passed**: el código anterior permitía
  listar y resumir tareas de `trainer` con token de `student`, y crear una
  tarea para `trainer`.
- **Prueba de corrección antes del cambio de producción (api, H-API-02):**
  al cambiar esas expectativas a 403 genérico y ejecutar
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "different_owner"`, terminaron **3 failed** con los resultados previos
  observados `200`, `200` y `201`.
- **Cambio/diff local (api, H-API-02):** `api/app/main.py:21-25` agrega
  `authenticated_owner`, reutilizado por listado, resumen y creación
  (`api/app/main.py:102-106,113-120,127-129`). Owner ausente o vacío en filtros
  conserva el fallback a la identidad; owner explícito distinto en filtros o
  payload produce `403 {"detail":"Forbidden"}`. No se cambian rutas ni forma de
  respuesta para solicitudes permitidas.
- **Pruebas posteriores (api, H-API-02):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "different_owner or authenticated_owner"` terminó **6 passed**. La suite
  completa con cobertura terminó **24 passed**; cobertura global de
  `app/main.py` **94%**. Sentencias ejecutables cambiadas (helper y tres
  invocaciones): **8/8 cubiertas**; ramas del guard en `api/app/main.py:23`:
  **2/2 cubiertas**. Reporte HTML en `api/htmlcov/`.
- **Estado de H-API-02:** Resuelto con la política 403 aprobada; la
  caracterización previa, red test, corrección, suite completa y cobertura
  están registradas. No se avanzó a H-API-03.
- **Cobertura del código modificado (api, H-API-02):** cálculo con el JSON
  generado por Coverage después de la suite completa: 8/8 sentencias
  ejecutables modificadas (helper y tres invocaciones) y 2/2 ramas del guard
  (`api/app/main.py:23`) cubiertas. Esto mide específicamente el código del
  hallazgo, separado del 94% global de `app/main.py`.

### H-API-03 — Valores de cliente concatenados en SQL

- **Hallazgo y problema:** `H-API-03`, inicialmente Pendiente, severidad alta.
  El filtro de
  tareas concatena `requested_owner` y se ejecuta en
  `api/app/main.py:105-106`; el INSERT concatena campos del payload en
  `api/app/main.py:120-122`; el resumen concatena `requested_owner` en
  `api/app/main.py:128-129`. La consulta por `lastrowid` también construye su
  SQL concatenando el ID (`api/app/main.py:123`).
- **Cambio propuesto:** usar consultas SQLite con placeholders y argumentos
  separados para todos los valores variables, incluso el ID recuperado.
  Mantener columnas, orden, defaults, transacción, códigos y JSON observados.
  No interpolar valores externos ni generados en cadenas SQL.
- **Archivos a tocar:** `api/app/main.py`; el repositorio nuevo de tareas de
  H-API-06 si se hace la separación en conjunto; `api/tests/test_api.py`.
- **Caracterización antes de tocar esos archivos:** fijar resultados normales
  de listar, crear y resumir tareas; agregar pruebas de persistencia exacta de
  texto con apóstrofes en título/descripción y de filtro de owner con comilla,
  sin usar entradas de explotación ni depender de efectos secundarios.
- **Caracterización previa (api, H-API-03):** desde cwd `api/`, las pruebas
  normales existentes se ejecutaron con
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "lists_seeded_tasks or creates_task_and_summary"` y pasaron (**2 passed**).
  Antes del cambio de producción se ejecutó
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "username_containing_apostrophe or creates_task_with_apostrophes or
  binds_values_in_task_queries"`: **4 failed**. Las tres pruebas de ruta
  devolvieron `500` en vez de `200`, `200` y `201`; el primer intento del spy
  también falló porque capturó consultas estáticas de inicialización, así que
  ese resultado del spy no se considera evidencia. El spy se ajustó para
  registrar solo llamadas de ruta.
- **Cambio/diff local (api, H-API-03):** `api/app/main.py:105-106` enlaza el
  owner del listado; `:120-123` enlaza los campos del `INSERT` y `lastrowid`;
  `:129-131` enlaza el owner del resumen. No se interpolan valores externos ni
  el ID generado en estas consultas.
- **Pruebas posteriores (api, H-API-03):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "username_containing_apostrophe or creates_task_with_apostrophes or
  binds_values_in_task_queries"` terminó **4 passed**. El spy verifica el SQL
  con placeholders y las tuplas exactas de parámetros; las pruebas de ruta
  confirman que usernames y textos con apóstrofes se procesan sin error y se
  devuelven correctamente. La suite completa con cobertura,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py --cov=app.main
  --cov-branch --cov-report=term-missing --cov-report=html`, terminó
  **28 passed**, cobertura global de `app/main.py` **94%** y reporte en
  `api/htmlcov/`.
- **Cobertura del código modificado (api, H-API-03):** 6/6 sentencias
  ejecutables modificadas en las consultas dinámicas cubiertas; cálculo con
  el JSON de Coverage de la ejecución completa. Esto es cobertura específica
  de H-API-03, separada del porcentaje global.
- **Estado de H-API-03:** Resuelto; no se cambiaron rutas, respuestas ni
  defaults. No se avanzó a H-API-04.

### H-API-04 — Nombre y tamaño de archivos subidos sin controles

- **Hallazgo y problema:** `H-API-04`, inicialmente Pendiente, severidad media.
  Antes del cambio, el nombre original se combinaba con el directorio y el
  contenido completo se leía y escribía sin validación ni límite
  (`api/app/main.py:145-150` en la versión caracterizada). Podía producir
  escritura fuera del directorio previsto o consumo excesivo de recursos.
- **Cambio propuesto:** validar presencia y nombre, normalizar/aislar el
  nombre dentro del directorio permitido, restringir extensiones y limitar
  bytes mientras se lee por bloques. Mantener ruta, status y claves de
  respuesta; `fileName` debe representar el nombre seguro almacenado.
  Usar las constantes `ALLOWED_REQUIREMENT_EXTENSIONS = {".txt"}`,
  `MAX_REQUIREMENT_FILE_SIZE_BYTES = 1048576` y un tamaño de bloque con nombre.
  Responder `415` para extensiones no permitidas y `413` para archivos que
  excedan el máximo; responder `400` para un nombre de archivo inválido.
- **Archivos a tocar:** `api/app/main.py`; módulo de servicio de archivos nuevo
  solo si se aprueba la separación de H-API-06; `api/tests/test_api.py`.
- **Caracterización antes de tocar esos archivos:** fijar el caso actual de
  carga válida, status `201`, forma de la respuesta y contenido guardado en el
  directorio temporal; registrar el comportamiento actual para nombre vacío,
  ruta relativa y archivo grande en entorno temporal, sin escribir fuera del
  directorio de prueba.
- **Decisión acordada (api, H-API-04):** la persona usuaria confirmó la
  allowlist `.txt`, máximo de `1048576` bytes, status `415` para extensión no
  permitida y `413` para tamaño excedido. El status `400` para nombres
  inválidos queda como la propuesta técnica del plan.
- **Caracterización previa (api, H-API-04):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "uploads_requirement or sanitizes_requirement_filename or
  unsupported_extension or over_size_limit or at_size_limit or
  empty_requirement_filename"` terminó con **4 failed, 2 passed** antes del
  cambio de producción. El caso válido y el límite exacto pasaron; la ruta con
  separadores se guardó con el nombre original, la extensión no permitida y
  el archivo sobre el límite recibieron `201`, y el nombre multipart vacío
  produjo `422` (se preserva esa validación de FastAPI). Tras observar ese
  `422`, se cambió el test de nombre vacío para fijar el contrato observado y
  se añadió un caso de basename vacío; ese caso específico no se volvió a
  ejecutar contra la versión previa antes del cambio.
- **Cambio/diff local (api, H-API-04):** `api/app/main.py:19-21` define
  allowlist, límite y tamaño de bloque; `:31-63` normaliza/rechaza nombres y
  lee por bloques hasta el máximo; `:183-195` valida confinamiento dentro del
  directorio, guarda el nombre seguro y conserva las claves de respuesta.
  Archivo válido sigue respondiendo `201`; extensión no permitida responde
  `415`, exceso responde `413`, nombre inválido responde `400`. El campo
  multipart ausente conserva el `422` observado.
- **Pruebas posteriores (api, H-API-04):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k
  "uploads_requirement or sanitizes_requirement_filename or
  unsupported_extension or over_size_limit or at_size_limit or
  filename_without_basename or missing_filename_validation or
  invalid_requirement_filename_values or target_resolving_outside"` terminó
  con **12 passed**. Incluye el caso válido y contenido/respuesta, `basename`
  confinado, extensión, límite sobre y exacto, nombres inválidos, y una
  resolución simulada fuera del directorio. La suite completa con cobertura
  terminó **39 passed**; cobertura global de `app/main.py` **96%**, reporte
  HTML en `api/htmlcov/`.
- **Cobertura del código modificado (api, H-API-04):** 28/28 sentencias
  ejecutables y 12/12 ramas cubiertas en el bloque de validación, lectura y
  escritura de carga; cálculo con JSON de Coverage de la suite completa.
- **Estado de H-API-04:** Resuelto con los límites y status confirmados; no se
  cambió la ruta ni las claves/forma de la respuesta válida. Se cerró este
  item antes de iniciar H-API-05.
- **Pruebas de carga cubiertas:** nombre seguro y contenido íntegro,
  confinamiento del basename, extensión rechazada con `415`, exceso con
  `413`, nombre inválido con `400`, nombre multipart ausente con `422`, y
  tamaño exacto del límite aceptado.

### H-API-05 — Dependencias con advisories de seguridad

- **Hallazgo y problema:** `H-API-05`, inicialmente Pendiente, severidad alta.
  La auditoría reportó dependencias runtime con advisories conocidos,
  incluyendo la transitiva `starlette`.
- **Cambio aplicado:** `api/requirements.txt` fija
  `fastapi==0.162.0`, `starlette==1.10.0`, `urllib3==2.8.0` y
  `python-multipart==0.0.32`. FastAPI se actualizó porque su pin previo
  restringía Starlette a `<0.51.0` e impedía instalar una versión corregida.
  No se añadió el scanner al runtime.
- **Archivos tocados:** `api/requirements.txt`; artefactos de escaneo y
  resumen en el directorio autorizado `api/reports/cve/`. No se cambió código
  de ejecución ni el contrato de endpoints.
- **Caracterización antes de tocar esos archivos:** ejecutar y registrar el
  baseline de pruebas API y el escaneo de dependencias antes de actualizar;
  conservar salida/herramienta/versiones suficientes para comparar.
- **Baseline previo (api, H-API-05):** antes de modificar dependencias, la
  suite completa posterior a H-API-04 terminó **39 passed**, con **96%**
  global de cobertura. `python -m pip check` desde cwd `api/` respondió
  `No broken requirements found`. No hubo cambio de código ni de manifiesto
  entre ese baseline y el escaneo nuevo.
- **Ejecución SCA previa (api, H-API-05):** `pip-audit` durante H-API-01
  terminó con código **1** y reportó **32 findings** para `urllib3 2.5.0`,
  `python-multipart 0.0.21` y `starlette 0.50.0`; no se ocultó ninguno.
- **Reescaneo detallado previo (api, H-API-05):** Python **3.13.15** y
  `pip-audit 2.10.1`; comando
  `.\.venv\Scripts\pip-audit.exe -r requirements.txt --format json --output
  "$env:TEMP\api-hapi05-before.json"` desde cwd `api/`; terminó con código **1**
  y **32 findings** en `urllib3 2.5.0`, `python-multipart 0.0.21` y
  `starlette 0.50.0`, que corresponden a **17 advisory/package pairs
  únicos** tras deduplicar aliases repetidos. El JSON bruto se conservará en
  `api/reports/cve/pip-audit-before.json`; el reporte normalizado estará en
  `api/reports/cve/cve-report-1.json`.
- **Severidad y objetivo propuesto (api, H-API-05):** GitHub Security
  Advisories API confirmó severidad para los 17 GHSA del reporte. Los índices
  de paquetes publican `urllib3 2.8.0`, `python-multipart 0.0.32` y
  `starlette 1.10.0` como versiones actuales consultadas; cubren los mínimos
  fijados por el reporte (`2.8.0`, `0.0.31` y `1.3.1`, respectivamente).
  `fastapi 0.128.2` requiere `starlette<0.51.0`; la versión consultada de
  `fastapi 0.162.0` declara `starlette>=0.46.0`, por lo que habilita la
  corrección de Starlette 1.x. Cambiar FastAPI y fijar Starlette 1.x es una
  actualización de compatibilidad con riesgo mayor.
- **Decisión acordada (api, H-API-05):** la persona usuaria autorizó
  explícitamente `fastapi==0.162.0` junto con `starlette==1.10.0`, sujeto a
  verificar compatibilidad con la suite API. También se actualizarán los
  pins vulnerables a `urllib3==2.8.0` y `python-multipart==0.0.32`.
- **Reporte previo (api, H-API-05):** se preservó la salida JSON original de
  pip-audit en `api/reports/cve/pip-audit-before.json`; el reporte normalizado
  con los 17 advisories únicos, severidad GHSA y destinos propuestos está en
  `api/reports/cve/cve-report-1.json`. Estos artefactos no sustituyen el
  reescaneo posterior.
- **Verificación posterior (api, H-API-05):** tras `pip install -r
  requirements.txt` desde cwd `api/`, `.\.venv\Scripts\pip-audit.exe -r
  requirements.txt --format json --output "$env:TEMP\api-hapi05-after.json"`
  terminó con **0 findings**, código **0**. `python -m pip check` respondió
  `No broken requirements found`; las versiones instaladas fueron FastAPI
  `0.162.0`, Starlette `1.10.0`, urllib3 `2.8.0` y python-multipart `0.0.32`.
  `api/reports/cve/pip-audit-after.json` conserva el JSON bruto;
  `cve-report-2.json` y `final-cve-report.json` contienen arrays vacíos.
- **Regresión posterior (api, H-API-05):** desde cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py --cov=app.main
  --cov-branch --cov-report=term-missing --cov-report=html` terminó con
  **39 passed**, **96%** de cobertura global y reporte `api/htmlcov/`.
  El cambio de este hallazgo es solo de dependencias; no se atribuye ese
  porcentaje global como cobertura de código del diff.
- **Warnings observados:** la ejecución mostró advertencia deprecada de
  Starlette que recomienda `httpx2` con `starlette.testclient`, además de la
  advertencia existente de `FastAPI.on_event`. No se suprimieron; migrar el
  test client queda fuera de H-API-05.
- **Método/artefacto:** la herramienta compartida `appmod-cve-assessment`
  admite Maven, NuGet y npm, no Python. Se utilizó el fallback de la skill y
  se corroboraron findings y severidades con `pip-audit` y la GitHub Security
  Advisories API, sin instalar scanner de runtime. La persona usuaria
  autorizó `api/reports/cve/`.
- **Estado de H-API-05:** Resuelto. El reescaneo final está limpio; resumen y
  reportes preservan hallazgos previos y posteriores.

### H-API-06 — Responsabilidades concentradas en `main.py`

- **Hallazgo y problema:** `H-API-06`, severidad media. Antes del cambio,
  inicialización SQLite, rutas, serialización, reglas y acceso a disco vivían
  en `api/app/main.py:102-127,129-138,140-208`, acoplando cambios y
  dificultando probar capas independientemente.
- **Cambio propuesto:** separar rutas FastAPI, servicios de reglas y
  repositorios de persistencia; mantener `create_app` como composición e
  inyección de base de datos/directorio para pruebas. Introducir solo módulos
  que reduzcan responsabilidades reales y evitar abstracciones duplicadas.
  Conservar métodos, códigos, campos y defaults observados salvo los cambios
  de seguridad descritos explícitamente en H-API-01, H-API-02 y H-API-04.
- **Archivos modificados:** `api/app/main.py`,
  `api/app/routes.py`, `api/app/services.py`, `api/app/security.py`,
  `api/app/repository.py` y `api/tests/test_api.py`.
- **Caracterización antes de tocar esos archivos:** ampliar primero pruebas
  de todos los endpoints observados: listado, creación, resumen, carga,
  validación de token e integración de backend-health con HTTP simulado. Fijar
  status, JSON, datos sembrados, defaults y errores sin contactar servicios
  externos.
- **Caracterización previa (api, H-API-06):** antes de refactorizar, la
  suite completa con cobertura terminó **41 passed**, **99%** global de
  `app/main.py`. Las pruebas nuevas `test_backend_health_returns_mocked_backend_response`
  y `test_backend_health_returns_observed_failure_response` pasaron (**2
  passed**) con HTTP simulado; fijan el status/body y los argumentos
  `GET`, URL configurada y timeout `3.0`. No se contactó backend externo.
- **Cambio/diff local (api, H-API-06):** `main.py` conserva composición e
  inyección; rutas HTTP se registran en `routes.py`; reglas de tareas, carga y
  backend-health residen en `services.py`; JWT/owner en `security.py`; SQLite
  en `repository.py`. No se añadieron rutas ni se alteraron las formas de las
  respuestas observadas.
- **Pruebas posteriores (api, H-API-06):** desde la raíz, con cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py --cov=app
  --cov-branch --cov-report=term-missing --cov-report=html` terminó con
  **41 passed**. Cobertura global del paquete `app`: **99%** (193/193
  sentencias cubiertas; 32/34 ramas cubiertas, 2 parcialmente cubiertas en
  `services.py:87-88`). Los dos tests de backend-health siguen usando mocks;
  no se contactó un servicio externo. Se observaron advertencias deprecadas
  de `httpx`/Starlette TestClient y `FastAPI.on_event`; no se ocultaron.
- **Estado de H-API-06:** Resuelto. El diff de separación y la regresión de
  41 pruebas respaldan la preservación del contrato observado. No se afirma
  100% de cobertura de ramas; la cobertura de sentencias es 100%.

### H-API-07 — Tipado genérico, errores amplios y anidamiento

- **Hallazgo y problema:** `H-API-07`, severidad baja. Antes del cambio,
  payloads y
  respuestas usan `dict[str, Any]`/`dict` (`api/app/routes.py:23-58`,
  `api/app/services.py:53-105,107-128,130-141`), existe una captura amplia
  (`api/app/services.py:136-141`) y hay condicionales anidados en el resumen
  (`api/app/services.py:66-88`). La duplicación mencionada
  en el reto no quedó confirmada y no se planifica eliminar duplicación sin
  evidencia.
- **Cambio propuesto:** introducir modelos Pydantic para request/response
  preservando campos requeridos, defaults, nombres JSON y status observados;
  dividir métodos por responsabilidad, extraer el cálculo del resumen y usar
  retornos anticipados donde mejoren claridad. Capturar errores esperados de
  forma específica, devolver mensajes genéricos y registrar detalles solo en
  logs controlados. Centralizar valores de dominio relevantes en constantes.
  Evitar cambios de contrato no acordados, especialmente validación nueva de
  tipos/rangos.
- **Archivos modificados:** `api/app/routes.py`, `api/app/services.py`,
  `api/app/schemas.py` y `api/tests/test_api.py`.
- **Caracterización antes de tocar esos archivos:** fijar claves y tipos JSON,
  defaults para campos omitidos, aceptación/rechazo actual de payloads,
  errores 401 y status/body de backend-health ante fallo simulado. No contactar
  el backend real.
- **Caracterización previa (api, H-API-07):** se añadieron tests que fijan
  defaults, coerción a string, claves de creación y conteos de resumen para
  `TODO`, `DONE` y `ARCHIVED`, junto con el test existente del error de
  backend. Antes de modificar producción, con cwd `api/`,
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_api.py --cov=app
  --cov-branch --cov-report=term-missing --cov-report=html` terminó con
  **43 passed**, **100%** global (193/193 sentencias y 34/34 ramas). No se
  contactaron servicios externos.
- **Cambio/diff local (api, H-API-07):** nuevo `api/app/schemas.py` con
  modelos Pydantic de request/response; `routes.py` declara modelos de salida
  y tipa el cuerpo de creación; `services.py` usa modelos de salida, calcula
  `byStatus` con una sola condición por estado, excluye `DONE`/`ARCHIVED` con
  una condición combinada y centraliza valores de dominio relevantes. El
  backend-health captura solo `urllib3.exceptions.HTTPError`, registra el
  detalle en log y responde con mensaje genérico; fallas inesperadas no se
  convierten en éxito y el servidor devuelve un `500` genérico. Campos,
  defaults, status exitosos y nombres JSON observados permanecen iguales. No
  se agregaron dependencias.
- **Pruebas posteriores (api, H-API-07):** se actualizó el caso de fallo de
  transporte para usar `HTTPError` y comprobar el mensaje genérico; un test
  adicional asegura que una excepción inesperada resulte en `500` sin filtrar
  su   detalle. Con cwd `api/`, `.\.venv\Scripts\python.exe -m pytest -q
  tests\test_api.py --cov=app --cov-branch --cov-report=term-missing
  --cov-report=html` terminó con **44 passed**, **100% global de `app`**:
  233/233 sentencias y 28/28 ramas; las sentencias ejecutables modificadas en
  `routes.py`, `services.py` y `schemas.py` quedaron cubiertas. Las únicas
  advertencias fueron las deprecaciones ya visibles de Starlette TestClient
  (`httpx`) y `FastAPI.on_event`; no se silenciaron.
- **Iteración de validación:** una primera definición recursiva local de
  `JsonValue` provocó error de colección Pydantic; se reemplazó por el tipo
  `pydantic.JsonValue` y la suite final pasó. No quedó una desviación funcional
  del plan.
- **Estado de H-API-07:** Resuelto; diff, caracterización previa y regresión
  posterior respaldan la conservación del contrato observado.

## Secuencia, dependencias y cobertura

1. Crear/ejecutar pruebas de caracterización antes de cambios, con datos y
   archivos temporales; documentar línea base.
2. Coordinar la emisión JWT externa para H-API-01. La política de owner para
   H-API-02 y los límites de carga para H-API-04 ya fueron confirmados y se
   registraron en sus apartados; mantenerlos como decisiones de contrato.
3. Implementar H-API-01 a H-API-05 con sus pruebas, manteniendo rutas y formas
   de respuesta; registrar explícitamente cualquier cambio semántico de
   seguridad.
4. Separar capas por H-API-06 y aplicar tipado/errores/refactor por H-API-07,
   ejecutando regresión tras cada lote revisable.
5. Ejecutar SCA antes/después de cualquier cambio de dependencia; conservar
   alertas, no bajar gates ni umbrales.

README.md documenta `python tools/lab.py test api` desde la raíz. Para ejecutar
directamente desde `api/` y producir cobertura global/reporte HTML, se propone:

```bash
python -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=html
```

La meta es 85% para el código modificado, distinta de la cobertura global.
Medir ambas por separado y calcular cobertura del diff con líneas ejecutables
modificadas cubiertas / líneas ejecutables modificadas totales, indicando
archivos, numerador y denominador. El comando/reporte por sí solo no prueba
cobertura específica del diff. No se ejecutó ninguna prueba o escaneo durante
la preparación de este plan.
