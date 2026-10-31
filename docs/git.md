# Repositorio Git

El repositorio guarda el código, los archivos de Docker, las plantillas de configuración, el conocimiento profesional revisado, las pruebas y la documentación. La rama principal es `main`.

`.gitignore` excluye `.env`, `.secrets/`, `.runtime/`, los modelos descargados, los documentos originales de `data/incoming/`, las conversaciones de `data/state/` y los informes generados de `reports/`. `.env.example`, los archivos `.gitkeep` y `reports/README.md` sí se versionan.

## Publicar el primer commit

Crea un repositorio vacío en tu proveedor Git, con la visibilidad que prefieras, sin inicializar README ni otros archivos. Desde este directorio, sustituye la URL del ejemplo por la de ese repositorio:

```bash
git remote add origin https://github.com/TU_USUARIO/agent-cv.git
git push -u origin main
```

Si `origin` ya existe, comprueba su destino con `git remote -v`. El envío requiere autenticación con permisos sobre ese repositorio. Las credenciales se gestionan fuera del proyecto; no se incluyen en la URL ni en los archivos versionados.

## Guardar cambios posteriores

```bash
git status
git add src tests data docs scripts README.md
git diff --cached --check
git diff --cached
git commit -m "Describe el cambio"
git push
```

Añade explícitamente los demás archivos modificados, como Docker o las dependencias, cuando formen parte del cambio. Ejecuta las verificaciones pertinentes indicadas en el README antes de publicar.

## Recuperar en otro servidor

Clona el repositorio y sigue las instrucciones de despliegue del README. Las claves, la configuración local, las conversaciones y los modelos descargados no forman parte del respaldo Git. Para conservar la API key en una migración, restaura de forma privada el archivo `.secrets/api_key` antes de ejecutar el bootstrap; si no existe, el bootstrap genera una clave nueva. La clave actual y el despliegue existente permanecen en el VPS.
