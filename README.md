# Autochatty — controlador de ChatGPT en Windows

## Estado de la versión 5

La versión v5 del paquete local introduce:
- Exploración conservadora de títulos **realmente expuestos** por la interfaz de accesibilidad de Windows. No genera nombres sintéticos.
- Importación local de `conversations.json` desde un ZIP de exportación oficial de ChatGPT para conseguir mayor cobertura que la barra lateral visible.
- Agrupación por proyectos solo si el archivo contiene referencias y nombres de proyecto verificables. De otro modo, `Sin proyecto verificado`.
- Detección de títulos duplicados, evitando la ejecución automática cuando la selección de conversación es ambigua.
- La v5 conserva los horarios, el control de recursos y los estados anteriores.

**Advertencia:** el repositorio todavía no contiene el código fuente completo ni un ejecutable compilado de v5. El paquete ZIP de código está disponible en la conversación de ChatGPT donde se generó. No se ha probado el módulo UIA contra la app instalada del usuario.

La importación de datos se procesa localmente. No subas a GitHub tu exportación, el historial ni el archivo de configuración de usuario.

La app oficial de ChatGPT no ofrece aquí una integración documentada que permita enumerar todo el historial o todos los proyectos en tiempo real: los resultados por UIA son necesariamente parciales.
