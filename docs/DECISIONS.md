# Decisiones de arquitectura

## ADR-001: construir Celeste con arquitectura propia

Se estudiaran proyectos externos tipo JARVIS como referencia de implementaciones, pero no seran la base del codigo de Celeste. Celeste debe ser multiplataforma y distribuida desde el diseno.

## ADR-002: Markdown como fuente de verdad humana

Las notas y recuerdos importantes deben permanecer en formatos abiertos. La base de datos futura sera un indice/cache reconstruible, no la unica copia del conocimiento.

## ADR-003: no usar IA en V0.1

El Core debe funcionar sin LLM. Primero se valida red, almacenamiento y Android-PC.

## ADR-004: no resolver conflictos destructivamente

Cuando exista sincronizacion bidireccional, un conflicto de contenido humano no debe resolverse con Last-Write-Wins silencioso. Celeste preservara ambas versiones hasta poder fusionarlas.

## ADR-005: privilegios minimos

Un LLM nunca recibira shell/sudo/administrador irrestricto. Toda accion del sistema pasara por herramientas declaradas y politicas de permiso.

## ADR-006: modelo Ollama chico por defecto mientras el Core corre por CPU

`CELESTE_LLM_MODEL` local se bajo de `qwen3.5:9b` a `qwen3.5:4b` (2026-09-04). El PC actual no tiene GPU compatible para acelerar Ollama (Core corre 100% CPU), y para el caso de uso de voz (V0.5) la latencia importa mas que la calidad marginal de un modelo mas grande: una respuesta lenta rompe la sensacion de "asistente" cuando se habla en vivo. Este es un ajuste de config local en `.env` (no versionado), no un cambio de codigo. Revisar de nuevo cuando el PC tenga GPU NVIDIA (Ollama acelera bien con CUDA); ahi probablemente conviene volver a `qwen3.5:9b` o subir a un modelo mayor.
