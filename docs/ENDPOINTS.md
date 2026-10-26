# Contrato HTTP — API ReqFlow

Este documento describe los cinco endpoints actuales de la API de tareas,
requerimientos y estado del backend. Los ejemplos muestran la estructura y
valores permitidos por el código; las fechas, identificadores, rutas de disco y
el contenido del backend dependen de la ejecución.

## Alcance del contrato

- **Contrato observado:** los métodos, rutas, campos y comportamientos
  documentados abajo se derivan de `api/app/routes.py`,
  `api/app/schemas.py`, `api/app/security.py`,
  `api/app/services.py` y `api/app/repository.py`.
- **Decisiones acordadas:** JWT firmado con RS256, `iss=BCP`, `aud=dev` y
  clave pública configurada en `devpub`; las operaciones de tareas quedan
  limitadas al username autenticado y un `owner` explícito distinto se rechaza
  con `403`; la carga acepta `.txt` hasta 1.048.576 bytes, con `415` para
  extensiones no permitidas y `413` para archivos que superen el máximo.
  Decisiones registradas en `PLAN.md` para H-API-01, H-API-02 y H-API-04.
- **Riesgos/preguntas abiertas:** no existe especificación OpenAPI independiente
  ni contrato humano separado del código; este documento registra el contrato
  observado, no añade garantías sobre disponibilidad del backend ni sobre el
  formato del timestamp. El token debe ser emitido por un componente que
  produzca los claims y la firma acordados.

## Autenticación común

Todos los endpoints requieren este encabezado:

```http
Authorization: Bearer <JWT>
```

La API verifica la firma RS256 y exige `exp`, `iss`, `aud`, `username` y `role`;
`iss` debe ser `BCP`, `aud` debe ser `dev`, y `username` y `role` deben ser
cadenas. No se acepta el token Base64 anterior. La configuración ausente o
inválida de la clave pública es un error del servidor, no un rechazo normal de
credenciales (`api/app/security.py:23-56`).

Un rechazo común de autenticación devuelve `401`:

```json
{"detail":"Invalid token"}
```

El cuerpo de un error interno del servidor se presenta como texto plano:

```text
Internal Server Error
```

## `GET /api/tasks`

1. **Qué hace:** lista las tareas asignadas al usuario autenticado
   (`api/app/routes.py:26-32`).
2. **Autenticación:** sí; enviar el encabezado común
   `Authorization: Bearer <JWT>`.
3. **Request**

   | Campo/parámetro | Tipo | Obligatorio | Descripción |
   |---|---|---:|---|
   | `owner` (query) | string | No | Si se omite o está vacío se usa `username` del JWT. Si contiene otro username, la solicitud se rechaza con `403`. |

   Ejemplo completo:

   ```http
   GET /api/tasks?owner=student HTTP/1.1
   Host: api.example.test
   Authorization: Bearer <JWT>
   Accept: application/json
   ```

4. **Response exitosa:** `200 OK`. Cada elemento contiene:

   | Campo | Tipo | Descripción |
   |---|---|---|
   | `id` | integer | Identificador de la tarea. |
   | `title` | string | Título. |
   | `description` | string | Descripción. |
   | `status` | string | Estado de la tarea. |
   | `owner` | string | Username propietario. |
   | `priority` | string | Prioridad. |
   | `createdAt` | string | Fecha de creación serializada por SQLite. |

   Ejemplo completo con las dos tareas semilla del usuario `student`:

   ```json
   [
     {
       "id": 1,
       "title": "Refactor login",
       "description": "Separar responsabilidades en frontend",
       "status": "TODO",
       "owner": "student",
       "priority": "HIGH",
       "createdAt": "2026-10-26 16:30:00"
     },
     {
       "id": 2,
       "title": "Review API",
       "description": "Revisar seguridad de endpoints",
       "status": "IN_PROGRESS",
       "owner": "student",
       "priority": "MEDIUM",
       "createdAt": "2026-10-26 16:31:00"
     }
   ]
   ```

   Los IDs y fechas del ejemplo son ilustrativos; el código no fija esos
   timestamps (`api/app/repository.py:21-32,34-36`).
5. **Respuestas de error**

   | Estado | Cuándo ocurre | Ejemplo de cuerpo |
   |---|---|---|
   | `401 Unauthorized` | Falta el Bearer, el token no es válido, expiró o no cumple firma/claims. | `{"detail":"Invalid token"}` |
   | `403 Forbidden` | Se envía un `owner` distinto del username autenticado. | `{"detail":"Forbidden"}` |
   | `500 Internal Server Error` | La clave de verificación no está configurada o es inválida, o falla una operación interna. | `Internal Server Error` (texto plano) |
6. **Notas de seguridad:** el filtro SQL usa el owner derivado de la identidad
   autenticada; el query parameter no permite consultar tareas de otro usuario
   (`api/app/security.py:16-20`, `api/app/repository.py:34-36`).

## `POST /api/tasks`

1. **Qué hace:** crea una tarea para el usuario autenticado y devuelve la
   tarea persistida (`api/app/routes.py:34-43`).
2. **Autenticación:** sí; enviar el encabezado común
   `Authorization: Bearer <JWT>`.
3. **Request**

   | Campo/parámetro | Tipo | Obligatorio | Descripción |
   |---|---|---:|---|
   | cuerpo JSON | objeto | Sí | El objeto puede omitir todos los campos opcionales de abajo. |
   | `title` | valor JSON | No | Se convierte a string; default `""`. |
   | `description` | valor JSON | No | Se convierte a string; default `""`. |
   | `status` | valor JSON | No | Se convierte a string; default `"TODO"`. |
   | `priority` | valor JSON | No | Se convierte a string; default `"MEDIUM"`. |
   | `owner` | valor JSON | No | Si se omite, se asigna el username autenticado. Si se envía, debe representar ese mismo username; un valor distinto se rechaza. |

   Los campos admiten valores JSON; los campos extra no forman parte del
   modelo y se ignoran. Para una integración normal, enviar strings en los
   campos de texto y `owner` (`api/app/schemas.py:9-14`,
   `api/app/services.py:75-85`).

   Ejemplo completo:

   ```http
   POST /api/tasks HTTP/1.1
   Host: api.example.test
   Authorization: Bearer <JWT>
   Content-Type: application/json
   Accept: application/json

   {
     "title": "Preparar pruebas de API",
     "description": "Verificar creación y resumen",
     "status": "TODO",
     "priority": "HIGH",
     "owner": "student"
   }
   ```

4. **Response exitosa:** `201 Created`. Devuelve:

   | Campo | Tipo | Descripción |
   |---|---|---|
   | `id` | integer | Identificador asignado por SQLite. |
   | `title` | string | Título guardado. |
   | `description` | string | Descripción guardada. |
   | `status` | string | Estado guardado. |
   | `owner` | string | Username autenticado. |
   | `priority` | string | Prioridad guardada. |
   | `createdAt` | string | Fecha de creación serializada por SQLite. |

   Ejemplo completo:

   ```json
   {
     "id": 4,
     "title": "Preparar pruebas de API",
     "description": "Verificar creación y resumen",
     "status": "TODO",
     "owner": "student",
     "priority": "HIGH",
     "createdAt": "2026-10-26 16:35:00"
   }
   ```

   ID y fecha dependen del estado de la base de datos.
5. **Respuestas de error**

   | Estado | Cuándo ocurre | Ejemplo de cuerpo |
   |---|---|---|
   | `401 Unauthorized` | Falta el Bearer, el token no es válido, expiró o no cumple firma/claims. | `{"detail":"Invalid token"}` |
   | `403 Forbidden` | `owner` está presente y no coincide con el username del JWT. | `{"detail":"Forbidden"}` |
   | `422 Unprocessable Entity` | El cuerpo está ausente o no puede validarse como el objeto JSON esperado. | `{"detail":[{"loc":["body"],"msg":"Field required","type":"missing","input":null}]}` |
   | `500 Internal Server Error` | Clave JWT inválida/ausente u otro fallo interno, por ejemplo persistencia. | `Internal Server Error` (texto plano) |
6. **Notas de seguridad:** la identidad del token determina el propietario
   persistido. Un campo `owner` no puede asignar tareas a otra identidad.
   `title`, `description`, `status` y `priority` se enlazan como parámetros
   SQLite, no se concatenan al SQL (`api/app/security.py:16-20`,
   `api/app/repository.py:38-49`).

## `GET /api/summary`

1. **Qué hace:** resume el número de tareas del usuario autenticado por estado
   y cuenta las tareas de prioridad alta que no están cerradas
   (`api/app/routes.py:45-51`, `api/app/services.py:87-106`).
2. **Autenticación:** sí; enviar el encabezado común
   `Authorization: Bearer <JWT>`.
3. **Request**

   | Campo/parámetro | Tipo | Obligatorio | Descripción |
   |---|---|---:|---|
   | `owner` (query) | string | No | Si se omite o está vacío se usa `username` del JWT. Si contiene otro username, la solicitud se rechaza con `403`. |

   Ejemplo completo:

   ```http
   GET /api/summary?owner=student HTTP/1.1
   Host: api.example.test
   Authorization: Bearer <JWT>
   Accept: application/json
   ```

4. **Response exitosa:** `200 OK`. Campos:

   | Campo | Tipo | Descripción |
   |---|---|---|
   | `owner` | string | Username resumido. |
   | `total` | integer | Total de tareas del usuario. |
   | `byStatus` | objeto de string a integer | Conteo de tareas agrupado por cada valor de `status` presente. |
   | `highPriorityOpen` | integer | Tareas `HIGH` cuyo estado no es `DONE` ni `ARCHIVED`. |

   Ejemplo completo para los datos semilla de `student`:

   ```json
   {
     "owner": "student",
     "total": 2,
     "byStatus": {
       "TODO": 1,
       "IN_PROGRESS": 1
     },
     "highPriorityOpen": 1
   }
   ```
5. **Respuestas de error**

   | Estado | Cuándo ocurre | Ejemplo de cuerpo |
   |---|---|---|
   | `401 Unauthorized` | Falta el Bearer, el token no es válido, expiró o no cumple firma/claims. | `{"detail":"Invalid token"}` |
   | `403 Forbidden` | Se envía un `owner` distinto del username autenticado. | `{"detail":"Forbidden"}` |
   | `500 Internal Server Error` | Clave JWT inválida/ausente u otro fallo interno de persistencia. | `Internal Server Error` (texto plano) |
6. **Notas de seguridad:** el owner efectivo siempre es el `username`
   autenticado; el query parameter no puede consultar el resumen de otro
   usuario. La consulta SQLite filtra con parámetro enlazado
   (`api/app/security.py:16-20`, `api/app/repository.py:51-54`).

## `POST /api/requirements`

1. **Qué hace:** guarda un archivo de requerimientos de texto para el usuario
   autenticado (`api/app/routes.py:53-62`,
   `api/app/services.py:119-143`).
2. **Autenticación:** sí; enviar el encabezado común
   `Authorization: Bearer <JWT>`.
3. **Request**

   | Campo/parámetro | Tipo | Obligatorio | Descripción |
   |---|---|---:|---|
   | `file` (multipart) | archivo binario | Sí | Campo multipart llamado `file`. El nombre debe tener extensión `.txt` (la comparación no distingue mayúsculas) y el contenido no puede superar 1.048.576 bytes. |

   Ejemplo completo con curl:

   ```bash
   curl -X POST "https://api.example.test/api/requirements" \
     -H "Authorization: Bearer <JWT>" \
     -H "Accept: application/json" \
     -F "file=@requirements.txt;type=text/plain"
   ```

   El servidor normaliza el nombre recibido a un basename antes de guardar;
   `file.filename` no se usa directamente como ruta
   (`api/app/services.py:33-49,124-133`).
4. **Response exitosa:** `201 Created`. Campos:

   | Campo | Tipo | Descripción |
   |---|---|---|
   | `owner` | string | Username autenticado que realizó la carga. |
   | `fileName` | string | Basename normalizado del archivo guardado. |
   | `storedAt` | string | Ruta local donde se guardó; depende de `WORKSHOP_UPLOAD_DIR` y del entorno. |
   | `size` | integer | Tamaño del contenido guardado en bytes. |

   Ejemplo completo:

   ```json
   {
     "owner": "student",
     "fileName": "requirements.txt",
     "storedAt": "/srv/reqflow/uploads/requirements.txt",
     "size": 28
   }
   ```

   La ruta es ilustrativa y variará según la configuración del servidor.
5. **Respuestas de error**

   | Estado | Cuándo ocurre | Ejemplo de cuerpo |
   |---|---|---|
   | `400 Bad Request` | Nombre inválido o sin basename aceptable; también multipart malformado. | `{"detail":"Invalid filename"}`; para multipart malformado: `{"detail":"Invalid multipart data."}` |
   | `401 Unauthorized` | Falta el Bearer, el token no es válido, expiró o no cumple firma/claims. | `{"detail":"Invalid token"}` |
   | `413 Content Too Large` | El archivo excede 1.048.576 bytes. | `{"detail":"File exceeds maximum size"}` |
   | `415 Unsupported Media Type` | La extensión no es `.txt`. | `{"detail":"Unsupported file extension"}` |
   | `422 Unprocessable Entity` | Falta el campo requerido `file` o el nombre de archivo está vacío y FastAPI no recibe un `UploadFile` válido. | `{"detail":[{"type":"missing","loc":["body","file"],"msg":"Field required","input":null}]}` |
   | `500 Internal Server Error` | Clave JWT inválida/ausente o fallo interno de escritura. | `Internal Server Error` (texto plano) |
6. **Notas de seguridad:** solo se aceptan archivos `.txt` hasta el límite
   indicado. La lectura se hace en bloques y el nombre se normaliza y confina
   al directorio configurado. El campo `owner` de la respuesta procede del
   token, no del formulario (`api/app/services.py:20-66,119-143`).

## `GET /api/backend-health`

1. **Qué hace:** consulta el endpoint de salud de autenticación y devuelve el
   resultado de esa comprobación junto con el usuario solicitante
   (`api/app/routes.py:64-68`, `api/app/services.py:144-162`).
2. **Autenticación:** sí; enviar el encabezado común
   `Authorization: Bearer <JWT>`.
3. **Request**

   | Campo/parámetro | Tipo | Obligatorio | Descripción |
   |---|---|---:|---|
   | ninguno | — | — | No recibe query parameters ni cuerpo. La URL consultada por el servidor es `AUTH_HEALTH_URL` o, si no está configurada, `http://localhost:8080/q/health`. |

   Ejemplo completo:

   ```http
   GET /api/backend-health HTTP/1.1
   Host: api.example.test
   Authorization: Bearer <JWT>
   Accept: application/json
   ```

4. **Response exitosa:** `200 OK` cuando la llamada al servicio se completa.
   Campos:

   | Campo | Tipo | Descripción |
   |---|---|---|
   | `requestedBy` | string | Username autenticado que solicitó el chequeo. |
   | `status` | integer | Código HTTP recibido del servicio consultado; `0` representa error de transporte capturado. |
   | `body` | string | Cuerpo recibido, decodificado como UTF-8; en error de transporte contiene el mensaje genérico. |

   Ejemplo completo de respuesta recibida por el test con backend simulado:

   ```json
   {
     "requestedBy": "student",
     "status": 202,
     "body": "backend ready"
   }
   ```

   Si urllib3 genera un error HTTP de transporte, el endpoint sigue respondiendo
   `200 OK` con `status: 0`:

   ```json
   {
     "requestedBy": "student",
     "status": 0,
     "body": "Backend health check failed"
   }
   ```
5. **Respuestas de error**

   | Estado | Cuándo ocurre | Ejemplo de cuerpo |
   |---|---|---|
   | `401 Unauthorized` | Falta el Bearer, el token no es válido, expiró o no cumple firma/claims. | `{"detail":"Invalid token"}` |
   | `500 Internal Server Error` | Falla inesperada no clasificada como `urllib3.exceptions.HTTPError`, falla la decodificación UTF-8 o hay un error de configuración JWT. | `Internal Server Error` (texto plano) |

   Un error HTTP de transporte de urllib3 no es un status de error de este
   endpoint: se representa en la respuesta `200` anterior
   (`api/app/services.py:147-162`).
6. **Notas de seguridad:** el username se toma de la identidad verificada.
   Los detalles de `urllib3.exceptions.HTTPError` se registran en el log del
   servidor, no se incluyen en el cuerpo de respuesta
   (`api/app/services.py:151-157`). Esta ruta provoca una llamada saliente a
   la URL configurada; los consumidores deben tratar `status: 0` como backend
   no disponible.
