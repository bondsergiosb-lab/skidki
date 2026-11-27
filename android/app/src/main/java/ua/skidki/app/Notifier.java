package ua.skidki.app;

import android.Manifest;
import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileNotFoundException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.NumberFormat;
import java.util.Calendar;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Ежедневное уведомление «20 горящих скидок». Профиль приходит из страницы (Bridge.setNotify) и хранится здесь,
 * в SharedPreferences. Каждый день в 9 утра будильник запускает задачу: скачать deals.json, отобрать скидки, показать.
 */
final class Notifier {
    static final String TAG = "Skidki";
    static final int COUNT = 20;
    private static final String PREFS = "notify";
    private static final String CHANNEL = "hot";
    private static final int HOUR = 9;               // скидки собираются ночью; GitHub иногда запаздывает
    private static final int MAX_RETRIES = 5;        // данные ещё не обновились — пробуем через 2 часа, до 19:00
    private static final int MAX_SENT = 800;
    static final int JOB_DAILY = 1, JOB_NOW = 2, JOB_RETRY = 3;

    private Notifier() {
    }

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static void setProfile(Context c, String profileJson) {
        prefs(c).edit().putString("profile", profileJson == null ? "" : profileJson).apply();
        schedule(c);
    }

    static boolean permissionGranted(Context c) {
        if (Build.VERSION.SDK_INT >= 33
                && c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return false;
        }
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        return nm == null || nm.areNotificationsEnabled();
    }

    /** Будильник на 9:00 каждый день (неточный — система может сдвинуть, зато бережёт батарею). */
    static void schedule(Context c) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        PendingIntent pi = PendingIntent.getBroadcast(c, 0, new Intent(c, AlarmReceiver.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        am.cancel(pi);
        if (prefs(c).getString("profile", "").isEmpty()) return;
        Calendar at = Calendar.getInstance();
        at.set(Calendar.HOUR_OF_DAY, HOUR);
        at.set(Calendar.MINUTE, 0);
        at.set(Calendar.SECOND, 0);
        if (at.getTimeInMillis() <= System.currentTimeMillis()) at.add(Calendar.DAY_OF_YEAR, 1);
        am.setInexactRepeating(AlarmManager.RTC_WAKEUP, at.getTimeInMillis(), AlarmManager.INTERVAL_DAY, pi);
    }

    /** Задача с интернетом: now — кнопка «Прислать сейчас», delayMs — повтор, если данные ещё не обновились. */
    static void runJob(Context c, boolean now, long delayMs) {
        // у повтора свой номер: задача с тем же номером, поставленная изнутри работающей, остановила бы её
        int id = now ? JOB_NOW : delayMs > 0 ? JOB_RETRY : JOB_DAILY;
        JobInfo.Builder b = new JobInfo.Builder(id, new ComponentName(c, DealsJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY);
        if (delayMs > 0) b.setMinimumLatency(delayMs);
        c.getSystemService(JobScheduler.class).schedule(b.build());
    }

    /** Основная работа; выполняется в фоновом потоке DealsJob. */
    static void work(Context c, boolean now) throws Exception {
        SharedPreferences sp = prefs(c);
        String profileJson = sp.getString("profile", "");
        if (profileJson.isEmpty()) return;
        JSONObject profile = new JSONObject(profileJson);
        String base = c.getString(R.string.app_url) + "data/";
        JSONObject data;
        boolean whole = false;  // старый формат данных: всё одним файлом deals.json
        try {
            data = new JSONObject(download(base + "meta.json"));
        } catch (FileNotFoundException e) {
            data = new JSONObject(download(base + "deals.json"));
            whole = true;
        }
        String generated = data.optString("generated");

        if (!now && generated.equals(sp.getString("generated", ""))) {
            int retries = sp.getInt("retries", 0);
            if (retries < MAX_RETRIES) {
                sp.edit().putInt("retries", retries + 1).apply();
                runJob(c, false, 2 * 3600_000L);
            }
            return;
        }

        JSONArray items = whole ? data.getJSONArray("items") : new JSONArray();
        if (!whole) {  // только части данных, нужные профилю: женское, мужское, детское
            Set<String> ids = new HashSet<>();
            for (String shard : Deals.shards(profile)) {
                JSONArray part = new JSONObject(download(base + shard + ".json")).getJSONArray("items");
                for (int i = 0; i < part.length(); i++) {
                    JSONObject it = part.getJSONObject(i);
                    if (ids.add(it.optString("id"))) items.put(it);
                }
            }
        }
        Map<String, Double> sent = loadSent(sp);
        List<JSONObject> hot = Deals.pick(items, profile, sent, COUNT);
        if (!now) sp.edit().putString("generated", generated).putInt("retries", 0).apply();
        if (hot.isEmpty()) {
            if (now) show(c, profile, hot, data);
            return;
        }
        show(c, profile, hot, data);
        if (!now) {  // проверочное уведомление не считается — иначе завтра эти скидки не придут
            for (JSONObject it : hot) {
                sent.remove(it.optString("id"));  // в конец списка — чтобы при обрезке ушли самые старые
                sent.put(it.optString("id"), it.optDouble("p"));
            }
            saveSent(sp, sent);
        }
    }

    private static void show(Context c, JSONObject profile, List<JSONObject> hot, JSONObject data) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Горящие скидки", NotificationManager.IMPORTANCE_DEFAULT));
        }
        String name = profile.optString("name", "");
        String title;
        StringBuilder ids = new StringBuilder();
        Notification.InboxStyle inbox = new Notification.InboxStyle();
        JSONObject stores = data.optJSONObject("stores");
        NumberFormat money = NumberFormat.getIntegerInstance(new Locale("uk", "UA"));
        for (int i = 0; i < hot.size(); i++) {
            JSONObject it = hot.get(i);
            if (ids.length() > 0) ids.append(',');
            ids.append(it.optString("id"));
            if (i < 7) {
                JSONObject st = stores == null ? null : stores.optJSONObject(it.optString("s"));
                inbox.addLine("−" + it.optInt("r") + "% · " + money.format(Math.round(it.optDouble("p"))) + " ₴ · "
                        + it.optString("t") + (st != null ? " — " + st.optString("name") : ""));
            }
        }
        if (hot.isEmpty()) {
            title = (name.isEmpty() ? "" : name + ", ") + "сегодня новых горящих скидок по вашему выбору нет";
        } else {
            title = (name.isEmpty() ? "" : name + ", ") + "сегодня " + hot.size() + " " + plural(hot.size()) + " 🔥";
            if (hot.size() > 7) inbox.setSummaryText("и ещё " + (hot.size() - 7) + " — нажмите, чтобы посмотреть");
        }
        inbox.setBigContentTitle(title);

        Intent open = new Intent(c, MainActivity.class).putExtra(MainActivity.EXTRA_HOT, ids.toString())
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(c, 1, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder nb = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, CHANNEL) : legacyBuilder(c);
        nb.setSmallIcon(R.drawable.ic_notify)
                .setColor(0xFFE8457A)
                .setContentTitle(title)
                .setContentText(hot.isEmpty() ? "Загляните завтра или ослабьте фильтры профиля"
                        : "−" + hot.get(0).optInt("r") + "% · " + hot.get(0).optString("t"))
                .setStyle(hot.isEmpty() ? null : inbox)
                .setContentIntent(pi)
                .setAutoCancel(true);
        try {
            nm.notify(1, nb.build());
        } catch (SecurityException e) {  // уведомления запрещены
            Log.w(TAG, "нет разрешения на уведомления", e);
        }
    }

    @SuppressWarnings("deprecation")
    private static Notification.Builder legacyBuilder(Context c) {
        return new Notification.Builder(c);
    }

    private static String plural(int n) {
        int m10 = n % 10, m100 = n % 100;
        if (m10 == 1 && m100 != 11) return "горящая скидка";
        if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "горящие скидки";
        return "горящих скидок";
    }

    private static Map<String, Double> loadSent(SharedPreferences sp) {
        Map<String, Double> m = new LinkedHashMap<>();
        try {
            JSONArray arr = new JSONArray(sp.getString("sent", "[]"));
            for (int i = 0; i < arr.length(); i++) {
                JSONArray pair = arr.getJSONArray(i);
                m.put(pair.getString(0), pair.getDouble(1));
            }
        } catch (Exception ignored) {
        }
        return m;
    }

    private static void saveSent(SharedPreferences sp, Map<String, Double> m) {
        JSONArray arr = new JSONArray();
        int skip = Math.max(0, m.size() - MAX_SENT);  // храним последние MAX_SENT
        for (Map.Entry<String, Double> e : m.entrySet()) {
            if (skip-- > 0) continue;
            arr.put(new JSONArray().put(e.getKey()).put(e.getValue()));
        }
        sp.edit().putString("sent", arr.toString()).apply();
    }

    private static String download(String url) throws Exception {
        HttpURLConnection con = (HttpURLConnection) new URL(url).openConnection();
        con.setConnectTimeout(20000);
        con.setReadTimeout(60000);
        con.setUseCaches(false);
        try (InputStream in = con.getInputStream()) {
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] chunk = new byte[64 * 1024];
            for (int n; (n = in.read(chunk)) > 0; ) buf.write(chunk, 0, n);
            return buf.toString(StandardCharsets.UTF_8.name());
        } finally {
            con.disconnect();
        }
    }
}
