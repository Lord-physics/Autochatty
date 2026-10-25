# Autochatty v8 - Descubrimiento de Recientes y Proyectos

Autochatty v8 actualiza el descubrimiento para la app oficial de ChatGPT para Windows y trata Recientes y Proyectos como secciones independientes.

## Uso

1. Abre Autochatty y ChatGPT en una sesion desbloqueada de Windows.
2. Autochatty inicia automaticamente el descubrimiento local de elementos accesibles.
3. Elige un chat con un clic; se registra en la cola sin exportar ni importar archivos.
4. Los proyectos detectados aparecen por su nombre real, incluso si la app no revela los chats del proyecto.

Autochatty no inventa titulos, no lee mensajes y no escanea cachés privadas. Si Windows no publica un chat mediante su arbol de accesibilidad, Autochatty no puede descubrirlo por este metodo. Recientes no incluye necesariamente todo el historial. No existe una API publica documentada para enumerar toda la cuenta desde la app.

## Diagnostico automatico

Si la app no expone chats o proyectos, Autochatty escribe
`%LOCALAPPDATA%\ControladorChatGPT\diagnostico_uia.json`.

El archivo guarda los tipos de controles, su zona, jerarquia y los nombres de categorias conocidos. **No guarda los titulos privados de chats/proyectos ni el contenido de los mensajes.** Puedes compartirlo voluntariamente para adaptar el detector a tu version real de Windows. No se envia nada a ningun servidor.

## Instalacion desde el ZIP

- Para el codigo Python: Python 3.11+, ejecutar `instalar.bat` y `iniciar.bat`.
- Para un ejecutable independiente: descargar el artefacto de la compilacion v8 desde GitHub Actions una vez que esta finalice correctamente y usar `ControladorChatGPT.exe`.
- Cierra Autochatty v6/v7 antes de sustituir los archivos de programa. La configuracion se conserva en `%LOCALAPPDATA%\ControladorChatGPT`.

El actualizador v6 anterior NO incluye esta version. Las pruebas del detector son simulaciones: el comportamiento en tu app Windows no esta validado todavia.
