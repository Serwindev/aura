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
import android.view.View;
import android.view.autofill.AutofillId;
import android.view.autofill.AutofillValue;
import android.widget.RemoteViews;

import org.aura.asha.R;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Android Autofill service (D-34 ladder step 3). Android calls this when she taps a field in another screen and
 * A.U.R.A. is her chosen autofill service. It offers one suggestion, "A.U.R.A. visit"; nothing is filled unless she
 * picks it, and she saves/submits the form herself. Nothing from the other screen is stored, logged or sent.
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
        FillPlanner.ScreenLayout layout = FillPlanner.find(comp.getPackageName(), comp.getClassName());
        if (layout == null) return null; // not allow-listed: offer nothing

        VisitStore.Visit visit = VisitStore.load(this);
        if (visit == null) return null;

        Map<String, AutofillId> ids = new LinkedHashMap<>();
        for (int i = 0; i < structure.getWindowNodeCount(); i++) collect(structure.getWindowNodeAt(i).getRootViewNode(), ids);
        Map<String, String> plan = FillPlanner.plan(layout, new ArrayList<>(ids.keySet()), visit.answers);
        if (plan.isEmpty()) return null;

        String label = getString(R.string.autofill_dataset_label, plan.size());
        RemoteViews presentation = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
        presentation.setTextViewText(android.R.id.text1, label);

        @SuppressWarnings("deprecation") // Dataset.Builder(RemoteViews) / setValue(id, value): API 26-compatible forms
        Dataset.Builder ds = new Dataset.Builder(presentation);
        for (Map.Entry<String, String> e : plan.entrySet()) {
            //noinspection deprecation
            ds.setValue(ids.get(e.getKey()), AutofillValue.forText(e.getValue()));
        }
        return new FillResponse.Builder().addDataset(ds.build()).build();
    }

    /** Text fields by resource id name; sensitive fields (password/OTP/PIN) are skipped and never looked at again. */
    private static void collect(AssistStructure.ViewNode node, Map<String, AutofillId> out) {
        if (node == null) return;
        AutofillId id = node.getAutofillId();
        String entry = node.getIdEntry();
        if (id != null && entry != null && node.getAutofillType() == View.AUTOFILL_TYPE_TEXT) {
            String[] hints = node.getAutofillHints();
            boolean sensitive = FillPlanner.isSensitive(node.getInputType(), entry,
                    node.getHint() == null ? null : node.getHint(), hints == null ? null : new HashSet<>(Arrays.asList(hints)));
            if (!sensitive && !out.containsKey(entry)) out.put(entry, id);
        }
        for (int i = 0; i < node.getChildCount(); i++) collect(node.getChildAt(i), out);
    }

    @Override
    public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        callback.onSuccess(); // A.U.R.A. never saves what she types in other apps
    }
}
