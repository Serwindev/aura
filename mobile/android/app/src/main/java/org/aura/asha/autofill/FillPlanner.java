package org.aura.asha.autofill;

import java.util.Locale;
import java.util.Set;

/**
 * Safety rules around the fill (pure Java, unit-tested on the JVM). Which field gets which answer is decided by
 * {@link FieldMatcher}. D-38 (demo): any app or web page may be filled, by label, but:
 *  - password / OTP / PIN / Aadhaar / captcha fields are never read or filled;
 *  - the A.U.R.A. app's own screens are never filled (except the SIMULATED practice form);
 *  - only answers she confirmed are offered; blank stays blank; she picks the suggestion and submits herself;
 *  - answers expire after 12 hours.
 */
public final class FillPlanner {
    private FillPlanner() {}

    public static final String OWN_PACKAGE = "org.aura.asha";
    public static final String SIM_ACTIVITY = OWN_PACKAGE + ".autofill.SimulatedFormActivity";

    /** Whether this screen may get a suggestion at all. */
    public static boolean screenAllowed(String packageName, String activityClass) {
        if (packageName == null) return false;
        if (packageName.equals(OWN_PACKAGE)) return SIM_ACTIVITY.equals(activityClass); // never the app itself
        return true;
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

    private static final String[] SENSITIVE_WORDS = {"password", "passwd", "pwd", "otp", "pin", "mpin", "captcha",
            "aadhaar", "aadhar", "uid", "userid", "username", "login", "पासवर्ड", "ओटीपी", "आधार"};

    /** True for password, OTP, PIN, login and similar fields: never read, never filled. */
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

    static boolean hasSensitiveWord(String s) {
        if (s == null) return false;
        String camel = s.replaceAll("([a-z])([A-Z])", "$1 $2");
        String[] tokens = FieldMatcher.norm(camel).split(" ");
        for (String t : tokens) {
            for (String w : SENSITIVE_WORDS) if (t.equals(w) || (t.startsWith(w) && w.length() > 3)) return true;
        }
        return false;
    }

    /** Answers expire so an old visit is not filled into a new screen by mistake. */
    public static final long TTL_MILLIS = 12L * 60 * 60 * 1000;

    public static boolean expired(long savedAtMillis, long nowMillis) {
        return savedAtMillis <= 0 || nowMillis - savedAtMillis > TTL_MILLIS || nowMillis < savedAtMillis;
    }

    static String lower(String s) {
        return s == null ? "" : s.toLowerCase(Locale.ROOT);
    }
}
