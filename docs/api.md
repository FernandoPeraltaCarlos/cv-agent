# Contrato de conexión

URL base para Banorte: `https://agent-cv.fernandoperalta.xyz/v1`.
Recurso completo: `POST https://agent-cv.fernandoperalta.xyz/v1/responses`.
Autenticación: `Authorization: Bearer <contenido de .secrets/api_key>`.
Modelo público: `cv-fernando`. Si Banorte envía otra etiqueta de modelo, se acepta como alias del mismo agente; la respuesta identifica siempre `cv-fernando`. Esto no permite elegir otros modelos ni proveedores.

## Crear respuesta

```json
{
  "model": "cv-fernando",
  "input": "¿Qué extensión desarrolló en HSBC?",
  "stream": false,
  "store": true
}
```

También se acepta `input` como array de mensajes de texto `user`/`assistant`, con contenido string o partes `input_text`/`output_text`. Se puede reenviar el item assistant de una respuesta anterior, incluido `phase: final_answer`. La última intervención debe ser de usuario y tener contenido.

```json
{
  "input": "¿Y cómo ayudó al equipo?",
  "previous_response_id": "resp_<id de la respuesta anterior>",
  "stream": true
}
```

Si se usa `previous_response_id`, enviar solo los mensajes nuevos; reenviar todo el historial además del ID duplicaría el contexto. `store=false` impide recuperar o continuar esa respuesta por ID: el cliente debe reenviar el historial en `input`. No existe continuación efímera por ID para respuestas no almacenadas.

El objeto devuelto sigue `ResponseResource`, con `output` compuesto por un mensaje assistant y una parte `output_text`. El texto responde directamente, sin encabezado de fuentes ni referencias a archivos; las anotaciones permanecen vacías. La procedencia se conserva internamente en los hechos y en los informes de evaluación. Las decisiones de falta de información, privacidad o fuera de alcance son respuestas de conversación normales con HTTP 200. Los saludos y preguntas de disponibilidad, como «hola, ¿estás ahí?», reciben una presentación breve sin llamar al modelo; una pregunta profesional que acompañe al saludo sigue el flujo de consulta del perfil.

## Streaming y límites

`stream=true` devuelve SSE (`text/event-stream`): `response.created`, `response.in_progress`, heartbeats, `response.output_item.added`, `response.content_part.added`, `response.output_text.delta`, `response.output_text.done`, `response.content_part.done`, `response.output_item.done`, y `response.completed` o `response.incomplete`. Fallos después de abrir el stream terminan con `response.failed`.

La respuesta se valida antes del primer delta; por eso streaming no garantiza texto inmediato. La configuración del proxy debe permitir SSE y una espera de al menos 50 segundos.

`max_output_tokens` se aplica como un techo conservador de bytes UTF-8 del texto renderizado, que garantiza no superar ese número de tokens para tokenizadores de bytes, pero puede cortar antes de lo necesario. Si se alcanza, se devuelve estado `incomplete` y motivo `max_output_tokens`. Para respuestas completas, omitir el campo o usar al menos 2048. No se contabilizan como tokens del modelo los textos curados que la aplicación concatena: `usage` informa el consumo real del selector interno, no una tokenización exacta del texto público. Esta es una limitación explícita del adaptador extractivo.

`temperature`, `top_p`, `reasoning`, `parallel_tool_calls` e instrucciones del cliente no modifican la política del servicio: el selector usa temperatura cero y razonamiento desactivado. `metadata` se valida y se refleja en la respuesta. `stream_options` se acepta sin efectos; no se añaden campos de obfuscación. Solo se soporta formato de salida `text`.

No se soportan imágenes, vídeos, audio, archivos, herramientas externas, background, WebSocket, compaction ni salida JSON del usuario. Se devuelve HTTP 400 al solicitarlos. La compatibilidad declarada es con el subconjunto de texto, no con toda la suite multimodal/agéntica de Open Responses.

## Otras rutas

| Ruta | Autenticación | Uso |
| --- | --- | --- |
| `GET /healthz` | No | Proceso vivo; no implica que el modelo/perfil estén listos. |
| `GET /readyz` | Sí | Comprueba aprobación del perfil y disponibilidad del modelo. |
| `GET /v1/models` | Sí | Enumera `cv-fernando`. |
| `GET /v1/models/cv-fernando` | Sí | Consulta el modelo público. |
| `GET /v1/responses/{id}` | Sí | Recupera una respuesta almacenada no caducada. |
| `DELETE /v1/responses/{id}` | Sí | Elimina una respuesta almacenada. |
| `GET /metrics` | Sí | Contadores y duración acumulada en formato Prometheus. |

Errores: 400 entrada no soportada, 401 credencial inválida, 404 respuesta ausente/caducada, 413 cuerpo excesivo, 415 Content-Type incorrecto, 429 frecuencia/concurrencia, 502 salida inválida o motor fallido, 503 perfil/modelo no disponible y 504 timeout. El cuerpo usa `error` con `type`, `code`, `message` y `param`. No incluye trazas ni entradas del usuario.

El servicio requiere un único proceso Uvicorn. Escalar a varios workers o réplicas exige trasladar los límites globales a un almacén compartido y coordinar la capacidad del motor.

Si el conector de Banorte realiza peticiones directamente desde el navegador, configura `ALLOWED_ORIGINS` como un array JSON con el origen HTTPS exacto de ese chat. Por defecto no se habilita CORS; no se permite `*`. Un preflight permitido no sustituye la API key. La conexión entre servidores no requiere CORS.
