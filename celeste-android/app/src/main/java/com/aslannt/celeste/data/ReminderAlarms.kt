package com.aslannt.celeste.data

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import java.time.Instant
import java.time.format.DateTimeParseException

const val REMINDER_ALARM_EXTRA_ID = "reminder_id"
const val REMINDER_ALARM_EXTRA_TITLE = "title"
const val REMINDER_ALARM_EXTRA_MESSAGE = "message"

/**
 * Schedules on-device alarms for Celeste's local reminders so they still notify
 * the user when the app is backgrounded or closed. Celeste Core only keeps an
 * in-app notice feed (see NotificationStore); the actual OS-level alert has to
 * live on the phone, tied to a real wall-clock alarm, not a server poll.
 */
object ReminderAlarms {

    /** Re-syncs alarms for every reminder that is still pending (not done/cancelled). */
    fun sync(context: Context, reminders: List<Reminder>) {
        val manager = alarmManager(context) ?: return
        reminders
            .filter { it.doneAt.isNullOrBlank() && it.cancelledAt.isNullOrBlank() }
            .forEach { schedule(context, manager, it) }
    }

    fun cancel(context: Context, reminderId: String) {
        val manager = alarmManager(context) ?: return
        manager.cancel(pendingIntent(context, reminderId, title = "", message = ""))
    }

    private fun schedule(context: Context, manager: AlarmManager, reminder: Reminder) {
        val dueMillis = try {
            Instant.parse(reminder.dueAt).toEpochMilli()
        } catch (_: DateTimeParseException) {
            return
        }
        // If Celeste was closed while it became due, still fire almost immediately
        // instead of silently dropping it.
        val triggerAt = maxOf(dueMillis, System.currentTimeMillis() + 1_000)
        val pending = pendingIntent(context, reminder.id, reminder.title, reminder.message)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !manager.canScheduleExactAlarms()) {
                manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
            } else {
                manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
            }
        } catch (_: SecurityException) {
            manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending)
        }
    }

    private fun pendingIntent(
        context: Context,
        reminderId: String,
        title: String,
        message: String,
    ): PendingIntent {
        val intent = Intent(context, ReminderAlarmReceiver::class.java).apply {
            putExtra(REMINDER_ALARM_EXTRA_ID, reminderId)
            putExtra(REMINDER_ALARM_EXTRA_TITLE, title)
            putExtra(REMINDER_ALARM_EXTRA_MESSAGE, message)
        }
        return PendingIntent.getBroadcast(
            context,
            reminderId.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun alarmManager(context: Context): AlarmManager? =
        context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
}
