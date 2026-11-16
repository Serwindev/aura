package org.aura.asha.autofill;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Build;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import org.aura.asha.R;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * SIMULATED government-style data-entry screen, built from the form the ASHA has open in A.U.R.A. (HBNC, SSBSK,
 * RCH child tracking). For demos of the autofill service: labels sit above each field and view ids are generated,
 * so autofill must find fields by label, as in a real app. Not a government app: it keeps and sends nothing.
 */
public class SimulatedFormActivity extends Activity {
    public static final String EXTRA_FORM = "form";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        int pad = dp(16);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(pad, pad, pad, pad);

        TextView banner = text(getString(R.string.sim_form_banner), 14, true);
        banner.setBackgroundColor(Color.parseColor("#FFE9A8"));
        banner.setTextColor(Color.parseColor("#5E3F00"));
        banner.setPadding(dp(10), dp(8), dp(10), dp(8));
        col.addView(banner);

        JSONObject form = null;
        try {
            String raw = getIntent().getStringExtra(EXTRA_FORM);
            if (raw != null) form = new JSONObject(raw);
        } catch (JSONException ignored) { /* shown as "open from a form" below */ }

        if (form == null) {
            col.addView(text(getString(R.string.sim_form_open_from_app), 16, false));
        } else {
            col.addView(text(form.optString("title"), 20, true));
            col.addView(text(getString(R.string.sim_form_help), 14, false));
            // a login box like real apps have: A.U.R.A. must never fill it
            col.addView(section(getString(R.string.sim_form_login)));
            col.addView(text(getString(R.string.sim_form_pin), 15, false));
            EditText pin = new EditText(this);
            pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
            pin.setId(View.generateViewId());
            col.addView(pin);
            JSONArray sections = form.optJSONArray("sections");
            for (int i = 0; sections != null && i < sections.length(); i++) {
                JSONObject s = sections.optJSONObject(i);
                if (s == null) continue;
                col.addView(section(s.optString("title")));
                JSONArray rows = s.optJSONArray("rows");
                for (int k = 0; rows != null && k < rows.length(); k++) addRow(col, rows.optJSONObject(k));
            }
            Button submit = new Button(this);
            submit.setText(R.string.sim_form_submit);
            submit.setOnClickListener(v -> {
                Toast.makeText(this, R.string.sim_form_submitted, Toast.LENGTH_LONG).show();
                recreate(); // fresh, empty screen
            });
            col.addView(submit);
            // start with no field focused (otherwise the cursor lands in the PIN box, which autofill must skip)
            col.setFocusableInTouchMode(true);
            col.requestFocus();
        }

        ScrollView scroll = new ScrollView(this);
        scroll.addView(col);
        ViewCompat.setOnApplyWindowInsetsListener(scroll, (v, insets) -> { // keep clear of the status/navigation bars
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        setContentView(scroll);
    }

    private void addRow(LinearLayout col, JSONObject r) {
        if (r == null) return;
        String en = r.optString("label_en"), local = r.optString("question");
        String label = local.isEmpty() || local.equals(en) ? en : en + " / " + local;
        TextView lbl = text(label, 15, false);
        // like a labelled field in a real app: the label is part of what Android shows the autofill service
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) lbl.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_YES);
        col.addView(lbl);
        String input = r.optString("input", "text");
        View field;
        if ("yesno".equals(input)) {
            Spinner sp = new Spinner(this);
            ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item,
                    new String[]{"-- Select --", "Yes", "No"});
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ad.setAutofillOptions("-- Select --", "Yes", "No"); // lets autofill pick Yes/No
            sp.setAdapter(ad);
            sp.setContentDescription(en);
            field = sp;
        } else {
            EditText et = new EditText(this);
            if ("number".equals(input)) et.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
            else et.setInputType(InputType.TYPE_CLASS_TEXT);
            et.setHint("date".equals(input) ? "dd-mm-yyyy" : en);
            // Android strips label text set at runtime from what autofill sees; the field's own description is kept
            et.setContentDescription(en);
            field = et;
        }
        field.setId(View.generateViewId());
        col.addView(field, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private TextView section(String title) {
        TextView t = text(title, 17, true);
        t.setPadding(0, dp(18), 0, dp(4));
        return t;
    }

    private TextView text(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(6), 0, dp(2));
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
