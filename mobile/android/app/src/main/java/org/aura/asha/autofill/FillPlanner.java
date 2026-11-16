package org.aura.asha.autofill;

import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Decides what (if anything) to fill on a screen. Pure Java, no Android types, so it is unit-tested on the JVM.
 * Rules (docs/decisions/003-autofill.md, condition 3–5):
 *  - only allow-listed screens (package + activity class);
 *  - the screen's field ids must all be known for that layout, else the layout changed and nothing is filled;
 *  - password / OTP / PIN / captcha fields are never filled (callers skip them before they reach here);
 *  - only rows the ASHA confirmed (non-blank values) are filled; blank stays blank.
 */
public final class FillPlanner {

    /** One allow-listed screen: field id (Android resource entry name) to HBNC form row id; null = known but never filled. */
    public static final class ScreenLayout {
        public final String packageName;
        public final String activityClass;
        public final Map<String, String> fieldToRow;

        public ScreenLayout(String packageName, String activityClass, Map<String, String> fieldToRow) {
            this.packageName = packageName;
            this.activityClass = activityClass;
            this.fieldToRow = Collections.unmodifiableMap(fieldToRow);
        }
    }

    private FillPlanner() {}

    public static final String OWN_PACKAGE = "org.aura.asha";

    /**
     * The allow-list. Only the built-in SIMULATED test form is on it: the terms of e-Kavach / other government apps
     * have not been checked yet (D-34 condition 1), so no government app is listed. Adding one needs a decision entry.
     */
    public static final List<ScreenLayout> ALLOW_LIST = Collections.singletonList(simulatedHbncForm());

    private static ScreenLayout simulatedHbncForm() {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("visit_date", "date");
        m.put("visit_day", "day");
        m.put("baby_weight", "C2");
        m.put("baby_temp", "C3");
        m.put("jaundice", "C4");
        m.put("bcg", "C5");
        m.put("opv", "C6");
        m.put("hepb", "C7");
        m.put("feeding_ok", "A5");
        m.put("referred", "D1");
        m.put("beneficiary_id", null); // she types this herself
        m.put("remarks", null);
        return new ScreenLayout(OWN_PACKAGE, OWN_PACKAGE + ".autofill.SimulatedFormActivity", m);
    }

    public static ScreenLayout find(String packageName, String activityClass) {
        for (ScreenLayout s : ALLOW_LIST) {
            if (s.packageName.equals(packageName) && s.activityClass.equals(activityClass)) return s;
        }
        return null;
    }

    /**
     * @param layout   the allow-listed layout for this screen
     * @param fieldIds non-sensitive text field ids found on the screen
     * @param answers  confirmed answers: form row id to value
     * @return field id to value; empty when there is nothing to fill or the screen does not match the layout
     */
    public static Map<String, String> plan(ScreenLayout layout, List<String> fieldIds, Map<String, String> answers) {
        if (layout == null || fieldIds == null || fieldIds.isEmpty() || answers == null || answers.isEmpty()) {
            return Collections.emptyMap();
        }
        for (String id : fieldIds) {
            if (id == null || !layout.fieldToRow.containsKey(id)) return Collections.emptyMap(); // layout changed: stop
        }
        Map<String, String> out = new LinkedHashMap<>();
        for (String id : fieldIds) {
            String row = layout.fieldToRow.get(id);
            if (row == null) continue;
            String v = answers.get(row);
            if (v != null && !v.trim().isEmpty()) out.put(id, v);
        }
        return out;
    }

    // InputType constants copied as literals so this class needs no Android classes.
    private static final int TYPE_MASK_CLASS = 0x0000000f;
    private static final int TYPE_MASK_VARIATION = 0x00000ff0;
    private static final int TYPE_CLASS_TEXT = 0x00000001;
    private static final int TYPE_CLASS_NUMBER = 0x00000002;
    private static final int TYPE_TEXT_VARIATION_PASSWORD = 0x00000080;
    private static final int TYPE_TEXT_VARIATION_VISIBLE_PASSWORD = 0x00000090;
    private static final int TYPE_TEXT_VARIATION_WEB_PASSWORD = 0x000000e0;
    private static final int TYPE_NUMBER_VARIATION_PASSWORD = 0x00000010;

    private static final String[] SENSITIVE_WORDS = {"password", "passwd", "otp", "pin", "captcha", "aadhaar", "aadhar", "mpin"};

    /** True for password, OTP, PIN and similar fields: never read, never filled. */
    public static boolean isSensitive(int inputType, String idEntry, String hint, Set<String> autofillHints) {
        int cls = inputType & TYPE_MASK_CLASS;
        int var = inputType & TYPE_MASK_VARIATION;
        if (cls == TYPE_CLASS_TEXT && (var == TYPE_TEXT_VARIATION_PASSWORD || var == TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
                || var == TYPE_TEXT_VARIATION_WEB_PASSWORD)) return true;
        if (cls == TYPE_CLASS_NUMBER && var == TYPE_NUMBER_VARIATION_PASSWORD) return true;
        if (hasSensitiveWord(idEntry) || hasSensitiveWord(hint)) return true;
        if (autofillHints != null) {
            for (String h : autofillHints) if (hasSensitiveWord(h)) return true;
        }
        return false;
    }

    private static boolean hasSensitiveWord(String s) {
        if (s == null) return false;
        String[] tokens = s.toLowerCase(Locale.ROOT).split("[^a-z0-9]+");
        for (String t : tokens) {
            for (String w : SENSITIVE_WORDS) if (t.equals(w) || t.startsWith(w) && w.length() > 3) return true;
        }
        // camelCase ids such as loginPin / otpCode
        String camel = s.replaceAll("([a-z])([A-Z])", "$1 $2").toLowerCase(Locale.ROOT);
        if (!camel.equals(s.toLowerCase(Locale.ROOT))) return hasSensitiveWord(camel);
        return false;
    }

    /** Answers expire so an old visit is not filled into a new screen by mistake. */
    public static final long TTL_MILLIS = 12L * 60 * 60 * 1000;

    public static boolean expired(long savedAtMillis, long nowMillis) {
        return savedAtMillis <= 0 || nowMillis - savedAtMillis > TTL_MILLIS || nowMillis < savedAtMillis;
    }

    static Map<String, String> mapOf(String... kv) {
        Map<String, String> m = new HashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put(kv[i], kv[i + 1]);
        return m;
    }
}
