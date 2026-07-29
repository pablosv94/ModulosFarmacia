# Monitor de plazas del CIFP Leixa

Proyecto autónomo en Python 3.12 que consulta directamente el informe público de módulos
liberados de FP de la Xunta de Galicia. Solo extrae el centro `15021469 - CIFP Leixa`, el ciclo
`ZD2SAN000 - Farmacia e parafarmacia`, curso 2026-2027, grado medio y modalidad a distancia.
Compara cada PDF válido con el último estado y avisa por Telegram únicamente si cambian los
módulos o sus plazas.

El descargador identifica por separado un PDF real, el aviso HTML de informe en actualización,
errores HTTP temporales y HTML inesperado. Valida el dominio, `Content-Type`, firma `%PDF-`,
tamaño máximo de 50 MB y aplica timeouts y reintentos. El estado solo se sustituye después de
una descarga y extracción válidas.

## Ejecución local

Requisitos: Python 3.12 y acceso HTTPS a `www.edu.xunta.gal` y `api.telegram.org`.

En PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:TELEGRAM_BOT_TOKEN = "token proporcionado por BotFather"
$env:TELEGRAM_CHAT_ID = "identificador obtenido con getUpdates"
python -m leixa_monitor.cli check
```

En Linux o macOS, la activación es `source .venv/bin/activate` y las variables se definen con
`export TELEGRAM_BOT_TOKEN='…'` y `export TELEGRAM_CHAT_ID='…'`.

Comandos disponibles:

```text
python -m leixa_monitor.cli check
python -m leixa_monitor.cli check --dry-run
python -m leixa_monitor.cli check --force-notify
python -m leixa_monitor.cli send-test-notification
python -m leixa_monitor.cli print-current
python -m leixa_monitor.cli --data-dir otra-carpeta --attempts 5 --retry-wait 3 check
python -m leixa_monitor.cli -v check
```

`--dry-run` descarga y analiza, pero no envía ni modifica archivos. `--force-notify` envía el
estado actual aunque no haya cambios semánticos. La primera ejecución guarda una línea base sin
alerta; para avisar también entonces, define `NOTIFY_ON_FIRST_RUN=true`.

El estado válido queda en `data/state.json` y el contador de salud en `data/health.json`. La
salida manual muestra una tabla con código, módulo, ofertadas, ocupadas y vacantes. Código de
salida `0` significa éxito, `2` que el informe sigue actualizándose tras los reintentos y `1` un
error real. Si el SHA-256 coincide con el anterior, no vuelve a extraer ni notificar.

Los dos primeros fallos consecutivos solo generan logs. Al tercero se envía una única alerta;
tras recuperarse se envía otra y el contador vuelve a cero. Un fallo nunca borra el estado
anterior.

## Configuración de Telegram

1. En Telegram, abre `@BotFather`.
2. Envía `/newbot`, elige nombre y usuario, y guarda el token en un gestor seguro.
3. Abre una conversación con el bot recién creado y envíale cualquier mensaje.
4. Define el token temporalmente en tu terminal, sin guardarlo en el repositorio.
5. Consulta `getUpdates` y lee `message.chat.id`.

PowerShell, ocultando el token de la salida:

```powershell
$token = Read-Host "Token del bot"
$updates = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getUpdates"
$updates.result | ForEach-Object { $_.message.chat.id } | Sort-Object -Unique
Remove-Variable token
```

Linux/macOS:

```bash
read -rsp "Token del bot: " token; echo
curl -sS "https://api.telegram.org/bot${token}/getUpdates" |
  python -c "import json,sys; print(*{x['message']['chat']['id'] for x in json.load(sys.stdin)['result'] if 'message' in x}, sep='\n')"
unset token
```

Después configura `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` como variables de entorno y prueba:

```text
python -m leixa_monitor.cli send-test-notification
```

No pegues el token en incidencias, logs ni archivos. Si se filtra, revócalo desde BotFather.

## Configuración en GitHub

1. Sube este repositorio a GitHub.
2. Abre **Settings** → **Secrets and variables** → **Actions**.
3. En **Repository secrets**, crea `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
4. En **Settings** → **Actions** → **General**, revisa que los workflows puedan escribir en el
   repositorio. El YAML solicita exclusivamente `contents: write`.
5. Abre la pestaña **Actions** y selecciona **Monitor CIFP Leixa**.
6. Pulsa **Run workflow**, activa `Enviar solo una notificación de prueba` y ejecútalo.
7. Comprueba que llega el mensaje y que la ejecución termina correctamente.
8. Lanza otra ejecución sin esa opción para crear `data/state.json`.
9. Comprueba la siguiente ejecución programada en Actions.

El workflow se programa cada diez minutos durante las 24 horas, ejecuta formato, lint, tipado y
tests antes del monitor, y versiona únicamente `state.json` y `health.json` si cambiaron. Usa
concurrencia exclusiva y hasta tres intentos de `pull --rebase` y push. GitHub Actions puede
retrasar varios minutos los trabajos programados: diez minutos es una frecuencia solicitada, no
precisión en tiempo real. Los workflows programados solo funcionan en la rama por defecto y
GitHub puede desactivarlos tras largos periodos sin actividad.

## Desarrollo y pruebas

```text
ruff format --check .
ruff check .
mypy src
pytest
pytest -m integration
```

`pytest` excluye por defecto el test de red. La prueba `integration` es optativa y consulta el
endpoint real; puede saltarse si el informe se está regenerando.

## Diagnóstico

- **El informe se está actualizando:** es una respuesta normal de la Xunta. El monitor hace
  cinco intentos separados por 3 segundos. Finaliza con código 2 y conserva el estado.
- **No se encuentra el centro:** verifica que el curso sigue siendo 2026-2027 y revisa el texto
  extraído del PDF; tras tres ejecuciones fallidas se enviará la alerta persistente.
- **No se encuentra el ciclo:** la Xunta puede haber cambiado el código, el rótulo o el diseño.
  No edites el estado a mano; añade el nuevo formato como fixture y adapta el parser.
- **Telegram devuelve 401:** el token es incorrecto o fue revocado. Sustituye
  `TELEGRAM_BOT_TOKEN`.
- **Telegram devuelve 400:** normalmente el `chat_id` es incorrecto o el usuario aún no inició
  conversación con el bot. Envía un mensaje al bot y repite `getUpdates`.
- **GitHub Actions no puede hacer push:** revisa `contents: write`, la configuración de permisos
  de Actions y las reglas de protección de rama. Una regla que exige pull request impedirá el
  commit directo del bot.
- **El workflow programado no aparece:** el archivo debe estar en la rama por defecto. Comprueba
  que Actions esté habilitado y que el repositorio no lleve inactivo más de 60 días.
- **El parser deja de funcionar:** descarga el PDF manualmente para diagnóstico, extrae texto
  sin compartir datos sensibles, crea un fixture mínimo y ajusta `extractor.py`. El monitor
  conserva automáticamente el último estado válido.

## Diseño

`downloader.py` controla red y clasificación de respuestas; `extractor.py` mantiene el contexto
centro → ciclo → módulos y tolera saltos de línea y cabeceras repetidas; `comparator.py` produce
cambios estructurados; `state.py` escribe JSON atómicamente; `notifier.py` genera HTML escapado
y usa la API oficial de Telegram; `cli.py` coordina el proceso y la salud persistente.

No se usa OCR, navegador automatizado ni servicios de pago. El PDF no se guarda ni versiona.
