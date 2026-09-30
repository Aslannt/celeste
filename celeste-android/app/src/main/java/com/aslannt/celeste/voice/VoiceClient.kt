package com.aslannt.celeste.voice

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.util.Base64
import com.aslannt.celeste.BuildConfig
import com.aslannt.celeste.data.CelesteConfig
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Phone side of Celeste's voice (ADR-014): the phone only records and plays.
 * Transcription (Whisper) and the voice (Piper) run on the user's PC through
 * POST /api/v1/assistant/voice, so nothing depends on Google speech services
 * and the voice is the same as the desktop orb.
 */
class VoiceClient(private val context: Context, private val config: () -> CelesteConfig) {

    data class VoiceReply(
        val transcript: String,
        val reply: String,
        val provider: String,
        val confirmationId: String?,
        val wav: ByteArray?,
    )

    class RecordingResult(val wav: ByteArray?, val deadMic: Boolean)

    @Volatile private var stopRequested = false
    private var player: MediaPlayer? = null
    private var envelope: FloatArray = FloatArray(0)
    private var playStartedAt = 0L

    fun stopRecording() {
        stopRequested = true
    }

    /**
     * Records until the user stops talking (~1.6 s of silence), the caller asks
     * to stop, or 25 s pass. Noise floor = quietest blocks seen so far, so
     * speaking right after the tap does not make the cut come early.
     */
    @SuppressLint("MissingPermission") // callers request RECORD_AUDIO first
    fun record(onLevel: (Float) -> Unit): RecordingResult {
        stopRequested = false
        debugInjectedWav()?.let { return RecordingResult(it, deadMic = false) }

        val minBuffer = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            max(minBuffer, BLOCK * 8),
        )
        val pcm = ByteArrayOutputStream()
        val block = ShortArray(BLOCK)
        val history = ArrayList<Float>()
        var peak = 0f
        var speechStarted = false
        val started = System.currentTimeMillis()
        var lastVoice = started
        try {
            recorder.startRecording()
            while (!stopRequested) {
                val read = recorder.read(block, 0, BLOCK)
                if (read <= 0) continue
                val bytes = ByteBuffer.allocate(read * 2).order(ByteOrder.LITTLE_ENDIAN)
                var sum = 0.0
                for (i in 0 until read) {
                    bytes.putShort(block[i])
                    val v = block[i] / 32768f
                    sum += v * v
                    peak = max(peak, kotlin.math.abs(v))
                }
                pcm.write(bytes.array())
                history.add(sqrt(sum / read).toFloat())
                val floor = percentile10(history)
                val threshold = max(0.004f, floor * 3f)
                val rms = history.takeLast(3).average().toFloat()
                onLevel(min(1f, rms / (threshold * 4f)))
                val now = System.currentTimeMillis()
                if (rms > threshold) {
                    speechStarted = true
                    lastVoice = now
                }
                if (speechStarted && now - lastVoice > SILENCE_MS) break
                if (!speechStarted && now - started > NO_SPEECH_MS) {
                    onLevel(0f)
                    return RecordingResult(null, deadMic = peak < 1e-4f)
                }
                if (now - started > MAX_MS) break
            }
        } finally {
            runCatching { recorder.stop() }
            recorder.release()
        }
        onLevel(0f)
        if (!speechStarted) return RecordingResult(null, deadMic = false)
        return RecordingResult(wavFromPcm(pcm.toByteArray(), RATE), deadMic = false)
    }

    /** Sends the recording to the Core; the reply comes back as text + WAV. */
    fun ask(wav: ByteArray): VoiceReply {
        val cfg = config()
        val connection = URL(cfg.coreBaseUrl.trimEnd('/') + "/api/v1/assistant/voice").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 6000
        connection.readTimeout = 120_000
        connection.doOutput = true
        connection.setRequestProperty("X-Celeste-Token", cfg.apiToken)
        connection.setRequestProperty("Content-Type", "audio/wav")
        try {
            connection.outputStream.use { it.write(wav) }
            val code = connection.responseCode
            val body = (if (code in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull()
                throw IllegalStateException(detail?.takeIf { it.isNotBlank() } ?: "El Core respondió $code.")
            }
            val json = JSONObject(body)
            var confirmationId: String? = null
            val events = json.optJSONArray("events")
            if (events != null) {
                for (i in 0 until events.length()) {
                    val event = events.getJSONObject(i)
                    if (event.optString("status") == "confirmation_required" && !event.isNull("confirmation_id")) {
                        confirmationId = event.getString("confirmation_id")
                    }
                }
            }
            val audio = json.optString("audio_wav_base64", "")
            return VoiceReply(
                transcript = json.optString("transcript"),
                reply = json.optString("reply"),
                provider = json.optString("provider"),
                confirmationId = confirmationId,
                wav = if (audio.isBlank() || audio == "null") null else Base64.decode(audio, Base64.DEFAULT),
            )
        } finally {
            connection.disconnect()
        }
    }

    /** Plays the reply without blocking; [level] animates the orb while it speaks. */
    fun play(wav: ByteArray, onDone: () -> Unit) {
        stopPlayback()
        envelope = envelopeOf(wav)
        val file = File(context.cacheDir, "celeste_reply.wav").apply { writeBytes(wav) }
        player = MediaPlayer().apply {
            setDataSource(file.absolutePath)
            setOnCompletionListener {
                it.release()
                if (player === it) player = null
                onDone()
            }
            prepare()
            playStartedAt = System.currentTimeMillis()
            start()
        }
    }

    fun isPlaying(): Boolean = player != null

    fun level(): Float {
        if (player == null || envelope.isEmpty()) return 0f
        val index = ((System.currentTimeMillis() - playStartedAt) / 30L).toInt()
        return envelope[min(index, envelope.size - 1).coerceAtLeast(0)]
    }

    fun stopPlayback() {
        player?.let { runCatching { it.stop() }; it.release() }
        player = null
    }

    /**
     * Debug builds only: if files/debug_input.wav exists (pushed with adb), it is
     * used instead of the microphone, so the whole voice flow can be tested on
     * an emulator with no mic. Never active in release builds.
     */
    private fun debugInjectedWav(): ByteArray? {
        if (!BuildConfig.DEBUG) return null
        val file = File(context.getExternalFilesDir(null), "debug_input.wav")
        if (!file.exists()) return null
        return file.readBytes().also { file.renameTo(File(file.parentFile, "debug_input.used.wav")) }
    }

    companion object {
        const val RATE = 16000
        private const val BLOCK = 480 // 30 ms
        private const val SILENCE_MS = 1600L
        private const val NO_SPEECH_MS = 6000L
        private const val MAX_MS = 25_000L

        private fun percentile10(values: List<Float>): Float {
            val sorted = values.sorted()
            return sorted[(sorted.size - 1) / 10]
        }

        fun wavFromPcm(pcm: ByteArray, rate: Int): ByteArray {
            val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN).apply {
                put("RIFF".toByteArray()); putInt(36 + pcm.size); put("WAVE".toByteArray())
                put("fmt ".toByteArray()); putInt(16); putShort(1); putShort(1)
                putInt(rate); putInt(rate * 2); putShort(2); putShort(16)
                put("data".toByteArray()); putInt(pcm.size)
            }
            return header.array() + pcm
        }

        /** 30 ms RMS envelope (0..1) of a 16-bit mono WAV, to animate speech. */
        fun envelopeOf(wav: ByteArray): FloatArray {
            if (wav.size <= 44) return FloatArray(0)
            val buffer = ByteBuffer.wrap(wav, 44, wav.size - 44).order(ByteOrder.LITTLE_ENDIAN)
            val rate = ByteBuffer.wrap(wav, 24, 4).order(ByteOrder.LITTLE_ENDIAN).int.coerceAtLeast(8000)
            val frame = rate * 30 / 1000
            val samples = (wav.size - 44) / 2
            val out = FloatArray(samples / frame + 1)
            var peak = 1e-6f
            for (f in out.indices) {
                var sum = 0.0
                var n = 0
                while (n < frame && buffer.remaining() >= 2) {
                    val v = buffer.short / 32768f
                    sum += v * v
                    n++
                }
                out[f] = if (n == 0) 0f else sqrt(sum / n).toFloat()
                peak = max(peak, out[f])
            }
            for (f in out.indices) out[f] = out[f] / peak
            return out
        }
    }
}
