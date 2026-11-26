package ua.skidki.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Утренний будильник → задача с уведомлением. После перезагрузки телефона будильник ставится заново. */
public class AlarmReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) {
            Notifier.schedule(context);
            return;
        }
        Notifier.prefs(context).edit().putInt("retries", 0).apply();
        Notifier.runJob(context, false, 0);
    }
}
