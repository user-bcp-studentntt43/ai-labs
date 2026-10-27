# Hallazgos

Discovery de `api/`, con referencias desde la raíz. Los estados y notas de
resolución reflejan la evidencia registrada por hallazgo; no implican
aprobación humana de otros cambios pendientes.

## Contrato observado de API

El contrato HTTP observado y las decisiones acordadas se documentan en
`docs/ENDPOINTS.md`. La tabla de abajo resume las rutas actuales; la
especificación detallada de campos, ejemplos y status está en ese documento:

| Ruta | Comportamiento observado |
|---|---|
| `GET /api/tasks` | Requiere encabezado de autorización con token. Acepta `owner` opcional; si falta o es vacío usa el username del token, y si difiere devuelve `403`. Devuelve tareas serializadas con `id`, `title`, `description`, `status`, `owner`, `priority` y `createdAt` (`api/app/routes.py:26-32`). |
| `POST /api/tasks` | Requiere token; recibe un objeto y devuelve `201` con la tarea serializada. Aplica valores por defecto; owner omitido usa la identidad y owner explícito distinto devuelve `403` (`api/app/routes.py:34-43`). |
| `GET /api/summary` | Requiere token, acepta `owner` opcional; mismatch devuelve `403`. Devuelve `owner`, `total`, `byStatus` y `highPriorityOpen` (`api/app/routes.py:45-51`). |
| `POST /api/requirements` | Requiere token y archivo multipart `.txt` de hasta 1 MiB. Normaliza el nombre a un basename dentro del directorio; responde `415` por extensión no permitida, `413` por tamaño excedido y `400` por nombre inválido (`api/app/routes.py:53-62`, `api/app/services.py:33-66,119-143`). |
| `GET /api/backend-health` | Requiere token; consulta `AUTH_HEALTH_URL` o `http://localhost:8080/q/health` y devuelve status/body (`api/app/routes.py:64-68`, `api/app/services.py:144-162`). |

El token del discovery inicial era Base64 de `username|role|expiry|secret`
(`api/app/main.py:14,17-26`, antes de H-API-01). Tras resolver H-API-01, la API
exige JWT RS256 con issuer `BCP`, audience `dev`, claims `exp`, `iss`, `aud`,
`username` y `role`, y clave RSA pública en `devpub`
(`api/app/security.py:11-56`).
SQLite se abre con `WORKSHOP_DB_PATH` o `./data/workshop.db`; el repositorio
crea la tabla y carga datos iniciales (`api/app/main.py:17-27`,
`api/app/repository.py:5-56`).

## Matriz de seguimiento — API

| id | componente | hallazgo | tipo | explicacion | evidencia (archivo:linea) | severidad | estado |
|---|---|---|---|---|---|---|---|
| H-API-01 | api | Token Base64 con secreto embebido | Vulnerabilidad | Base64 no autentica criptográficamente el contenido y el secreto estaba en el código; quien conozca el formato podía elegir identidad, rol y expiración. Resuelto: se valida JWT RS256 con issuer/audience acordados y clave `devpub`; pruebas JWT en `api/tests/test_api.py` (18 passed en esa etapa). | `api/app/security.py:11-56` (corrección; código vulnerable antes del cambio en `api/app/main.py:14,17-26`) | alta | Resuelto |
| H-API-02 | api | El cliente controla `owner` en consultas y creación | Vulnerabilidad | `GET /api/tasks` y `GET /api/summary` permitían consultar un owner indicado por el cliente; `POST /api/tasks` permitía asignarlo en el cuerpo. Resuelto: solicitudes con owner distinto a la identidad ahora reciben 403; pruebas de autorización en `api/tests/test_api.py` (24 passed en suite completa a esa etapa). | `api/app/security.py:16-20`, `api/app/routes.py:26-43,45-51` | alta | Resuelto |
| H-API-03 | api | Filtros e inserts SQL concatenados | Vulnerabilidad | Valores externos y el ID insertado se concatenaban en SQL. Resuelto: filtros, `INSERT` y consulta por ID usan placeholders con parámetros enlazados; pruebas de apóstrofes y de argumentos de `execute` en `api/tests/test_api.py` (28 passed en esa etapa). | `api/app/repository.py:34-53` | alta | Resuelto |
| H-API-05 | api | Dependencias runtime con advisories conocidas | Vulnerabilidad | La auditoría inicial encontró 32 registros (17 advisories GHSA únicos) en `urllib3==2.5.0`, `python-multipart==0.0.21` y `starlette==0.50.0`. Resuelto: pins actualizados, incluyendo FastAPI por compatibilidad; el reescaneo reportó 0 findings. Reportes y resumen en `api/reports/cve/`. | `api/requirements.txt:1-7`; reportes `api/reports/cve/cve-report-1.json` y `final-cve-report.json` | alta | Resuelto |
| H-API-04 | api | Nombre de archivo de carga usado directamente | Vulnerabilidad | `file.filename` se combinaba con el directorio sin normalización, extensión permitida ni límite de lectura. Resuelto: basename saneado y confinado, allowlist `.txt`, máximo de 1048576 bytes leído en bloques, `415`/`413`/`400` según el error; la validación multipart de nombre ausente conserva `422`. Pruebas focalizadas y suite completa (39 passed en esa etapa). | `api/app/services.py:33-66,119-143`, `api/app/routes.py:53-62` | media | Resuelto |
| H-API-06 | api | Rutas, acceso a datos, reglas y serialización concentrados en un módulo | Refactor | Inicialización/composición, endpoints, reglas, serialización y persistencia estaban concentradas. Resuelto: se separaron composición, rutas, servicios, seguridad y repositorio; la suite preserva los endpoints y sus respuestas (41 passed). | `api/app/main.py:17-42`, `api/app/routes.py:20-68`, `api/app/repository.py:5-57`, `api/app/services.py:68-162`, `api/app/security.py:16-56` | media | Resuelto |
| H-API-07 | api | Uso de `dict`, captura amplia y condicionales anidados | Refactor | Los payloads/respuestas usaban diccionarios genéricos, se capturaban excepciones amplias y el cálculo del resumen tenía condicionales anidados. Resuelto: modelos Pydantic tipados conservan los campos y valores observados, resumen con una sola condición y manejo específico de errores HTTP de backend sin devolver detalles internos; suite posterior **44 passed**, cobertura global **100%**. | `api/app/schemas.py:8-47`, `api/app/routes.py:26-68`, `api/app/services.py:68-162` | baja | Resuelto |

## Validación

La caracterización inicial del discovery no ejecutó pruebas. Tras H-API-04,
`api/tests/test_api.py` pasó con **39 passed**; tras H-API-05, **39 passed**
y 96% global; tras H-API-06, **41 passed** y 99% global del paquete `app`.
H-API-01 obtuvo **27/27 sentencias** en el
autenticador; H-API-02 obtuvo **8/8 sentencias y 2/2 ramas** en la política de
owner; H-API-03 obtuvo **6/6 sentencias SQL modificadas**; H-API-04 obtuvo
**28/28 sentencias y 12/12 ramas** en el código de carga modificado. La
auditoría inicial reportó 32 registros y la auditoría posterior, **0
findings**; H-API-06 cubrió todas las sentencias ejecutables de los módulos
separados. Tras H-API-07, la suite pasó con **44 tests**, **100% global**,
233/233 sentencias y 28/28 ramas de `app`; todas las sentencias ejecutables
de `routes.py`, `services.py` y `schemas.py` quedaron cubiertas. En la
ejecución de pruebas de contrato posterior se registraron **67 tests passed**,
también con **100% global** (233/233 sentencias y 28/28 ramas), vinculada a
H-API-01 a H-API-07 en `docs/TESTING.md`. Los comandos y resultados
históricos por hallazgo permanecen en `PLAN.md`.
