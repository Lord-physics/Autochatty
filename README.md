# Autochatty

Controlador experimental de trabajos de ChatGPT en Windows 10/11.

## Versión 7 — detección corregida

La v6 filtraba exclusivamente listas UIA con nombre "Chats" y filas ListItem/TreeItem. La v7 reconoce también enlaces, botones y texto asociado a navegación, **solo dentro de una zona de chats verificable**. Detecta la barra lateral si Windows expone su control y espera a que cargue la app.

Descubre automáticamente las conversaciones accesibles y permite seleccionarlas con un clic. No inventa nombres y solo agrupa por proyectos si la relación es verificable. **No garantiza un inventario completo de la cuenta:** la aplicación oficial puede no exponer todas las conversaciones a accesibilidad UIA.

### Ejecutable Windows

GitHub Actions compila el nuevo \`ControladorChatGPT.exe\`; consulta [Actions](https://github.com/Lord-physics/Autochatty/actions) para descargar el artefacto \`Autochatty-v7-Windows\` después de que el workflow termine. El EXE v6 anterior no contiene la corrección.

Documentación: [LEEME](Autochatty/LEEME.md) y [Prueba en Windows](Autochatty/PRUEBA_EN_TU_PC.md). No subas exportaciones, historial ni archivos de configuración personales.
