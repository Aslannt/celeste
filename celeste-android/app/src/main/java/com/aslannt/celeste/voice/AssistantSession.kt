package com.aslannt.celeste.voice

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.aslannt.celeste.data.CelesteApi
import com.aslannt.celeste.data.ConfigStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.Normalizer

enum class Phase { IDLE, LISTENING, THINKING, SPEAKING, ERROR }

/**
 * One conversation turn at a time: tap -> listen -> think (PC) -> speak.
 * Shared by the minimal home screen and the assistant overlay so both behave
 * exactly the same. Compose state, so the UI just reads the fields.
 */
class AssistantSession(context: Context, private val scope: CoroutineScope) {
    private val store = ConfigStore(context)
    private val voice = VoiceClient(context.applicationContext) { store.load() }

    var phase by mutableStateOf(Phase.IDLE)
        private set
    var heard by mutableStateOf("")
        private set
    var reply by mutableStateOf("")
        private set
    var level by mutableFloatStateOf(0f)
        private set

    private var pendingConfirmation: String? = null
    private var job: Job? = null
    private var onTurnFinished: (() -> Unit)? = null

    val isConfigured: Boolean get() = store.load().coreBaseUrl.isNotBlank()

    /** Tap on the orb: start, stop listening early, or interrupt the voice. */
    fun toggle() {
        when (phase) {
            Phase.IDLE, Phase.ERROR -> listen()
            Phase.LISTENING -> voice.stopRecording()
            Phase.SPEAKING -> {
                voice.stopPlayback()
                phase = Phase.IDLE
                level = 0f
                onTurnFinished?.invoke()
            }
            Phase.THINKING -> Unit
        }
    }

    /** Called by the overlay: close itself once Celeste finished talking. */
    fun setOnTurnFinished(callback: (() -> Unit)?) {
        onTurnFinished = callback
    }

    fun listen() {
        if (!isConfigured) {
            phase = Phase.ERROR
            reply = "Configura la dirección del Core en el engranaje."
            return
        }
        job?.cancel()
        job = scope.launch {
            phase = Phase.LISTENING
            heard = ""
            val recording = withContext(Dispatchers.IO) { voice.record { level = it } }
            level = 0f
            val wav = recording.wav
            if (wav == null) {
                phase = if (recording.deadMic) Phase.ERROR else Phase.IDLE
                reply = if (recording.deadMic) "El micrófono no da señal." else "No te escuché."
                onTurnFinished?.invoke()
                return@launch
            }
            phase = Phase.THINKING
            val confirmation = pendingConfirmation
            try {
                val answer = withContext(Dispatchers.IO) { voice.ask(wav) }
                heard = answer.transcript
                if (confirmation != null) {
                    pendingConfirmation = null
                    speakText(resolveConfirmation(confirmation, answer.transcript))
                    return@launch
                }
                pendingConfirmation = answer.confirmationId
                reply = answer.reply
                val audio = answer.wav
                if (audio != null) speak(audio) else finishTurn()
            } catch (error: Exception) {
                phase = Phase.ERROR
                reply = error.message?.takeIf { it.isNotBlank() }
                    ?: "No pude hablar con tu PC. ¿Está encendido el Core?"
                onTurnFinished?.invoke()
            }
        }
    }

    fun cancel() {
        job?.cancel()
        voice.stopRecording()
        voice.stopPlayback()
        phase = Phase.IDLE
        level = 0f
    }

    private suspend fun speak(wav: ByteArray) {
        phase = Phase.SPEAKING
        withContext(Dispatchers.Main) { voice.play(wav) { finishTurn() } }
        while (scope.isActive && voice.isPlaying()) {
            level = voice.level()
            delay(30)
        }
        level = 0f
    }

    /** Confirmation replies are short and local: no need to ask the PC for audio. */
    private suspend fun speakText(text: String) {
        reply = text
        finishTurn()
    }

    private fun finishTurn() {
        level = 0f
        if (pendingConfirmation != null) {
            // Celeste asked "¿confirmo?": listen for "sí"/"no" without another tap.
            listen()
            return
        }
        phase = Phase.IDLE
        onTurnFinished?.invoke()
    }

    private suspend fun resolveConfirmation(confirmationId: String, said: String): String {
        val plain = Normalizer.normalize(said.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
        val api = CelesteApi(store.load())
        return withContext(Dispatchers.IO) {
            runCatching {
                when {
                    NO.containsMatchIn(plain) -> { api.cancelAssistantAction(confirmationId); "Cancelado." }
                    YES.containsMatchIn(plain) -> { api.confirmAssistantAction(confirmationId); "Hecho." }
                    else -> { api.cancelAssistantAction(confirmationId); "No entendí si sí o no; lo cancelé por seguridad." }
                }
            }.getOrElse { "No pude completar la confirmación." }
        }
    }

    private companion object {
        val YES = Regex("\\b(si|confirmo|confirma|dale|hazlo|claro|de una|adelante)\\b")
        val NO = Regex("\\b(no|cancela|cancelar|olvidalo|dejalo)\\b")
    }
}
