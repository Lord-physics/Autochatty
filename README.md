# Autochatty v8

Controlador experimental de ChatGPT para Windows.

**Version 8:** el explorador de conversaciones distingue las secciones actuales **Recientes** y **Proyectos**, muestra proyectos accesibles aunque no expongan sus chats, y permite elegir chats accesibles con un clic. Se conserva la cola de trabajos y los horarios.

**Limitacion:** la accesibilidad de Windows no garantiza la enumeracion completa de la cuenta. Los nombres se leen de la interfaz real; no se generan nombres ni se importan datos externos automaticamente.

Cuando la app no expone chats o proyectos se genera un diagnostico local sin nombres privados en `%LOCALAPPDATA%\ControladorChatGPT\diagnostico_uia.json`. No se envia automaticamente.

**Compilacion:** GitHub Actions compila `ControladorChatGPT.exe` y publica un artefacto descargable: [Actions](https://github.com/Lord-physics/Autochatty/actions). No se ha validado aun en el equipo Windows del usuario.

Documentacion: [LEEME](Autochatty/LEEME.md).
