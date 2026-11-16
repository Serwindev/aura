package org.aura.asha;

import android.os.Bundle;
import android.webkit.WebView;

import androidx.activity.OnBackPressedCallback;

import com.getcapacitor.BridgeActivity;

import org.aura.asha.autofill.AuraAutofillPlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AuraAutofillPlugin.class);
        super.onCreate(savedInstanceState);
        // Android back button: the web app is one page, so ask it to go one screen back (window.auraBack in app.js).
        // On Home or Login it returns false and the app goes to the background instead of closing.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                WebView wv = getBridge() == null ? null : getBridge().getWebView();
                if (wv == null) { moveTaskToBack(true); return; }
                wv.evaluateJavascript("(typeof auraBack === 'function' && auraBack()) ? 'y' : 'n'", v -> {
                    if (!"\"y\"".equals(v)) moveTaskToBack(true);
                });
            }
        });
    }
}
