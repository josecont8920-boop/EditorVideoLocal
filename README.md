# local_engine — Motor local de generación de video

Módulo autónomo dentro de ContentBotMXL: genera videos a partir de
**cualquier texto** (guion, artículo, PDF), 100% local, sin APIs de pago.

## Diferencia con el motor principal (`core/` en la raíz del repo)

| | Motor principal (raíz) | `local_engine/` |
|---|---|---|
| Guion | Gemini (paga) | Tu propio texto/PDF, sin IA generativa |
| Voz | edge-tts (online, gratis) | Coqui TTS (100% offline) |
| Imágenes | Robot MXL (assets fijos) | Tus propios fondos, por emoción |
| Uso | Canal infantil automatizado | Cualquier proyecto de video |

## Instalación

```bash
cd ~/ContentBotMXL_oficial
pip install -r local_engine/requirements.txt --break-system-packages
```

La primera vez que corras el TTS, Coqui va a descargar el modelo de voz
(unos cientos de MB). Después de eso, funciona sin internet.

## Uso — Interfaz web

```bash
streamlit run local_engine/frontend/app.py
```

## Uso — Por código

```python
from local_engine.core.orquestador import generar_video

resultado = generar_video(
    fuente_texto="Había una vez un robot que soñaba con las estrellas...",
    titulo="El robot y las estrellas",
    formato="vertical",  # o "horizontal"
)
print(resultado["ruta_completa"])
```

`fuente_texto` acepta: texto plano, ruta a `.txt`, o ruta a `.pdf`.

## Assets necesarios

Antes de generar tu primer video, agrega al menos una imagen a:
```
local_engine/assets/backgrounds/
```

Opcionalmente, organiza por emoción para que el video sea más dinámico:
```
local_engine/assets/backgrounds/feliz/
local_engine/assets/backgrounds/pensativo/
local_engine/assets/backgrounds/sorprendido/
local_engine/assets/backgrounds/hablando/
```

Música de fondo opcional (loop automático con fade in/out):
```
local_engine/assets/music/*.mp3
```

## Estructura

```
local_engine/
├── core/
│   ├── text_input.py       -> carga texto plano o PDF
│   ├── scene_processor.py  -> divide el texto en escenas (reglas, sin IA de pago)
│   ├── tts_engine.py       -> Coqui TTS (voz offline)
│   ├── asset_selector.py   -> elige imagen de fondo por emoción
│   ├── video_assembler.py  -> MoviePy: Ken Burns + subtítulos + música
│   └── orquestador.py      -> une todo el pipeline
├── frontend/
│   └── app.py               -> interfaz Streamlit
├── config/settings.py       -> configuración (formato, fuente, colores, modelo TTS)
├── assets/backgrounds/      -> tus imágenes de fondo
├── assets/music/            -> música de fondo opcional
├── data/textos_pendientes/  -> (opcional) lote de textos a procesar
└── output/                  -> videos generados
```
