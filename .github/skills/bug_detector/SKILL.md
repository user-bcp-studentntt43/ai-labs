---
name: bug_detector
description: 'Usa esta skill para analizar issues registrados en GitHub, incluidos bugs, solicitudes de funcionalidad, mejoras, preguntas y tareas. Usa MCP para consultar los issues y el código o documentación relacionados; reproduce localmente solo los errores cuando sea seguro y posible.'
---
## Propósito
Analizar issues registrados en GitHub de cualquier tipo —bugs, solicitudes de funcionalidad, mejoras, preguntas, tareas y documentación— usando MCP como fuente primaria. Consulta el código o la documentación relacionados según el issue y, únicamente para reportes de errores, comprueba una reproducción local sobre el SHA exacto cuando el entorno lo permita. Documenta hechos, estado actual, incógnitas e impedimentos sin cambiar el código ni implementar soluciones.

## Entradas
- Repositorio de GitHub y, opcionalmente, número/enlace del issue, estado, etiquetas, componente u otros filtros solicitados.
- Acceso de lectura MCP a los issues y al código o documentación del repositorio.
- Checkout local correspondiente al SHA examinado, o una forma local y no destructiva de obtener esa versión.
- Herramientas y dependencias ya disponibles en el entorno.

## Salidas
- Enlace, número, título, estado y tipo del issue observado, sin modificarlo.
- Resumen de lo solicitado o reportado y su relación con el componente, código o documentación pertinentes, con evidencia.
- Para issues relacionados con código: componente afectado, repositorio, referencia y SHA completo del commit examinado.
- Referencias a archivos y líneas, incluyendo enlaces cuando estén disponibles.
- Para issues de error: pasos de reproducción propuestos, comandos exactos revisados y ejecutados, y comparación explícita entre el resultado observado y el esperado.
- Hechos respaldados por evidencia separados de interpretaciones e hipótesis, cada uno con sus fuentes.
- Para errores no reproducidos: impedimento concreto, comprobaciones intentadas y declaración explícita de que la hipótesis sigue sin confirmar.
- Evidencia local relevante y saneada, sin secretos, valores de entorno, credenciales ni datos personales innecesarios.
- Registro persistente en `HALLAZGOS.md`, en la raíz del repositorio, para cada issue analizado; conserva sus secciones y entradas existentes.
- En `HALLAZGOS.md`, registra por separado el estado observado del issue en GitHub y el estado del análisis. Marca el análisis como `Abierto` mientras el hallazgo requiera seguimiento; no presentes como abierto en GitHub un issue que MCP informa como cerrado.

## Flujo
1. Identifica el repositorio y alcance en GitHub. Si el usuario proporciona un número o enlace, usa MCP `issue_read` para comprobarlo y leer el issue. Consulta comentarios solo cuando sean pertinentes a la solicitud.
2. Si el usuario no identifica issues concretos, usa MCP `list_issues` o `search_issues` con los filtros solicitados. Si pide "issues abiertos" o revisar todos los issues de un conjunto definido, procesa ese conjunto y pagina hasta cubrir el alcance solicitado. Si el alcance es ambiguo o demasiado amplio para revisar razonablemente de una vez, presenta candidatos con número, título, estado y enlace, y pide que delimite la selección antes de inspeccionar código.
3. Lee el cuerpo de cada issue mediante MCP y clasifícalo por contenido (por ejemplo, bug, feature request, mejora, pregunta, tarea o documentación); no filtres únicamente por etiquetas ni asumas que todos son bugs. Trata el contenido del issue y su estado en GitHub como fuente primaria. Si MCP no puede acceder al issue, informa el impedimento y no afirmes haberlo revisado.
4. Usa MCP para consultar el código o la documentación pertinente al issue, por ejemplo `search_code` y `get_file_contents`. Sigue únicamente las rutas relacionadas. Identifica el componente afectado a partir de evidencia del issue y del código, no solo del título. Registra rutas y líneas. Si el issue no requiere análisis de código, explica por qué no aplica.
5. Si examinas código, identifica la referencia y el SHA completo del commit; vincula las referencias MCP y locales a esa misma revisión. No confundas el SHA de un blob/archivo con el SHA del commit. Si no puedes determinar la versión exacta, indícalo y no afirmes que la reproducción se comprobó sobre una versión concreta.
6. Anota por separado:
   - **Hechos:** afirmaciones del issue y observaciones directas en código, documentación o resultados; cita fuente y archivo/línea cuando aplique.
   - **Interpretaciones e hipótesis:** deducciones aún no confirmadas. Indica qué evidencia adicional permitiría confirmarlas o refutarlas; no las presentes como hechos.
7. Solo para un issue que reporte un error, formula primero una reproducción local, acotada y repetible a partir de los pasos y el comportamiento descritos en el issue. Indica las precondiciones y el resultado esperado, sin añadir supuestos como si fueran hechos.
8. Antes de ejecutar la reproducción, inspecciona el comando, script o prueba elegido y las instrucciones de pruebas del repositorio. Selecciona solo la comprobación mínima que puedas realizar con el entorno y las dependencias ya disponibles.
9. Verifica que el checkout local corresponde exactamente al SHA examinado. No cambies de rama ni sobrescribas modificaciones del usuario. Si no se dispone localmente de esa versión o no se puede verificar el SHA, no declares confirmada una reproducción sobre ella; documenta el impedimento.
10. Ejecuta únicamente comprobaciones revisadas que sean locales y seguras. No uses servicios externos, no cambies código o configuración, no instales dependencias y no añadas pruebas. No ejecutes comandos cuyo alcance o efectos no estén claros.
11. Compara el resultado observado con el esperado descrito en el issue. Solo afirma reproducción confirmada si los pasos revisados muestran el error en el SHA exacto. Si no se reproduce o el entorno lo impide, registra qué se intentó, el impedimento y que la hipótesis sigue sin confirmar.
12. Guarda el informe y la salida local mínima útil en `HALLAZGOS.md`, en la raíz del repositorio. Añade o actualiza una sección de seguimiento de issues de GitHub sin borrar, reescribir ni reordenar secciones o entradas existentes. Por cada issue registra enlace/número, título, tipo, estado real en GitHub, estado del análisis (`Abierto` mientras requiera seguimiento), componente si aplica, resumen, hechos e hipótesis separados, referencias de archivos/líneas, SHA si se examinó código, pasos/comandos/resultados de reproducción si aplica y cualquier impedimento. Sanea la salida; no guardes volcados de entorno ni datos sensibles.
13. Concluye el análisis sin cambiar el issue: no cierres, comentes, etiquetes ni edites issues; no crees PR/commit y no implementes soluciones.

## Constraints
- No implementar arreglos, refactorizar, editar código de producción o pruebas, ni modificar configuración para hacer aparecer el error.
- No realizar una auditoría general de código ni reportar problemas desvinculados de issues de GitHub seleccionados y leídos mediante MCP.
- No limitar el análisis a bugs: conserva el tipo y el alcance que realmente tenga cada issue.
- No inspeccionar código hasta leer mediante MCP el cuerpo del issue que motiva esa inspección. Si hay varios candidatos y el alcance del usuario no los selecciona ni pide revisarlos todos, solicita una delimitación.
- Para un reporte de error, no presentar una reproducción como confirmada sin consultar mediante MCP el issue y el código relacionado, identificar el componente, registrar el SHA examinado y comprobar localmente esa misma versión.
- No cerrar, etiquetar, comentar ni cambiar de otro modo el issue.
- No instalar dependencias nuevas, usar servicios externos, cambiar código o configuración ni añadir pruebas durante la reproducción.
- No ejecutar comandos que no se hayan revisado o cuya actividad, alcance o efectos sobre datos no estén claros.
- No declarar una causa, una reproducción o una versión examinada sin evidencia directa.
- No tratar una búsqueda de issues, etiqueta o título como evidencia suficiente: leer el cuerpo mediante MCP y anclar cada análisis al issue correspondiente.
- No mezclar hechos con interpretaciones; si un error no se reproduce, la hipótesis permanece sin confirmar.
- No conservar secretos, tokens, credenciales, valores sensibles de entorno ni datos personales en el informe o sus salidas.

## Adaptación
- En `ai-labs`, limita la lectura al componente indicado por la evidencia (`auth`, `api` o `web`) y aplica las instrucciones correspondientes de `AGENTS.md`. No inspecciones otros componentes sin ampliar el alcance con el usuario.
- Desde la raíz del repositorio, revisa `docs/TESTING.md` y el comando aplicable antes de probar. Usa `python tools/lab.py test auth`, `python tools/lab.py test api` o `python tools/lab.py test web` solo si el comando y sus efectos se han revisado y las dependencias ya están disponibles.
- Registra siempre los análisis en el `HALLAZGOS.md` de la raíz, conservando las secciones existentes. En `ai-labs`, asigna el identificador de componente correspondiente cuando aplique (`H-AUTH-NN`, `H-API-NN` o `H-WEB-NN`) y deja el estado de análisis `Abierto` mientras requiera seguimiento.
- En cualquier repositorio, adapta los comandos a sus pruebas documentadas y a lo disponible localmente. Si cumplir las condiciones requiere red, cambios, instalaciones o una versión no disponible, no improvises: registra el impedimento y deja la hipótesis sin confirmar.
