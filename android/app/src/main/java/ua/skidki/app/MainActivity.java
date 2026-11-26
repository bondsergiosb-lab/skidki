package ua.skidki.app;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

/** Показывает сайт со скидками. Ссылки на магазины открываются в браузере или в приложении магазина. */
public class MainActivity extends Activity {

    static final String EXTRA_HOT = "hot";  // id товаров из уведомления, через запятую

    private static final String OFFLINE = "<html><body style='font-family:sans-serif;text-align:center;padding:40% 24px;color:#333'>"
            + "<h2>Нет интернета</h2><p>Проверьте подключение и попробуйте ещё раз.</p>"
            + "<p><a href='%s' style='display:inline-block;background:#e8457a;color:#fff;padding:12px 28px;"
            + "border-radius:12px;text-decoration:none'>Повторить</a></p></body></html>";

    private WebView web;
    private String home;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        home = getString(R.string.app_url);
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // настройки и избранное хранятся в localStorage
        s.setDatabaseEnabled(true);
        s.setUserAgentString(s.getUserAgentString() + " SkidkiApp/2");
        web.addJavascriptInterface(new Bridge(this), "SkidkiApp");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (url.toString().startsWith(home)) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (ActivityNotFoundException ignored) {
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    view.loadDataWithBaseURL(null, String.format(OFFLINE, home), "text/html", "utf-8", null);
                }
            }
        });

        String hot = getIntent().getStringExtra(EXTRA_HOT);
        if (hot != null) web.loadUrl(home + "#hot=" + Uri.encode(hot));
        else if (state != null) web.restoreState(state);
        else web.loadUrl(home);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String hot = intent.getStringExtra(EXTRA_HOT);
        if (hot == null) return;
        String js = "window.showHot ? (window.showHot(" + JSONObject.quote(hot) + "), true) : false";
        web.evaluateJavascript(js, result -> {
            if (!"true".equals(result)) web.loadUrl(home + "#hot=" + Uri.encode(hot));
        });
    }

    /** Android 13+: уведомления нужно разрешить. Спрашиваем, когда в настройках выбрали профиль для уведомлений. */
    void askNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        web.evaluateJavascript("window.renderNotify && document.querySelector('#view-settings.active') && window.renderNotify()", null);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        // сначала даём странице закрыть открытую шторку или вернуться на главный экран
        web.evaluateJavascript("window.appBack ? window.appBack() : false", result -> {
            if ("true".equals(result)) return;
            if (web.canGoBack()) web.goBack();
            else finish();
        });
    }
}
