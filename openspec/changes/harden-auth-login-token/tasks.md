# Tasks

## 1. Caracterización del comportamiento actual (antes de cualquier cambio funcional)

- [x] 1.1 Agregar en `auth/src/test/java/com/bcp/workshop/auth/AuthResourceTest.java` una prueba que fije que un login válido hoy devuelve `200` con un `token` Base64 decodificable a `username|role|expiry|secret` y `expiresIn` siempre `3600`; verificar con `python tools/lab.py test auth` (ejecuta `mvn verify` en `auth/`) en verde, sin tocar código de producción.
- [x] 1.2 Agregar una prueba que fije que hoy una solicitud **sin** el campo `client` (o vacío) igual devuelve `200` (comportamiento actual, sin validación); verificar con `python tools/lab.py test auth` en verde.
- [x] 1.3 Agregar pruebas que fijen `400` cuando falta `username` o `password`, `401` ante credenciales que no matchean ningún registro (incluyendo el mensaje actual con el username recibido), y la forma completa de la respuesta exitosa actual incluido el campo `debug`; verificar con `python tools/lab.py test auth` en verde.
- [x] 1.4 Ejecutar `python tools/lab.py test auth` con el reporte de JaCoCo (`auth/target/site/jacoco/index.html`) y registrar la cobertura base de `AuthResource`/`LegacyTokenUtil` antes de modificar nada, como punto de comparación para los grupos siguientes.
  - Comando: `$env:QUARKUS_HTTP_TEST_PORT='0'; python tools/lab.py test auth` desde la raíz (el puerto de prueba 8081 estaba ocupado por otro proceso local; el override solo cambia el puerto). Resultado: BUILD SUCCESS, 9 tests, 0 fallos, 0 errores.
  - Cobertura base (JaCoCo, instrucciones / ramas cubiertas): `AuthResource` 102/129 (79%) y 11/14; `LegacyTokenUtil` 16/16 (100%) y 0/0; total del paquete 224/257 (87%) y 16/22.

## 2. Validación del campo `client` en el login

- [ ] 2.1 Modificar `AuthResource.login` para rechazar con `400` una solicitud sin `client` válido (mismo formato de cuerpo de error que los `400` existentes), sin tocar aún `LegacyTokenUtil`; verificar que la prueba de caracterización 1.2 se actualiza para reflejar el nuevo `400` y que `python tools/lab.py test auth` pasa en verde.
- [ ] 2.2 Agregar una prueba que confirme que un login con `client` válido (p. ej. `"angular-workshop"`) sigue devolviendo `200` sin cambios en la forma de la respuesta; verificar con `python tools/lab.py test auth`.

## 3. Externalización del secreto de firma por perfil

- [ ] 3.1 Agregar en `auth/src/main/resources/application.properties` la variable `AUTH_TOKEN_SECRET` con un valor por defecto documentado como exclusivo de laboratorio, limitado a los perfiles `%dev`/`%test`, y sin default en `%prod`, siguiendo el patrón de perfiles ya usado en el archivo (`%prod.quarkus.http.host=...`).
- [ ] 3.2 Hacer que `LegacyTokenUtil` (o su reemplazo) lea el secreto desde `AUTH_TOKEN_SECRET` en vez de la constante `WORKSHOP_SECRET_2026`, conservando por ahora el formato Base64 existente (sin firma todavía), para aislar el riesgo de configuración del riesgo de cambiar el formato del token; verificar que las pruebas de los grupos 1 y 2 siguen en verde con `python tools/lab.py test auth`.
- [ ] 3.3 Agregar una prueba que falle el arranque (o rechace explícitamente la emisión de tokens) cuando el servicio corre fuera de los perfiles de laboratorio/test sin `AUTH_TOKEN_SECRET` configurado; verificar con `python tools/lab.py test auth`.

## 4. Reemplazo del token por una versión firmada con claims mínimos

- [ ] 4.1 Reemplazar la construcción del token en `LegacyTokenUtil` por una serialización firmada (HMAC-SHA256 vía `javax.crypto.Mac`, sin dependencia nueva) con claims `sub`, `client`, `iat` y `exp`, usando el secreto de `AUTH_TOKEN_SECRET` del grupo 3; verificar con una prueba que decodifica el token emitido y confirma la presencia y el valor de los cuatro claims.
- [ ] 4.2 Calcular `expiresIn` en `AuthResource.login` a partir de `exp - iat` de los mismos claims recién construidos, eliminando la constante `3600` desconectada; verificar con una prueba que compara `expiresIn` contra `exp - iat` del token emitido dentro de una tolerancia documentada en la propia prueba.
- [ ] 4.3 Actualizar las pruebas de caracterización de 1.1 para reflejar el nuevo formato de token como comportamiento esperado (ya no Base64 plano), dejando explícito en el test o en un comentario que el formato anterior se reemplaza deliberadamente; verificar con `python tools/lab.py test auth`.
- [ ] 4.4 Agregar una prueba que confirme que la ruta, el método y la forma de la respuesta exitosa (`token`, `expiresIn`, `user` con `username`/`displayName`/`role`, y `debug`) y de los errores (`400`/`401`/`500`) no cambiaron pese al nuevo formato de token; verificar con `python tools/lab.py test auth`.

## 5. Firma verificable y ausencia de registros sensibles

- [ ] 5.1 Agregar una prueba que verifique la firma del token emitido con el secreto configurado y confirme que es válida y que los claims no fueron alterados.
- [ ] 5.2 Agregar una prueba que altere un byte del token emitido (payload o firma) y confirme que la verificación con el secreto configurado lo rechaza.
- [ ] 5.3 Revisar `AuthResource`/`LegacyTokenUtil` y confirmar (con una prueba o inspección reproducible) que ningún log generado por un login válido contiene el token completo ni el valor de `AUTH_TOKEN_SECRET`; si existe algún `printStackTrace`/log que podría incluirlos, ajustarlo para que no lo haga.

## 6. Verificación final de cobertura y regresión completa

- [ ] 6.1 Ejecutar `python tools/lab.py test auth` completo y confirmar que todas las pruebas de los grupos 1 a 5 pasan juntas, sin regresiones entre ellas.
- [ ] 6.2 Revisar el reporte de JaCoCo (`auth/target/site/jacoco/index.html`) y confirmar que el código modificado (`AuthResource`, `LegacyTokenUtil`, configuración de secreto) alcanza cobertura ≥85%, comparando contra la base registrada en 1.4.

## Workflow follow-up

- Ejecutar `openspec validate "harden-auth-login-token"` antes de iniciar la fase de aplicación (apply).
- La implementación de este checklist corresponde a una fase `apply` separada; esta tarea no la ejecuta.
- Archivar el cambio solo después de que el Issue #37 (`HU-01`) se dé por resuelto con evidencia (pruebas en verde, cobertura registrada) y con revisión humana, conforme al contrato de `auth` en `AGENTS.md`.
