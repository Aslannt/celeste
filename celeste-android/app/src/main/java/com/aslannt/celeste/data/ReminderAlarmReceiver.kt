package com.aslannt.celeste.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.aslannt.celeste.MainActivity

const val REMINDER_NOTIFICATION_CHANNEL_ID = "celeste_reminders"

/** Fires the actual OS notification when a local reminder's alarm goes off. */
class ReminderAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val reminderId = intent.getStringExtra(REMINDER_ALARM_EXTRA_ID) ?: return
        val title = intent.getStringExtra(REMINDER_ALARM_EXTRA_TITLE)
            ?.takeIf { it.isNotBlank() } ?: "Recordatorio"
        val message = intent.getStringExtra(REMINDER_ALARM_EXTRA_MESSAGE).orEmpty()
            .ifBlank { "Recordatorio de Celeste" }

        ensureChannel(context)

        val hasPermission = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(
                context, android.Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        if (!hasPermission) return

        val openIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val contentIntent = PendingIntent.getActivity(
            context,
            reminderId.hashCode(),
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(context, REMINDER_NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(title)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setAutoCancel(true)
            .setContentIntent(contentIntent)
            .build()

        NotificationManagerCompat.from(context).notify(reminderId.hashCode(), notification)
    }

    private fun ensureChannel(context: Context) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (manager.getNotificationChannel(REMINDER_NOTIFICATION_CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            REMINDER_NOTIFICATION_CHANNEL_ID,
            "Recordatorios de Celeste",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Avisos cuando vence un recordatorio creado en Celeste."
        }
        manager.createNotificationChannel(channel)
    }
}
