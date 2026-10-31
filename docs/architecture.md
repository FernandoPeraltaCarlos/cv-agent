# Decisiones de arquitectura

El servicio representa un único perfil, con un modelo local y un corpus pequeño. La API pública implementa el subconjunto de texto de Open Responses; Ollama es un detalle interno sin credenciales públicas ni puerto publicado. Un gateway HAProxy mínimo conecta el puerto de loopback del host con FastAPI: tanto FastAPI como Ollama permanecen en una red interna sin ruta por defecto. Se verificó que el intento de conexión directa de FastAPI a una IP externa devuelve `Network unreachable`.

## Modelo pequeño y respuestas extractivas

El modelo seleccionado es `qwen2.5:1.5b` Q4_K_M, archivo de 986.061.892 bytes. El manifiesto evaluado tiene digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. Se comparó con 0.5B en el corpus ampliado: el modelo pequeño superó el umbral básico, pero confundió una pregunta de precios de plugins con un listado general de plataformas. La elección de 1.5B mejora esa selección a cambio de más memoria y latencia, manteniendo 2 GiB como límite de Ollama. No se afirma haber comparado todos los modelos existentes. El nombre comercial no es una medida exacta de memoria de ejecución. Los informes guardan digest, tamaño cargado, tiempos y versión del perfil.

En lugar de generar libremente párrafos, el modelo devuelve hasta tres IDs mediante un esquema JSON cuyos valores permitidos son los hechos recuperados. La aplicación vuelve a validar esos IDs y compone el texto con evidencia revisada, en español o inglés. Las referencias permanecen internas y no se añaden al texto público. La prosa libre del modelo nunca se entrega al visitante.

Esta decisión permite usar un modelo menor y evita afirmaciones o enlaces inventados en la respuesta renderizada. Tiene un coste: el estilo es más repetitivo y el modelo aún puede seleccionar un hecho poco pertinente. La evaluación mide pertinencia, abstención y seguimiento; la evidencia aprobada puede contener errores humanos y debe revisarse. No se presenta esta solución como inmune a prompt injection.

## RAG sin servidor vectorial

La recuperación usa BM25 local, etiquetas bilingües, filtros por tipo de evidencia y restricción de entidad para empresas y referencias conversacionales. Este corpus tiene decenas de hechos; mantener otro modelo de embeddings o una base vectorial añadiría memoria y operación. La interfaz de recuperación permite sustituir esta capa si aumentan los documentos o las paráfrasis no se recuperan bien. No se atribuye búsqueda semántica vectorial a la versión actual.

Las preguntas generales sobre empresas recuperan directamente el hecho revisado `career-overview`, independientemente de muletillas como «ok», una reformulación como «no sabes» o una empresa discutida en el turno anterior. Los calificadores de empresa, tecnología, negación y actualidad se conservan para evitar sustituir una pregunta concreta por la lista general. Esta ruta limita la evidencia recuperada; el modelo sigue seleccionando los IDs y la aplicación mantiene la misma frontera de renderizado.

Los datos son un perfil JSON validado y versionado. Las fuentes brutas se guardan fuera del repositorio en `data/incoming/` y nunca se indexan automáticamente. No se compila LaTeX, navegan URLs aportadas por visitantes ni ejecutan instrucciones de documentos. `prepare-source` únicamente prepara material para revisión humana.

`data/knowledge.md` es la fuente consolidada legible, elaborada a partir de ambos CV, el sitio profesional y la sección de experiencia del MHTML de LinkedIn facilitado por Fernando. Su versión estructurada es `data/profile.json`. `data/career.json` conserva los intervalos revisados y las diferencias entre fuentes: prevalecen las fechas coincidentes de los CV y el sitio frente a discrepancias de LinkedIn. La extracción del MHTML usa UTF-8 y excluye perfiles de terceros, anuncios y mensajes.

`scripts/build_knowledge.py` regenera la fuente legible y los hechos de duración desde esa cronología revisada. El cálculo une meses naturales, con extremos incluidos; un mes compartido por varios trabajos solo cuenta una vez y las actividades abiertas se limitan al mes de revisión. Así se obtiene una estimación de unos siete años desde 2019, incluyendo DevStore MX. No equivale a medir días trabajados ni años de uso continuo de cada tecnología. La recuperación de preguntas sobre duración se restringe a esos hechos y no convierte la experiencia total en años con una habilidad o empresa sin evidencia.

## Contexto y API

El visitante puede reenviar mensajes mediante `input` o usar `previous_response_id` con respuestas almacenadas. Cada cadena contiene su historial, se vincula al hash de la API key y tiene IDs aleatorios de 128 bits. No existe historial global compartido. El servicio no dispone de identidad de usuario de Banorte: la confidencialidad entre visitantes que comparten una clave depende también de que Banorte no exponga IDs ajenos.

La recuperación utiliza la última pregunta del usuario y el tema explícito más reciente dentro del historial acotado, de modo que varias preguntas de seguimiento conservan la empresa o proyecto. Una empresa nueva cambia el tema; expresiones como «en general» permiten volver al perfil global. Las afirmaciones de mensajes assistant enviados por el cliente no son evidencia. Los mensajes system/developer y `instructions` se aceptan a nivel de transporte, pero no alteran la política ni se transmiten al selector como instrucciones.

El historial tiene un límite de caracteres independiente del contexto del modelo: no se reenvía toda la conversación a Ollama. Con `truncation=disabled` se rechazan historiales demasiado largos; con `auto` se eliminan mensajes antiguos, preservando orden y última pregunta. SQLite guarda cadenas con TTL de 24 horas y un máximo de 2000 respuestas. La caducidad se limpia en lecturas, escrituras y arranque; es retención lógica, no borrado forense garantizado de WAL/copias de seguridad.

Las respuestas SSE emiten created/in_progress, heartbeats y, una vez validado el resultado, el ciclo completo de item, parte, deltas y evento terminal. No son tokens sin verificar enviados directamente desde Ollama. Una desconexión cancela la petición al motor y libera el turno; el motor puede tardar brevemente en detener el trabajo ya iniciado.

## Seguridad y operación

- Solo datos profesionales aprobados entran en el contexto. La clave de API se lee fuera del prompt, se compara con tiempo constante y no se registra.
- Los patrones de ataque son una ayuda para rechazar abuso frecuente, no una frontera de seguridad. La frontera de salida es el conjunto de textos aprobados y los permisos reales de herramientas: el agente no tiene terminal, filesystem arbitrario, navegación ni herramientas externas.
- Cuerpo de 32 KiB, pregunta de 2000 caracteres, un turno de generación, 20 peticiones por minuto por instancia, timeout del modelo y cancelación al desconectar. Un único worker mantiene consistentes los límites en memoria.
- Contenedores sin privilegios, sin capabilities, filesystem de solo lectura, volúmenes mínimos, sin socket Docker y red interna sin egress durante operación. Solo se abre egress de Ollama al descargar modelos con la configuración bootstrap.
- El uso de memoria se limita a 256 MiB para FastAPI, 2 GiB para Ollama y 64 MiB para el gateway; tres CPU para inferencia. El gateway no monta el perfil, las conversaciones ni secretos y solo tiene un upstream fijo. No se incorporan Redis, colas, Kubernetes, MCP ni agentes adicionales porque no resuelven una necesidad actual.
- Métricas protegidas: peticiones, errores, decisiones, consumo de tokens internos, duración acumulada y ocupación. No se guardan conversaciones en logs. SQLite sí guarda el historial cuando `store=true`.
- Los resultados de pruebas no autorizan actualizar automáticamente el corpus ni desplegar una versión distinta del modelo.

## Referencias del contrato y modelo

- https://www.openresponses.org/specification
- https://www.openresponses.org/reference
- https://www.openresponses.org/compliance
- https://ollama.com/library/qwen2.5:1.5b
- https://docs.ollama.com/capabilities/structured-outputs
- https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

Se incluye el esquema oficial fechado 2026-04-24 para probar las respuestas y los eventos emitidos sin depender de una especificación que cambie durante la ejecución.

## Docker rootless en este servidor

Se usa un daemon rootless exclusivo del proyecto, con socket, imágenes y estado bajo `.runtime/`. Los comandos de `scripts/docker-rootless.sh` seleccionan ese socket explícitamente; el daemon y contexto de Docker existentes no se modifican. El servidor dispone de subuid/subgid para `dev` y cgroup v2; se comprobaron los límites efectivos de memoria y CPU en los contenedores.

Una particularidad de los bind mounts rootless hace que el archivo 0600 del host se vea como UID 0 en el contenedor. El bootstrap mantiene la clave canónica 0600 y crea una copia de lectura 0444 en `.secrets/`, directorio 0700 privado del propietario, para montarla en el contenedor sin privilegios. Esa copia no se comparte con Ollama ni el gateway. La rotación requiere regenerarla y recrear la API.

La imagen de Ollama se construye con los binarios y bibliotecas de CPU de la distribución oficial, validando su SHA-256 y excluyendo CUDA/Vulkan. Las imágenes base y el gateway se fijan por digest; el modelo evaluado se registra en `models.lock.json` y en los informes. Los paquetes del sistema de Debian se resuelven al construir; para reproducibilidad binaria completa se deben conservar las imágenes finales por digest.
