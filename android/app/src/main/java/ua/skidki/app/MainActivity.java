package ua.skidki.app;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Показывает сайт со скидками. Ссылки на магазины открываются в браузере или в приложении магазина. */
public class MainActivity extends Activity {

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
        s.setUserAgentString(s.getUserAgentString() + " SkidkiApp/1");

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

        if (state != null) web.restoreState(state);
        else web.loadUrl(home);
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
