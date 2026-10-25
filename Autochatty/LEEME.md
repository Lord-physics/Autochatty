# Autochatty v7 — selección directa de conversaciones

**Funciona con la aplicación ChatGPT para Windows.** No utiliza Edge, no se conecta a APIs privadas ni evita límites de uso.

## Uso diario (sin pasos de importación)

1. Abre Autochatty (`iniciar.bat` si usas código Python; `ControladorChatGPT.exe` si ya lo compilaste en Windows).
2. Al arrancar, Autochatty intenta abrir/encontrar la aplicación oficial ChatGPT y **busca automáticamente chats accesibles**.
3. En la lista agrupada por proyectos haz **un clic en el chat**. Queda registrado automáticamente para su programación, sin seleccionar archivos ZIP, escribir títulos, pulsar Importar ni confirmar.
4. Si quieres, selecciona otros chats del mismo modo. Puedes cerrar la ventana de lista: las elecciones se han guardado.

Los horarios y opciones que tenías de la v4/v5 se mantienen. Por seguridad, **el envío automático de mensajes sigue desactivado inicialmente**. Si lo habilitas, revisa antes el título de cada chat y haz una prueba controlada.

## Corrección v7 de la detección vacía

La v6 solo aceptaba ListItem/TreeItem en listas que Windows llamase exactamente "Chats". La v7 también reconoce Hyperlink, Button y Text dentro de un elemento navegable cuando un encabezado real de Chats o su jerarquía acredita el origen. Los botones de navegación y las etiquetas de proyecto no se consideran conversaciones. También puede desplegar una barra lateral identificada por UIA y espera un momento a que cargue WebView2.

No se generan nombres de chats. Si la app no publica su historial en la accesibilidad de Windows, la detección sigue siendo imposible de garantizar.

## Qué detecta realmente

- Solo títulos expuestos por los controles de accesibilidad de la aplicación ChatGPT. Puede desplazarse por las listas UIA y desplegar grupos de proyecto reconocibles, restaurando el estado al finalizar.
- Agrupa bajo el nombre de proyecto exclusivamente si la jerarquía accesible identifica inequívocamente su relación. Si no puede demostrarla, coloca la conversación en `Sin proyecto verificado`.
- Los chats con título duplicado se añaden solo como información y no se ejecutan automáticamente: el selector actual navega por título.
- Se resiste a inventar chats por heurísticas, usar cachés privadas, extraer cookies o acceder al contenido de los mensajes.

**No se puede garantizar encontrar todos los chats de una cuenta**: las conversaciones archivadas, bloqueadas, ocultas, una barra lateral virtualizada o una versión de ChatGPT que no exponga accesibilidad adecuada pueden faltar. Esta es una limitación real de la app y no debe interpretarse como que faltan en tu cuenta.

**No se ha probado contra tu instancia real de Windows.** El código se ha probado con simulaciones de UIA y pruebas de lógica; la compatibilidad de la interfaz puede cambiar tras actualizar ChatGPT.

## Actualización a v7

Descarga la compilación v7 desde GitHub Actions, o utiliza los archivos Python actualizados desde el ZIP. Conserva una copia del programa anterior y la configuración en %LOCALAPPDATA%\ControladorChatGPT. Si usas un EXE principal v6, debes sustituirlo por el EXE recompilado v7; los cambios en Python no afectan a un ejecutable antiguo.

## Desarrollo

- `chat_discovery.py`: exploración automática UIA, listas desplazables y proyectos verificados.
- `controller.py`: selección de un clic, horarios y cola.
- `storage.py`: persistencia local y migración.
- `app_adapter.py`: controles de la aplicación oficial, selección prudente por título.
- `.github/workflows/windows-build.yml`: pruebas y compilación del EXE principal en Windows.
- `build_native`: origen del lanzador de actualización.

Instalación desde fuentes: Python 3.11 o posterior, ejecutar `instalar.bat` y después `iniciar.bat`. Las pruebas se ejecutan con `probar.bat`.

**Privacidad:** los títulos/estados se guardan localmente en `%LOCALAPPDATA%\ControladorChatGPT`. No subas `controlador.json` a GitHub. El proyecto público solo contiene código y pruebas.
