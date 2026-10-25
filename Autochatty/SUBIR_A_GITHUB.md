# Subir el proyecto al GitHub propio

El repositorio debe ser independiente (no usar otro proyecto existente).
Repositorio sugerido: `Lord-physics/ControladorChatGPT-Windows`.

Desde Windows, instala [GitHub CLI](https://cli.github.com/), inicia sesion con `gh auth login`, abre una terminal dentro de la carpeta y ejecuta:

```powershell
git init
git add .
git commit -m "Controlador ChatGPT v4: descubrimiento e instalador Windows"
git branch -M main
gh repo create ControladorChatGPT-Windows --private --source . --remote origin --push
```

Si quieres incluir un release con los dos ejecutables compilados, el workflow `.github/workflows/windows-build.yml` compila el `.exe` principal en un runner Windows. Inicia el workflow manualmente desde **Actions**, o crea una etiqueta `v4.0.0` y subela al remoto para crear un GitHub Release. No cambies la visibilidad del repositorio sin revisar los archivos.

**No se suben historiales ni conversaciones:** la configuracion real vive en `%LOCALAPPDATA%\ControladorChatGPT`, fuera de esta carpeta. No incluyas ese directorio en el repositorio.

Alternativamente, descomprime el ZIP y ejecuta **`publicar_en_github.bat`** en Windows. Requiere Git para Windows y GitHub CLI; pide confirmacion antes de crear un repositorio **privado**. Si el repositorio ya existe, sigue las instrucciones manuales anteriores.
