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
