# Evaluaciones

Los JSON generados aquí están excluidos de Git. Pueden incluir ejemplos de tu trayectoria y deben revisarse antes de compartirlos.

`agent-cv evaluate` guarda el modelo, digest, memoria cargada, hash del perfil, hash de implementación/casos, decisiones y referencias por caso. No usa mocks. `tests/` valida el transporte y seguridad con un backend controlado; son comprobaciones distintas.

Un informe con `gate_passed=false` no constituye aprobación del modelo. Los informes iniciales del borrador se conservan como historial; el perfil activo revisado es `2026-10-31.consolidated-v3`, basado en ambos LaTeX, el portafolio y la experiencia del MHTML de LinkedIn. Cualquier cambio en fuentes, reglas, recuperación o modelo exige volver a evaluar la parte afectada.

La comparación de modelos se realiza secuencialmente para evitar que compitan por CPU o provoquen recargas entre casos. Se excluye un calentamiento de los percentiles; los tiempos incluyen recuperación y selección, sin tráfico de Banorte ni TLS. El informe conserva también el tiempo de esa primera llamada, que no debe interpretarse como arranque en frío si el modelo ya estaba cargado.

La evaluación ampliada contiene **126 casos**. `candidate-1.5b-evaluation.json` conserva las salidas originales del modelo 1.5B: el criterio anterior de IDs únicos marcó 124/126, aunque las dos respuestas restantes eran resúmenes profesionales válidos de los hechos nuevos. Se revisaron las expectativas de las preguntas amplias de perfil para aceptar `summary` o `professional-focus`; la definición general de DevStore MX también acepta el hecho revisado de agencia o fundador. Las preguntas concretas conservan sus hechos exigidos.

`docker-evaluation.json` registra **126/126** al comprobar de nuevo esas salidas reales contra las expectativas revisadas, sin modificar las respuestas ni volver a inferir. Conserva el hash del conjunto original y añade `expectation_review` con el hash revisado, los casos afectados y el informe original. Las preguntas y el historial son idénticos. El cambio posterior del valor predeterminado en configuración a 1.5B no altera el modelo evaluado: la comparación ya lo seleccionaba explícitamente por variable de entorno.

`comparison-0.5b-v3.json` conserva la comparación original y `comparison-0.5b-rescored.json` aplica la misma revisión de expectativas: **125/126**. Su fallo real fue elegir la lista general de plataformas para una pregunta sobre el cálculo de precios del plugin WooCommerce. 1.5B respondió con el hecho del plugin. La latencia p95 cálida fue 6,299 s para 0.5B y 12,784 s para 1.5B; la mediana de 1.5B fue 6,332 s. El aumento de calidad se acepta a cambio de más memoria y latencia, conservando el límite de 2 GiB. Estos tiempos incluyen recuperación y selección, no la red pública.

Las colecciones se utilizaron durante el desarrollo y la revisión; no constituyen un holdout estadístico ni demuestran generalización universal o inmunidad a ataques. Los textos renderizados y la procedencia interna de los hechos permiten revisar los resultados por contenido, además de sus IDs.

`public-verification.json` comprueba sobre HTTPS el perfil y modelo activos, el saludo de disponibilidad, siete años desde 2019, seguimientos de tickets y duración en HSBC, DevStore MX, ArkusNexus, el plugin de precios, abstención sobre años con Rust, rechazo de una clave incorrecta y SSE en inglés. Verifica que no aparezcan fuentes, nombres de archivos o la clave y que la credencial original no haya cambiado. Las cinco plantillas de `openresponses.json` comprueban el contrato de texto del protocolo sobre el dominio público, no el seguimiento de instrucciones de propósito general.

Las pruebas unitarias y de API completaron inicialmente **67 casos**; usan un selector controlado y complementan la evaluación con el modelo real. Se eliminaron los modelos de prueba anteriores tanto del volumen Docker como de la caché local, conservando sus informes. La lista instalada en Docker contiene únicamente `qwen2.5:1.5b`; el daemon local temporal de limpieza quedó detenido.

## Regresión de preguntas sobre empresas

Se reprodujeron por HTTPS los tres ejemplos «ok, donde ha trabajado?», «no sabes donde ha trabajado?» y «cuales son las empresas donde ha trabajado?». `employer-regression-before.json` conserva las respuestas incorrectas anteriores. El problema estaba en la recuperación: los términos conversacionales hacían que se descartara el identificador de historial y se recuperaran hechos irrelevantes.

La corrección reconoce la consulta general de historial y recupera el hecho completo `career-overview`. Los calificadores se conservan y deben aparecer en la evidencia: una palabra como «using» no permite responder con una empresa que no documente la tecnología preguntada. Se añadieron 23 casos a `eval/employers.json`, por lo que la colección completa contiene 149 casos. La corrección se verifica con las **91 pruebas unitarias y de API** y una regresión específica de **47 casos con el modelo real**: los 23 nuevos y 24 existentes de contexto, duración, empresas, plugins, abstención y seguridad. El informe de esta ejecución es `employer-regression-evaluation.json`; la ejecución anterior de 126 casos en `docker-evaluation.json` corresponde a la implementación anterior y no se presenta como una ejecución completa de los 149 actuales.

`employer-regression-public.json` verifica los tres textos exactos por HTTPS, tanto de forma independiente como enlazados por `previous_response_id`, un historial previo con rechazo del asistente y el paso desde una empresa concreta a la lista global mediante SSE. Incluye abstención para Banorte y empleo con Rust y comprueba que la API key se conserva. No se cambia el modelo ni el perfil.
