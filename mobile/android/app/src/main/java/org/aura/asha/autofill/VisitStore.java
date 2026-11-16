package org.aura.asha.autofill;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** The one form that is ready to autofill: confirmed answers only, kept on this phone (app-private, not backed up). */
public final class VisitStore {
    private static final String PREFS = "aura_autofill";
    private static final String KEY = "visit";

    public static final class Visit {
        public final String noteId, title;
        public final long savedAt;
        public final List<FieldMatcher.Answer> answers;

        Visit(String noteId, String title, long savedAt, List<FieldMatcher.Answer> answers) {
            this.noteId = noteId;
            this.title = title;
            this.savedAt = savedAt;
            this.answers = answers;
        }
    }

    private VisitStore() {}

    private static SharedPreferences prefs(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** @param fields array of {id, fill, input, match[]}; rows without a fill value are dropped (blank stays blank). */
    public static int save(Context c, String noteId, String title, JSONArray fields) throws JSONException {
        JSONArray kept = new JSONArray();
        for (int i = 0; i < fields.length(); i++) {
            JSONObject f = fields.getJSONObject(i);
            String fill = f.isNull("fill") ? "" : f.optString("fill", "");
            if (f.optString("id", "").isEmpty() || fill.trim().isEmpty()) continue;
            JSONObject a = new JSONObject();
            a.put("id", f.getString("id"));
            a.put("fill", fill);
            a.put("input", f.optString("input", "text"));
            a.put("match", f.optJSONArray("match") == null ? new JSONArray() : f.getJSONArray("match"));
            kept.put(a);
        }
        JSONObject o = new JSONObject();
        o.put("noteId", noteId);
        o.put("title", title);
        o.put("savedAt", System.currentTimeMillis());
        o.put("answers", kept);
        prefs(c).edit().putString(KEY, o.toString()).apply();
        return kept.length();
    }

    public static Visit load(Context c) {
        String raw = prefs(c).getString(KEY, null);
        if (raw == null) return null;
        try {
            JSONObject o = new JSONObject(raw);
            long savedAt = o.optLong("savedAt", 0);
            JSONArray arr = o.optJSONArray("answers");
            if (FillPlanner.expired(savedAt, System.currentTimeMillis()) || arr == null) {
                clear(c);
                return null;
            }
            List<FieldMatcher.Answer> answers = new ArrayList<>();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject a = arr.getJSONObject(i);
                List<String> words = new ArrayList<>();
                JSONArray m = a.optJSONArray("match");
                if (m != null) for (int k = 0; k < m.length(); k++) words.add(m.getString(k));
                answers.add(new FieldMatcher.Answer(a.getString("id"), a.getString("fill"), a.optString("input"), words));
            }
            return new Visit(o.optString("noteId"), o.optString("title"), savedAt, answers);
        } catch (JSONException e) {
            clear(c);
            return null;
        }
    }

    public static void clear(Context c) {
        prefs(c).edit().remove(KEY).apply();
    }
}
