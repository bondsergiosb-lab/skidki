package ua.skidki.app;

import android.webkit.JavascriptInterface;

/** То, что страница может попросить у приложения: window.SkidkiApp.* */
final class Bridge {
    private final MainActivity activity;

    Bridge(MainActivity activity) {
        this.activity = activity;
    }

    /** Профиль (JSON из app.js), для которого присылать уведомления; пустая строка — не присылать. */
    @JavascriptInterface
    public void setNotify(String profileJson) {
        Notifier.setProfile(activity.getApplicationContext(), profileJson);
        if (profileJson != null && !profileJson.isEmpty()) activity.runOnUiThread(activity::askNotificationPermission);
    }

    @JavascriptInterface
    public boolean permissionGranted() {
        return Notifier.permissionGranted(activity);
    }

    /** Кнопка «Прислать сейчас»: проверочное уведомление по сегодняшним данным. */
    @JavascriptInterface
    public void sendNow() {
        Notifier.runJob(activity.getApplicationContext(), true, 0);
    }
}
