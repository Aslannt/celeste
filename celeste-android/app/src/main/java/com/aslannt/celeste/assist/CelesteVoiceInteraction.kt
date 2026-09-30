package com.aslannt.celeste.assist

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.speech.RecognitionService
import android.speech.SpeechRecognizer
import com.aslannt.celeste.AssistActivity

/**
 * Makes Celeste selectable as the phone's default digital assistant, so the
 * assistant gesture (long-press power/home on most phones) opens her instead
 * of Google Assistant. The session only launches AssistActivity; all the real
 * work (recording, PC round trip, playback) happens there.
 */
class CelesteVoiceInteractionService : VoiceInteractionService()

class CelesteSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = CelesteSession(this)
}

class CelesteSession(context: Context) : VoiceInteractionSession(context) {
    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        startAssistantActivity(Intent(context, AssistActivity::class.java))
        hide()
    }
}

/**
 * Android requires every voice interaction service to declare a recognition
 * service. Celeste transcribes on the PC (Whisper), so this one politely
 * declines: other apps asking the system recognizer are not served by Celeste.
 */
class CelesteRecognitionService : RecognitionService() {
    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        listener?.error(SpeechRecognizer.ERROR_CLIENT)
    }

    override fun onCancel(listener: Callback?) = Unit

    override fun onStopListening(listener: Callback?) = Unit
}
