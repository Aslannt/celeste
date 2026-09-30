# celeste-desktop

Orbe de Celeste anclado al escritorio de Windows. Un clic y hablas.

Vive en el escritorio, como un widget de Rainmeter: queda debajo de todas las ventanas (solo se ve
cuando el escritorio está a la vista), Win + D no lo esconde y hacerle clic no le roba el foco a nada.

- **Clic**: empieza a escuchar; corta solo cuando dejas de hablar (~1 s de silencio).
- **Clic mientras escucha**: corta ya. **Clic mientras habla**: la calla.
- **Arrastrar**: mover el orbe (recuerda la posición). **Clic derecho**: nueva conversación / salir.
- Si Celeste pide confirmación (borrar, enviar correo), después de hablar vuelve a escuchar sola: di "sí" o "no". Si no queda claro, cancela.

Voz 100% local: el audio nunca sale del PC. Whisper `large-v3-turbo` en la GPU (~0.3 s) y Piper
(`es_MX-claude-high`). Al Core solo va el texto, por `POST /api/v1/assistant/chat`, con la misma
memoria de conversación y confirmaciones que la web UI y Android.

## Instalar

```powershell
cd celeste-desktop
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m piper.download_voices es_MX-claude-high --data-dir voices
copy .env.example .env   # poner CELESTE_API_TOKEN y, si hace falta, CELESTE_MIC
.\start_widget.ps1            # arrancar
.\start_widget.ps1 -Install   # además, arrancar solo al iniciar sesión
```

Colores del orbe: violeta tenue = cargando, violeta = listo, fucsia = escuchando,
violeta con anillo girando = pensando, lila pulsando = hablando, rojo = error.
