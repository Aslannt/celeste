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

private const val PREFS_NAME = "celeste_reminder_alarms"
private const val PREF_HANDLED_IDS = "handled_ids"

// Reminders overdue by more than this when first discovered are treated as
// stale (e.g. old test data) and are marked handled without alerting, instead
// of resurrecting them as a "fires in 1 second" catch-up notification.
private const val CATCH_UP_GRACE_MS = 24L * 60 * 60 * 1000

/**
 * Schedules on-device alarms for Celeste's local reminders so they still notify
 * the user when the app is backgrounded or closed. Celeste Core only keeps an
 * in-app notice feed (see NotificationStore); the actual OS-level alert has to
 * live on the phone, tied to a real wall-clock alarm, not a server poll.
 */
object ReminderAlarms {

    /**
     * Re-syncs alarms for every reminder that is still pending (not done/cancelled).
     * Each reminder is only ever scheduled once per install: `sync` runs on every
     * daily-context refresh (~30s), and re-arming an already-overdue reminder on
     * every pass would otherwise re-fire it in an endless loop.
     */
    fun sync(context: Context, reminders: List<Reminder>) {
        val manager = alarmManager(context) ?: return
        val handled = handledIds(context)
        reminders
            .filter { it.doneAt.isNullOrBlank() && it.cancelledAt.isNullOrBlank() }
            .filterNot { it.id in handled }
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
        val now = System.currentTimeMillis()
        if (now - dueMillis > CATCH_UP_GRACE_MS) {
            markHandled(context, reminder.id)
            return
        }

        // If Celeste was closed while it became due, still fire almost immediately
        // instead of silently dropping it.
        val triggerAt = maxOf(dueMillis, now + 1_000)
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
        markHandled(context, reminder.id)
    }

    private fun handledIds(context: Context): Set<String> =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getStringSet(PREF_HANDLED_IDS, emptySet())
            ?: emptySet()

    private fun markHandled(context: Context, reminderId: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val updated = handledIds(context).toMutableSet().apply { add(reminderId) }
        prefs.edit().putStringSet(PREF_HANDLED_IDS, updated).apply()
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
