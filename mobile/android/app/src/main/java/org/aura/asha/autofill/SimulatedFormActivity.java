package org.aura.asha.autofill;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Button;
import android.widget.Toast;

import org.aura.asha.R;

/**
 * SIMULATED government-style HBNC entry screen, for demos and tests of the autofill service.
 * It is not a government app, keeps nothing and sends nothing: "Submit" only clears the screen.
 */
public class SimulatedFormActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_simulated_form);
        Button submit = findViewById(R.id.submit);
        submit.setOnClickListener(v -> {
            Toast.makeText(this, R.string.sim_form_submitted, Toast.LENGTH_LONG).show();
            startActivity(getIntent()); // fresh, empty screen
            finish();
        });
    }
}
