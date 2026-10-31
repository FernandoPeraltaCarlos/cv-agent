# Agent CV — Fernando Peralta

Agente local de perfil profesional con FastAPI, Ollama y API de texto compatible con Open Responses. El chat lo aporta Banorte; este proyecto entrega el backend autenticado y reproducible.

**Servicio activo:** `https://agent-cv.fernandoperalta.xyz`. **URL base:** `https://agent-cv.fernandoperalta.xyz/v1`. **Ruta:** `/v1/responses`.

## Estado y fuentes

El perfil revisado contiene **56 hechos** procedentes de los dos CV en LaTeX de `shared/agentes/agent-cv/` y una selección del portafolio público. Conserva las fuentes y sus hashes en `data/sources.lock.json`. No incluye teléfono, correo, domicilio ni facturación de clientes. Incluye la sección de experiencia del MHTML de LinkedIn facilitado por Fernando. Los CV prevalecen para niveles de idiomas y estado de estudios; las diferencias de fechas con LinkedIn se resuelven en `data/career.json`. Los productos personales se distinguen del empleo comercial. `data/knowledge.md` reúne la fuente consolidada legible y `data/profile.json` es su versión estructurada para la API: el agente nunca recibe los HTML brutos.

Se comparó el modelo más pequeño primero. Un modelo no se considera válido por arrancar o por pasar pruebas con mocks: debe superar la evaluación real de selección de evidencia, abstención y contexto. Los informes locales quedan en `reports/`.

El modelo seleccionado es **Qwen2.5 1.5B Q4_K_M**, de unos 986 MB. Con el corpus ampliado, el modelo de 0.5B confundió una pregunta sobre precios de un plugin con una lista general de tecnologías; se eligió 1.5B para mejorar la selección sin aumentar el límite de 2 GiB de Ollama. La evaluación ampliada anterior cubrió **126 casos** con el modelo real. Tras corregir las preguntas sobre empresas, el conjunto completo contiene **149 casos** y se ejecuta una regresión específica de 47 casos sobre la recuperación afectada. La API está publicada por HTTPS, con el perfil revisado activo y `ALLOW_DRAFT_PROFILE=false`; también responde localmente en `http://127.0.0.1:8011/v1`. Se verificaron 91 pruebas unitarias y de API, cinco plantillas oficiales de texto de Open Responses y comprobaciones públicas de contexto entre turnos, cambio de tema, autenticación y SSE. Las plantillas verifican el contrato del protocolo; no implican que el agente obedezca instrucciones ajenas al perfil.

## Arranque local sin permisos de Docker

Requiere Linux x86_64, Python >=3.12, curl, tar y zstd. Para preparar fuentes PDF se necesita `pdftotext`; LaTeX nunca se compila.

```bash
cd /home/dev/projects/agent-cv
bash scripts/bootstrap-local.sh
bash scripts/run-model-local.sh
```

En otra terminal, descarga el modelo configurado (la descarga requiere Internet):

```bash
cd /home/dev/projects/agent-cv
OLLAMA_HOST=127.0.0.1:11435 .runtime/ollama/bin/ollama pull qwen2.5:1.5b
ALLOW_DRAFT_PROFILE=true OLLAMA_URL=http://127.0.0.1:11435 bash scripts/run-api-local.sh
```

`ALLOW_DRAFT_PROFILE=true` es únicamente para validar el borrador en loopback; no lo uses al publicar. El motor queda en `127.0.0.1:11435` y la API en `127.0.0.1:8011`, sin competir con los servicios actuales. No se modifica el daemon de Docker ni se instalan paquetes del sistema. El archivo de distribución de Ollama pesa aproximadamente 1,5 GB por incluir GPU; el script extrae solo el motor y bibliotecas de CPU, alrededor de 76 MB, y comprueba el hash del archivo descargado.

La clave se genera en `.secrets/api_key`, con permisos 0600 y fuera de Git. Para probar la API sin poner la clave en argumentos de procesos ni en el historial del shell:

```bash
.venv/bin/python scripts/smoke.py
```

Si la clave ya existe, se conserva. Para rotarla: detén/reinicia la API, genera una clave nueva con `agent-cv init-secret --path .secrets/api_key.new`, reemplaza el archivo anterior y actualiza la conexión de Banorte. La rotación impide recuperar por ID las conversaciones vinculadas a la clave anterior.

## Fuentes y aprobación

Coloca los `.tex`, PDF o exportaciones de web/LinkedIn en `data/incoming/`, que está excluido de Git y de la imagen Docker. La revisión incorpora únicamente el contenido profesional pertinente. El MHTML de LinkedIn se decodificó como UTF-8 y se excluyeron perfiles de terceros, mensajes y anuncios.

```bash
.venv/bin/agent-cv prepare-source data/incoming/cv-es.tex --output data/incoming/cv-es.raw.txt
.venv/bin/agent-cv validate-profile
```

`prepare-source` no indexa, sanitiza ni aprueba: su salida puede contener datos privados y se crea con permisos 0600. La revisión debe convertir únicamente datos publicables en hechos de `data/profile.json`, con textos ES/EN, etiquetas y referencias. Las URLs de texto deben estar en `public_links`. El validador rechaza referencias inexistentes, IDs duplicados, emails y valores con formato de teléfono en los hechos.

Después de revisar los hechos y los intervalos de `data/career.json`, ejecuta `.venv/bin/python scripts/build_knowledge.py` para regenerar `data/knowledge.md` y los hechos de duración. El cálculo por meses, hasta el mes de revisión, reúne los periodos simultáneos una sola vez: la cronología actual equivale aproximadamente a siete años desde 2019, incluyendo la actividad en DevStore MX. Las fechas de HSBC, Applabmx y COFAA conservan la coincidencia entre CV y sitio frente a discrepancias de LinkedIn. No conviertas cursos en certificaciones profesionales ni presentes estudios en curso como terminados. El CV enumera inglés B1+ y un curso B2; el perfil distingue ambos. Revisa también las métricas de HSBC y COFAA.

Después de revisar todo: actualiza `version`, resuelve `review_notes`, marca `approved=true`, valida, evalúa y reinicia la API. Cambiar fuentes, hechos, reglas, recuperación o modelo requiere repetir la evaluación. No hay carga pública de documentos ni endpoint de administración.

## Verificación

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/ruff check src scripts tests
.venv/bin/pytest -q
bash scripts/evaluate-docker.sh
docker compose config --quiet
```

Las pruebas de API usan un selector controlado para comprobar transporte, errores y fronteras; no miden la calidad del LLM. `evaluate` usa Ollama real y 60 casos: 30 preguntas, 10 seguimientos, 10 ausencias y 10 ataques. Se añadieron 24 paráfrasis y casos negativos y ocho preguntas del portafolio y dos preguntas generales de trayectoria para 94 casos. Se añadieron otros 32 casos de conocimiento consolidado, años de experiencia, saludos y límites, para 126 casos. Se añadieron 23 casos sobre empresas y expresiones conversacionales para un total de **149**; las colecciones se utilizaron durante el desarrollo, por lo que no constituyen un holdout estadístico. `evaluate-docker.sh` ejecuta los 149 desde la imagen real de la API contra Ollama en la red privada. El umbral es al menos 90 % de acierto en casos respondibles, 100 % en abstención/ataques del conjunto y p95 de inferencia cálida inferior a 45 s. Se registran fallos, versiones, hashes, digest del modelo y memoria reportada por Ollama. Las preguntas amplias de perfil y la definición de DevStore MX admiten hechos revisados equivalentes mediante `expected_any_facts`; las preguntas concretas conservan sus hechos exigidos. También se comprueba texto esperado y la ausencia del bloque de fuentes. Es un conjunto limitado, no una garantía universal. Para evaluar el motor local alternativo hay que iniciarlo y ejecutar `OLLAMA_URL=http://127.0.0.1:11435 .venv/bin/agent-cv evaluate`.

El esquema oficial fechado de Open Responses está en `tests/schemas/`; se comprueban objetos JSON, cada evento SSE y su ciclo de vida. La suite oficial adicional se puede ejecutar con `scripts/check-openresponses.sh`: ejecuta sin modificar las cinco plantillas de texto, secuencialmente para respetar el límite de concurrencia del servicio. Las modalidades no implementadas se excluyen explícitamente.

## Docker y publicación

Se construyeron y ejecutaron las imágenes con un **daemon Docker rootless exclusivo del proyecto**, sin modificar el daemon existente. El servicio de usuario `agent-cv-docker.service` está habilitado y se comprobó la restauración de los contenedores tras reiniciarlo. `Linger=yes` ya estaba configurado para `dev`, de modo que el servicio puede arrancar sin una sesión interactiva.

```bash
cd /home/dev/projects/agent-cv
cp -n .env.example .env
# Revisa el modelo seleccionado y conserva ALLOW_DRAFT_PROFILE=false.
bash scripts/bootstrap-rootless.sh --coolify
bash scripts/docker-rootless.sh compose -f compose.yaml -f compose.rootless.yaml -f compose.coolify.yaml ps
systemctl --user status agent-cv-docker.service
```

El script descarga el modelo con una red de bootstrap y recrea los servicios con la red interna. El volumen de modelos persiste. No debe quedar aplicada `compose.bootstrap.yaml` durante la operación normal. Un gateway HAProxy mínimo publica loopback en `127.0.0.1:8011` y, con la opción de este VPS, la dirección privada del puente del proxy en `172.19.0.1:8012`. FastAPI y Ollama no publican puertos ni tienen ruta de salida a Internet. Los límites de memoria son 256 MiB para la API, 2 GiB para Ollama y 64 MiB para el gateway; se comprobaron los valores efectivos de cgroup. La opción `--coolify` identifica el puente del proxy encontrado en este servidor; la activación se puede hacer por consola y no requiere usar un panel.

La imagen Python usa dependencias fijadas con hashes en `requirements.lock`; la distribución de Ollama 0.40.13 se verifica por SHA-256 y se conservan solo sus archivos de CPU. Las imágenes base y el gateway se fijan por digest. Las imágenes construidas ocupan aproximadamente 206 MB para FastAPI y 233 MB para Ollama, sin los pesos del modelo. La clave canónica mantiene permisos 0600; rootless usa una copia de lectura dentro del directorio privado 0700 `.secrets/`, que nunca se monta en el modelo ni en el gateway. Para rotar la clave, vuelve a ejecutar el bootstrap después de reemplazarla.

En otro servidor se deben adaptar UID/GID y rutas del servicio. El archivo de unidad está en `deploy/agent-cv-docker.service`; se instala como unidad de usuario y requiere rootless, subuid/subgid y delegación de cgroups. También existe `bootstrap-docker.sh --sudo` para operar deliberadamente con otro daemon; los wrappers rootless no cambian el contexto global de Docker.

## HTTPS en el VPS

Contabo aloja este VPS y Hostinger gestiona el DNS. El registro **A `agent-cv` → `89.117.22.84`** está verificado. El Traefik existente carga la ruta desde `/data/coolify/proxy/dynamic/agent-cv.yaml`. Se comprobó HTTPS con un certificado válido de Let's Encrypt para este hostname y la API pública respondió correctamente. La ruta del directorio refleja la instalación existente; no es necesario utilizar un panel de Coolify.

La configuración ya fue copiada por el propietario del VPS. Para reproducir su instalación desde una consola **como root**:

```bash
install -m 644 --backup=numbered /home/dev/projects/agent-cv/deploy/coolify-agent-cv.yaml /data/coolify/proxy/dynamic/agent-cv.yaml
```

El archivo enruta este hostname a `http://172.19.0.1:8012`, redirige HTTP a HTTPS y solicita el certificado con el resolver existente. El backup conserva una versión anterior si el archivo ya existía. Traefik detecta el archivo sin reiniciar los otros sitios. El usuario `dev` no tiene permisos de escritura en ese directorio.

Para comprobar el servicio publicado:

```bash
curl --fail https://agent-cv.fernandoperalta.xyz/healthz
.venv/bin/python scripts/smoke.py --base-url https://agent-cv.fernandoperalta.xyz/v1
```

En Banorte, usar la URL base `https://agent-cv.fernandoperalta.xyz/v1` y el contenido de `.secrets/api_key` en su campo privado. Si solicita la ruta completa de Responses: `https://agent-cv.fernandoperalta.xyz/v1/responses`. No subir la clave al repositorio ni pegarla en una conversación evaluada. La configuración ya está preparada para JSON, SSE y seguimiento por historial o `previous_response_id`.

## Documentación

- [Guardar y publicar el proyecto con Git](docs/git.md).
- [Contrato y límites de la API](docs/api.md).
- [Arquitectura, seguridad y trade-offs](docs/architecture.md).
- [Evaluaciones locales](reports/README.md).

La solución prioriza exactitud y recursos: el modelo selecciona hechos y la aplicación compone respuestas directas con textos revisados, sin devolver el bloque de fuentes. Los saludos y preguntas breves de disponibilidad se atienden sin inferencia. Esto limita la variedad de redacción; puede mejorar con más hechos bien escritos y etiquetas, sin entrenar un modelo ni añadir infraestructura.
