# Guía para agentes

- Antes de entregar, ejecutar: `ruff format --check .`, `ruff check .`, `mypy src` y
  `pytest`.
- Mantener separadas descarga, extracción, comparación, estado, notificación y CLI bajo
  `src/leixa_monitor`.
- Nunca incluir tokens, identificadores de chat ni otros secretos en código, fixtures, logs o
  documentación.
- Todo cambio del parser debe cubrirse con fixtures locales; los tests unitarios no dependen de
  la web real.
- Una descarga o extracción fallida nunca puede reemplazar el último `data/state.json` válido.
- Conservar Python 3.12 y compatibilidad con `.github/workflows/monitor-leixa.yml`.

