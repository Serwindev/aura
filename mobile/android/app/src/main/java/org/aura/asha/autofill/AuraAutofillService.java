package org.aura.asha.autofill;

import android.app.assist.AssistStructure;
import android.content.ComponentName;
import android.os.CancellationSignal;
import android.service.autofill.AutofillService;
import android.service.autofill.Dataset;
import android.service.autofill.FillCallback;
import android.service.autofill.FillContext;
import android.service.autofill.FillRequest;
import android.service.autofill.FillResponse;
import android.service.autofill.SaveCallback;
import android.service.autofill.SaveRequest;
import android.util.Pair;
import android.view.View;
import android.view.ViewStructure;
import android.view.autofill.AutofillId;
import android.view.autofill.AutofillValue;
import android.widget.RemoteViews;

import org.aura.asha.R;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

/**
 * Android Autofill service. When A.U.R.A. is her chosen autofill service and she taps a field in any app or web
 * page (Chrome with "Autofill using another service"), Android asks this service for suggestions. It matches the
 * screen's field labels to her confirmed answers (FieldMatcher) and offers ONE suggestion; nothing is filled until
 * she picks it, and she checks and submits the form herself. Password/OTP/PIN/login fields are skipped unread.
 * Nothing from the other screen is stored, logged or sent.
 */
public class AuraAutofillService extends AutofillService {

    @Override
    public void onFillRequest(FillRequest request, CancellationSignal cancellationSignal, FillCallback callback) {
        try {
            callback.onSuccess(buildResponse(request));
        } catch (RuntimeException e) {
            callback.onSuccess(null); // never break the other app; just offer nothing
        }
    }

    private FillResponse buildResponse(FillRequest request) {
        List<FillContext> contexts = request.getFillContexts();
        if (contexts == null || contexts.isEmpty()) return null;
        AssistStructure structure = contexts.get(contexts.size() - 1).getStructure();
        ComponentName comp = structure.getActivityComponent();
        if (!FillPlanner.screenAllowed(comp.getPackageName(), comp.getClassName())) return null;

        VisitStore.Visit visit = VisitStore.load(this);
        if (visit == null || visit.answers.isEmpty()) return null;

        List<FieldMatcher.Field> fields = new ArrayList<>();
        Map<String, AutofillId> ids = new HashMap<>();
        String[] lastLabel = {null};
        for (int i = 0; i < structure.getWindowNodeCount(); i++) {
            collect(structure.getWindowNodeAt(i).getRootViewNode(), fields, ids, lastLabel);
        }
        List<FieldMatcher.Fill> plan = FieldMatcher.plan(fields, visit.answers);
        if (plan.isEmpty()) return null;

        RemoteViews presentation = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
        presentation.setTextViewText(android.R.id.text1, getString(R.string.autofill_dataset_label, plan.size()));

        @SuppressWarnings("deprecation") // Dataset.Builder(RemoteViews) / setValue(id, value): API 26-compatible forms
        Dataset.Builder ds = new Dataset.Builder(presentation);
        for (FieldMatcher.Fill f : plan) {
            AutofillValue v = f.text != null ? AutofillValue.forText(f.text)
                    : f.listIndex != null ? AutofillValue.forList(f.listIndex) : AutofillValue.forToggle(f.toggle);
            //noinspection deprecation
            ds.setValue(ids.get(f.fieldKey), v);
        }
        return new FillResponse.Builder().addDataset(ds.build()).build();
    }

    /** Walks the screen in order. A plain text node (a label) is remembered for the next input field. */
    private static void collect(AssistStructure.ViewNode node, List<FieldMatcher.Field> out, Map<String, AutofillId> ids,
                                String[] lastLabel) {
        if (node == null) return;
        int type = node.getAutofillType();
        AutofillId id = node.getAutofillId();
        if (type == View.AUTOFILL_TYPE_NONE) {
            CharSequence text = node.getText();
            if (text != null && text.toString().trim().length() > 1 && node.getChildCount() == 0) lastLabel[0] = text.toString();
        } else if (id != null) {
            StringBuilder strong = new StringBuilder();
            StringBuilder weak = new StringBuilder();
            add(strong, lastLabel[0]);
            add(strong, node.getHint() == null ? null : node.getHint().toString());
            add(strong, node.getContentDescription() == null ? null : node.getContentDescription().toString());
            add(weak, node.getIdEntry());
            boolean htmlPassword = false;
            ViewStructure.HtmlInfo html = node.getHtmlInfo();
            if (html != null && html.getAttributes() != null) {
                for (Pair<String, String> a : html.getAttributes()) {
                    String k = a.first == null ? "" : a.first.toLowerCase(java.util.Locale.ROOT);
                    if (k.equals("label") || k.equals("placeholder") || k.equals("aria-label") || k.equals("title")) add(strong, a.second);
                    else if (k.equals("name") || k.equals("id")) add(weak, a.second);
                    else if (k.equals("type") && "password".equalsIgnoreCase(a.second)) htmlPassword = true;
                }
            }
            String[] hints = node.getAutofillHints();
            boolean sensitive = htmlPassword || FillPlanner.isSensitive(node.getInputType(), weak.toString(), strong.toString(),
                    hints == null ? null : new HashSet<>(Arrays.asList(hints)));
            lastLabel[0] = null; // a label belongs to the one field after it
            if (!sensitive && (type == View.AUTOFILL_TYPE_TEXT || type == View.AUTOFILL_TYPE_LIST || type == View.AUTOFILL_TYPE_TOGGLE)) {
                List<String> options = new ArrayList<>();
                CharSequence[] opts = node.getAutofillOptions();
                if (opts != null) for (CharSequence o : opts) options.add(o == null ? "" : o.toString());
                String key = String.valueOf(out.size());
                out.add(new FieldMatcher.Field(key, type, strong.toString(), weak.toString(), options));
                ids.put(key, id);
            }
        }
        for (int i = 0; i < node.getChildCount(); i++) collect(node.getChildAt(i), out, ids, lastLabel);
    }

    private static void add(StringBuilder b, String s) {
        if (s != null && !s.trim().isEmpty()) b.append(' ').append(s);
    }

    @Override
    public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        callback.onSuccess(); // A.U.R.A. never saves what she types in other apps
    }
}
