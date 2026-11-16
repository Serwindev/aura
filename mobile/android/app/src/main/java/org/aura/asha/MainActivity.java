package org.aura.asha;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

import org.aura.asha.autofill.AuraAutofillPlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AuraAutofillPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
