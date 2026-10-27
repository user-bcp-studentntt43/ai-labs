# Pruebas de API — ReqFlow

## Alcance y método

La matriz cubre cada endpoint documentado en [ENDPOINTS.md](./ENDPOINTS.md):
camino feliz, bordes y las respuestas de error descritas allí. Los casos usan
`TestClient`, SQLite y directorios temporales; las llamadas a backend-health
se sustituyen por dobles locales y no contactan servicios externos.

El único archivo de código cambiado en este paso es
`api/tests/test_api.py`; no se modificó código de producción. La cobertura se
mide sobre el paquete de aplicación `app` con `pytest-cov`/Coverage.py,
incluyendo ramas. Este reporte mide el código de API ejercitado por la suite,
no cobertura interna del archivo de pruebas.

## Matriz de casos

| Endpoint | Caso | Tipo | Resultado esperado |
|---|---|---|---|
| `GET /api/tasks` | Listado con datos semilla | Camino feliz | `200`; lista las tareas del usuario autenticado. |
| `GET /api/tasks` | `owner` vacío | Borde | `200`; se usa la identidad del JWT y solo se devuelven sus tareas. |
| `GET /api/tasks` | JWT ausente o inválido | Error `401` | `{"detail":"Invalid token"}`. |
| `GET /api/tasks` | `owner` de otra identidad | Error `403` | `{"detail":"Forbidden"}`; no se listan datos ajenos. |
| `GET /api/tasks` | Clave pública JWT ausente | Error `500` | Texto genérico `Internal Server Error`, sin detalles de configuración. |
| `POST /api/tasks` | Crear con todos los campos | Camino feliz | `201`; devuelve tarea serializada con `id` y `createdAt`. |
| `POST /api/tasks` | Objeto vacío | Borde | `201`; aplica title/description vacíos, status `TODO`, priority `MEDIUM` y owner autenticado. |
| `POST /api/tasks` | JWT ausente o inválido | Error `401` | `{"detail":"Invalid token"}`. |
| `POST /api/tasks` | `owner` de otra identidad | Error `403` | `{"detail":"Forbidden"}`; no permite asignar a otro owner. |
| `POST /api/tasks` | Cuerpo ausente | Error `422` | Detalle de validación con `loc=["body"]` y `type="missing"`. |
| `POST /api/tasks` | Clave pública JWT ausente | Error `500` | Texto genérico `Internal Server Error`. |
| `GET /api/summary` | Resumen con tareas semilla | Camino feliz | `200`; `total`, `byStatus` y `highPriorityOpen` reflejan los datos. |
| `GET /api/summary` | `owner` vacío / usuario sin coincidencias | Borde | Se usa la identidad; para un owner sin tareas el resumen es vacío y total `0` (también se comprueba con username que no coincide con datos semilla). |
| `GET /api/summary` | JWT ausente o inválido | Error `401` | `{"detail":"Invalid token"}`. |
| `GET /api/summary` | `owner` de otra identidad | Error `403` | `{"detail":"Forbidden"}`. |
| `GET /api/summary` | Clave pública JWT ausente | Error `500` | Texto genérico `Internal Server Error`. |
| `POST /api/requirements` | Carga `.txt` normal | Camino feliz | `201`; guarda bytes y devuelve `owner`, `fileName`, `storedAt`, `size`. |
| `POST /api/requirements` | Archivo vacío y archivo de tamaño exacto (1.048.576 bytes) | Borde | `201`; guarda el archivo y devuelve su tamaño, incluido `0` para archivo vacío. |
| `POST /api/requirements` | Nombre con ruta | Borde de seguridad | `201`; normaliza a basename y no escribe fuera del directorio. |
| `POST /api/requirements` | JWT ausente o inválido | Error `401` | `{"detail":"Invalid token"}`. |
| `POST /api/requirements` | Nombre inválido o multipart malformado | Error `400` | Nombre: `{"detail":"Invalid filename"}`; multipart: `{"detail":"Invalid multipart data."}`. |
| `POST /api/requirements` | Archivo mayor al máximo | Error `413` | `{"detail":"File exceeds maximum size"}`. |
| `POST /api/requirements` | Extensión no permitida o sin extensión | Error `415` | `{"detail":"Unsupported file extension"}`; no se crea archivo. |
| `POST /api/requirements` | Campo de archivo ausente o nombre multipart vacío | Error `422` | FastAPI devuelve error de validación; en campo ausente `loc=["body","file"]`, `type="missing"`. |
| `POST /api/requirements` | Clave pública ausente / error de escritura | Error `500` | Texto genérico `Internal Server Error`, sin detalle interno de filesystem. |
| `GET /api/backend-health` | Backend simulado responde HTTP 202 | Camino feliz | `200` de la API; devuelve `requestedBy`, status remoto `202` y body. |
| `GET /api/backend-health` | Error de transporte simulado | Borde/degradación | `200` de la API con `status: 0` y body `Backend health check failed`. |
| `GET /api/backend-health` | JWT ausente o inválido | Error `401` | `{"detail":"Invalid token"}`. |
| `GET /api/backend-health` | Clave pública JWT ausente | Error `500` | Texto genérico `Internal Server Error`. |
| `GET /api/backend-health` | Excepción inesperada durante la llamada | Error `500` | Texto genérico `Internal Server Error`; no se filtra el detalle simulado. |

Los errores `401` y los `500` por configuración de JWT se verifican para
**cada endpoint** con pruebas parametrizadas. Los `403` se ejercitan en las
tres operaciones que aceptan owner. Los ejemplos de error de validación se
comprueban por status y localización/tipo del error, sin depender del orden de
serialización de campos internos de Pydantic.

## Código de los tests

El código ejecutable completo está en
[api/tests/test_api.py](../api/tests/test_api.py). Entre los casos añadidos
para cerrar la matriz están:

```python
@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/api/tasks", {}),
        ("POST", "/api/tasks", {"json": {}}),
        ("GET", "/api/summary", {}),
        (
            "POST",
            "/api/requirements",
            {"files": {"file": ("valid.txt", b"text", "text/plain")}},
        ),
        ("GET", "/api/backend-health", {}),
    ],
)
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer malformed-token"],
    ids=["missing-token", "invalid-token"],
)
def test_all_documented_endpoints_require_authentication(
    method: str,
    path: str,
    request_kwargs: dict[str, object],
    authorization: str | None,
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    request_headers = (
        {} if authorization is None else {"Authorization": authorization}
    )
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            headers=request_headers,
            **request_kwargs,
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}
```

Los bordes de carga y sus errores se implementan en
`test_accepts_requirement_with_empty_content`,
`test_rejects_requirement_without_extension`,
`test_accepts_requirement_at_size_limit`,
`test_rejects_requirement_over_size_limit`,
`test_rejects_malformed_multipart_body` y
`test_returns_500_without_exposing_upload_write_error`. Las pruebas de
`GET /api/tasks`, `POST /api/tasks` y `GET /api/summary`, incluidas
autorización y validación, están identificadas por función en el mismo módulo;
la suite completa se ejecutó, no son resultados propuestos.

## Ejecuciones y cobertura

| Componente / IDs | Directorio de ejecución | Comando | Código de salida | Resultado |
|---|---|---|---:|---|
| `api`, endpoints documentados (H-API-01 a H-API-07) | `api/` | `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -ra` | `0` | Suite completa aprobada: **67 tests passed**. |
| `api`, cobertura de endpoints (H-API-01 a H-API-07) | `api/` | `.\.venv\Scripts\python.exe -m pytest tests\test_api.py --cov=app --cov-branch --cov-report=term-missing --cov-report=html -ra` | `0` | **67 tests passed**; **100% global** del paquete `app`. Reporte HTML: `api/htmlcov/index.html`. |

**Cobertura reportada:** `233/233` sentencias ejecutadas cubiertas (**100%**);
`28/28` ramas cubiertas (**100%**, ninguna parcial). Método: pytest-cov sobre
`app`, Coverage.py con medición de ramas. El diff de este paso solo modifica
tests, por lo que no hay nuevas sentencias de producción que medir por separado;
la cobertura del paquete bajo las pruebas nuevas supera el umbral del `85%`.

La ejecución reportó `67 passed, 129 warnings in 3.82s`. Las advertencias
visibles corresponden a Starlette TestClient (`httpx` deprecado) y
`FastAPI.on_event`; ninguna se suprimió.

## Fallos, pendientes y pruebas propuestas

- **Fallos:** ninguno en la suite final.
- **Pendientes de validación:** no se probó el backend-health contra un servicio
  real ni se validaron disponibilidad, TLS o credenciales del servicio
  externo; los tests usan exclusivamente dobles locales. No se ejecutó un
  escaneo de dependencias en este paso.
- **Pruebas propuestas:** realizar un smoke test de backend-health en un
  entorno de integración autorizado si se requiere validar conectividad real;
  no es condición para los resultados locales de esta matriz.
