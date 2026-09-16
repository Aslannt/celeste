from app.services.conversation import ConversationHistory


def test_append_and_recent_orders_messages():
    history = ConversationHistory()
    history.append_exchange("Hola", "Hola, como estas?")
    history.append_exchange("Bien, y tu?", "Tambien bien, gracias.")

    recent = history.recent()

    assert recent == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola, como estas?"},
        {"role": "user", "content": "Bien, y tu?"},
        {"role": "assistant", "content": "Tambien bien, gracias."},
    ]


def test_history_caps_to_max_turns():
    history = ConversationHistory(max_turns=2)
    for index in range(4):
        history.append_exchange(f"pregunta {index}", f"respuesta {index}")

    recent = history.recent()

    assert len(recent) == 4
    assert recent[0] == {"role": "user", "content": "pregunta 2"}
    assert recent[-1] == {"role": "assistant", "content": "respuesta 3"}


def test_idle_gap_resets_history():
    history = ConversationHistory(idle_seconds=0.05)
    history.append_exchange("Primero", "Respuesta uno")
    assert history.recent()

    import time

    time.sleep(0.1)

    assert history.recent() == []
    history.append_exchange("Segundo", "Respuesta dos")
    assert history.recent() == [
        {"role": "user", "content": "Segundo"},
        {"role": "assistant", "content": "Respuesta dos"},
    ]


def test_blank_user_message_is_ignored():
    history = ConversationHistory()
    history.append_exchange("   ", "no deberia guardarse")

    assert history.recent() == []


def test_blank_assistant_reply_keeps_only_user_message():
    history = ConversationHistory()
    history.append_exchange("Solo mi mensaje", "   ")

    assert history.recent() == [{"role": "user", "content": "Solo mi mensaje"}]


def test_clear_empties_history():
    history = ConversationHistory()
    history.append_exchange("Hola", "Hola de vuelta")
    history.clear()

    assert history.recent() == []
