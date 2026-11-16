package org.aura.asha.autofill;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Finds which confirmed answer belongs in which field of ANY screen, by the field's label — the way a password
 * manager recognises a "username" box (D-38). Pure Java (no Android types), unit-tested on the JVM.
 *
 * Rules: a field gets an answer only when one of that answer's label words (English or Hindi) is in the field's
 * label/hint/name; each field and each answer is used at most once (best match first); blank answers are never
 * offered; sensitive fields (password, OTP, PIN…) are removed by the caller before they get here.
 */
public final class FieldMatcher {
    private FieldMatcher() {}

    /** Same numbers as android.view.View.AUTOFILL_TYPE_*. */
    public static final int TYPE_TEXT = 1, TYPE_TOGGLE = 2, TYPE_LIST = 3;

    public static final class Answer {
        public final String id, fill, input; // input: text | number | date | yesno
        public final List<String> words;

        public Answer(String id, String fill, String input, List<String> words) {
            this.id = id;
            this.fill = fill;
            this.input = input == null ? "text" : input;
            this.words = words == null ? Collections.<String>emptyList() : words;
        }
    }

    public static final class Field {
        public final String key;
        public final int type;
        public final String strong; // label, hint, placeholder, content description (what she reads)
        public final String weak;   // view id / html name / html id (what the developer named it)
        public final List<String> options; // list fields (dropdowns)

        public Field(String key, int type, String strong, String weak, List<String> options) {
            this.key = key;
            this.type = type;
            this.strong = strong == null ? "" : strong;
            this.weak = weak == null ? "" : weak;
            this.options = options == null ? Collections.<String>emptyList() : options;
        }
    }

    public static final class Fill {
        public final String fieldKey, answerId;
        public final String text;       // TEXT fields
        public final Integer listIndex; // LIST fields
        public final Boolean toggle;    // TOGGLE fields

        Fill(String fieldKey, String answerId, String text, Integer listIndex, Boolean toggle) {
            this.fieldKey = fieldKey;
            this.answerId = answerId;
            this.text = text;
            this.listIndex = listIndex;
            this.toggle = toggle;
        }
    }

    private static final Set<String> YES = new HashSet<>(Arrays.asList("yes", "y", "haan", "han", "हाँ", "हां", "true", "1"));
    private static final Set<String> NO = new HashSet<>(Arrays.asList("no", "n", "nahin", "nahi", "नहीं", "नही", "false", "0"));

    /** Lower case, Devanagari folded (nukta dropped, ँ→ं), punctuation → space, single spaces. */
    public static String norm(String s) {
        if (s == null) return "";
        String t = Normalizer.normalize(s, Normalizer.Form.NFD).replace("़", "").replace('ँ', 'ं');
        t = Normalizer.normalize(t, Normalizer.Form.NFC).toLowerCase(Locale.ROOT).replace("'", "");
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < t.length(); i++) {
            char c = t.charAt(i);
            int type = Character.getType(c);
            boolean keep = Character.isLetterOrDigit(c) || type == Character.NON_SPACING_MARK || type == Character.COMBINING_SPACING_MARK;
            b.append(keep ? c : ' ');
        }
        return b.toString().trim().replaceAll("\\s+", " ");
    }

    /** Score of one label word in one text (0 = absent). Longer words and words at the start of the label win. */
    static int score(String text, String word) {
        String t = norm(text), w = norm(word);
        if (w.isEmpty() || t.isEmpty()) return 0;
        String compactW = w.replace(" ", "");
        boolean hit = (" " + t + " ").contains(" " + w + " ");
        // "OPV-1", "opv1", "OPV 1" are the same label
        if (!hit && compactW.length() >= 4 && compactW.matches("[a-z0-9]+")) hit = t.replace(" ", "").contains(compactW);
        if (!hit) return 0;
        int s = 10 + compactW.length();
        if (t.startsWith(w) || t.replace(" ", "").startsWith(compactW)) s += 3;
        return s;
    }

    private static int best(Field f, Answer a) {
        int top = 0;
        for (String w : a.words) {
            int strong = score(f.strong, w);
            int weak = score(f.weak, w);
            top = Math.max(top, Math.max(strong, weak > 0 ? weak - 6 : 0)); // a developer's id counts less than a label
        }
        return top;
    }

    /** @return fills in field order; empty when nothing matches. */
    public static List<Fill> plan(List<Field> fields, List<Answer> answers) {
        List<int[]> pairs = new ArrayList<>(); // {score, fieldIndex, answerIndex}
        for (int i = 0; i < fields.size(); i++) {
            for (int j = 0; j < answers.size(); j++) {
                Answer a = answers.get(j);
                if (a.fill == null || a.fill.trim().isEmpty()) continue; // blank stays blank
                int s = best(fields.get(i), a);
                if (s > 0) pairs.add(new int[]{s, i, j});
            }
        }
        pairs.sort((x, y) -> x[0] != y[0] ? y[0] - x[0] : x[1] != y[1] ? x[1] - y[1] : x[2] - y[2]);
        Fill[] byField = new Fill[fields.size()];
        Set<Integer> usedAnswers = new HashSet<>();
        for (int[] p : pairs) {
            if (byField[p[1]] != null || usedAnswers.contains(p[2])) continue;
            Fill f = valueFor(fields.get(p[1]), answers.get(p[2]));
            if (f == null) continue;
            byField[p[1]] = f;
            usedAnswers.add(p[2]);
        }
        List<Fill> out = new ArrayList<>();
        for (Fill f : byField) if (f != null) out.add(f);
        return out;
    }

    private static Fill valueFor(Field f, Answer a) {
        String v = a.fill.trim();
        boolean yesNo = "yesno".equals(a.input);
        if (f.type == TYPE_TEXT) return new Fill(f.key, a.id, v, null, null);
        if (f.type == TYPE_TOGGLE) {
            if (!yesNo) return null;
            return new Fill(f.key, a.id, null, null, YES.contains(norm(v)));
        }
        if (f.type == TYPE_LIST) {
            Integer idx = null;
            for (int i = 0; i < f.options.size() && idx == null; i++) {
                String o = norm(f.options.get(i));
                if (yesNo ? (YES.contains(norm(v)) ? YES.contains(o) : NO.contains(o)) : o.equals(norm(v))) idx = i;
            }
            return idx == null ? null : new Fill(f.key, a.id, null, idx, null);
        }
        return null; // date pickers and other types: she fills them herself
    }
}
