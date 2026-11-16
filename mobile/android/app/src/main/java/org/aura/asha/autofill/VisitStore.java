package org.aura.asha.autofill;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;

/** The one visit that is ready to autofill: confirmed answers only, kept on this phone (app-private storage, not backed up). */
public final class VisitStore {
    private static final String PREFS = "aura_autofill";
    private static final String KEY = "visit";

    public static final class Visit {
        public final String noteId;
        public final String title;
        public final long savedAt;
        public final Map<String, String> answers; // form row id -> value

        Visit(String noteId, String title, long savedAt, Map<String, String> answers) {
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

    /** @param fields array of {id, value}; rows without a value are dropped (blank stays blank). */
    public static int save(Context c, String noteId, String title, JSONArray fields) throws JSONException {
        JSONObject answers = new JSONObject();
        int n = 0;
        for (int i = 0; i < fields.length(); i++) {
            JSONObject f = fields.getJSONObject(i);
            String id = f.optString("id", "");
            String value = f.isNull("value") ? "" : f.optString("value", "");
            if (id.isEmpty() || value.trim().isEmpty()) continue;
            answers.put(id, value);
            n++;
        }
        JSONObject o = new JSONObject();
        o.put("noteId", noteId);
        o.put("title", title);
        o.put("savedAt", System.currentTimeMillis());
        o.put("answers", answers);
        prefs(c).edit().putString(KEY, o.toString()).apply();
        return n;
    }

    public static Visit load(Context c) {
        String raw = prefs(c).getString(KEY, null);
        if (raw == null) return null;
        try {
            JSONObject o = new JSONObject(raw);
            long savedAt = o.optLong("savedAt", 0);
            if (FillPlanner.expired(savedAt, System.currentTimeMillis())) {
                clear(c);
                return null;
            }
            JSONObject a = o.getJSONObject("answers");
            Map<String, String> answers = new LinkedHashMap<>();
            JSONArray names = a.names();
            if (names != null) for (int i = 0; i < names.length(); i++) answers.put(names.getString(i), a.getString(names.getString(i)));
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
