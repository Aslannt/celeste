from app.services.response_guard import (
    grounded_memory_priority_reply,
    guard_memory_reply,
    sanitize_public_events,
)
from app.services.tools import ToolExecution, ToolRisk


def _search_event() -> ToolExecution:
    return ToolExecution(
        tool="search_memory",
        risk=ToolRisk.READ,
        status="executed",
        output=[
            {
                "id": "1",
                "title": "tengo que revisar el aceite de la moto",
                "content": "tengo que revisar el aceite de la moto",
                "type": "note",
                "tags": ["assistant"],
            },
            {
                "id": "2",
                "title": "comprar lubricante para la cadena de la moto",
                "content": "comprar lubricante para la cadena de la moto",
                "type": "note",
                "tags": ["assistant"],
            },
            {
                "id": "3",
                "title": "Recordatorio: Revisar presion llantas moto - Sabado",
                "content": "El proximo sabado debo revisar la presion de las llantas de la moto.",
                "type": "task",
                "tags": ["mantenimiento", "moto", "recordatorio"],
            },
        ],
    )


def test_priority_request_replaces_domain_hallucinations_with_grounded_reply():
    reply, guarded = guard_memory_reply(
        "Revisa lo que recuerdas de la moto y dime que deberia hacer primero y por que.",
        (
            "Revisa el aceite primero porque sin aceite el motor puede sobrecalentarse. "
            "Luego sigue el recordatorio programado del sabado."
        ),
        [_search_event()],
    )

    assert guarded is True
    assert "no puedo determinar con certeza" in reply.lower()
    assert "sobrecalent" not in reply.lower()
    assert "recordatorio programado" not in reply.lower()
    assert "tengo que revisar el aceite de la moto" in reply
    assert "comprar lubricante para la cadena de la moto" in reply
    assert "no demuestra que exista una notificacion activa" in reply.lower()


def test_priority_request_can_be_grounded_immediately_after_search():
    reply = grounded_memory_priority_reply(
        "Revisa lo que recuerdas de la moto y dime que deberia hacer primero y por que.",
        [_search_event()],
    )

    assert reply is not None
    assert "no puedo determinar con certeza" in reply.lower()
    assert "tengo que revisar el aceite de la moto" in reply


def test_priority_early_exit_does_not_intercept_mutation_request():
    reply = grounded_memory_priority_reply(
        "Revisa lo de la moto, dime que deberia hacer primero y elimina la primera nota.",
        [_search_event()],
    )

    assert reply is None


def test_schedule_claim_without_priority_is_replaced():
    reply, guarded = guard_memory_reply(
        "Que recuerdas de la moto?",
        "Tienes un recordatorio programado para revisar las llantas el sabado.",
        [_search_event()],
    )

    assert guarded is True
    assert "recordatorio programado" not in reply.lower()
    assert "no demuestra que exista una notificacion activa" in reply.lower()


def test_grounded_memory_reply_without_priority_or_schedule_claim_is_unchanged():
    original = "Encontre tres notas sobre la moto."
    reply, guarded = guard_memory_reply(
        "Que recuerdas de la moto?",
        original,
        [_search_event()],
    )

    assert guarded is False
    assert reply == original


def test_guard_does_not_replace_mutation_or_confirmation_flows():
    delete_event = ToolExecution(
        tool="delete_note",
        risk=ToolRisk.CONFIRM,
        status="confirmation_required",
        confirmation_id="opaque-id",
    )
    original = "Necesito tu confirmacion antes de eliminar la nota."

    reply, guarded = guard_memory_reply(
        "Busca la nota de la moto y eliminala.",
        original,
        [_search_event(), delete_event],
    )

    assert guarded is False
    assert reply == original


def test_public_event_sanitizer_removes_provider_only_context():
    events = [
        {
            "tool": "search_memory",
            "risk": "READ",
            "status": "executed",
            "output": [
                {
                    "id": "1",
                    "title": "nota",
                    "_celeste_context": "provider-only",
                }
            ],
        }
    ]

    sanitized = sanitize_public_events(events)

    assert sanitized[0]["output"][0] == {"id": "1", "title": "nota"}
    assert "_celeste_context" in events[0]["output"][0]
