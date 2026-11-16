package org.aura.asha.autofill;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.provider.Settings;
import android.util.Base64;
import android.view.autofill.AutofillManager;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

/** Bridge from the web app (native.js) to the Autofill service and the share sheet. */
@CapacitorPlugin(name = "AuraAutofill")
public class AuraAutofillPlugin extends Plugin {

    private boolean serviceEnabled() {
        AutofillManager am = getContext().getSystemService(AutofillManager.class);
        return am != null && am.hasEnabledAutofillServices();
    }

    @PluginMethod
    public void setVisit(PluginCall call) {
        JSArray fields = call.getArray("fields");
        String noteId = call.getString("noteId", "");
        if (fields == null || noteId.isEmpty()) {
            call.reject("noteId and fields are required");
            return;
        }
        try {
            int n = VisitStore.save(getContext(), noteId, call.getString("title", ""), fields);
            JSObject r = new JSObject();
            r.put("fields", n);
            r.put("serviceEnabled", serviceEnabled());
            call.resolve(r);
        } catch (Exception e) {
            call.reject("Could not prepare autofill", e);
        }
    }

    @PluginMethod
    public void clearVisit(PluginCall call) {
        VisitStore.clear(getContext());
        call.resolve();
    }

    @PluginMethod
    public void status(PluginCall call) {
        JSObject r = new JSObject();
        r.put("serviceEnabled", serviceEnabled());
        r.put("ready", VisitStore.load(getContext()) != null);
        call.resolve(r);
    }

    /** Android's own screen where she picks A.U.R.A. as the autofill service (she can turn it off there too). */
    @PluginMethod
    public void openSettings(PluginCall call) {
        Intent i = new Intent(Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE);
        i.setData(Uri.parse("package:" + getContext().getPackageName()));
        try {
            getActivity().startActivity(i);
        } catch (ActivityNotFoundException e) {
            getActivity().startActivity(new Intent(Settings.ACTION_SETTINGS));
        }
        call.resolve();
    }

    /** SIMULATED government-style app screen for the form she has open (HBNC, SSBSK, RCH child). */
    @PluginMethod
    public void openTestForm(PluginCall call) {
        Intent i = new Intent(getContext(), SimulatedFormActivity.class);
        JSObject form = call.getObject("form");
        if (form != null) i.putExtra(SimulatedFormActivity.EXTRA_FORM, form.toString());
        getActivity().startActivity(i);
        call.resolve();
    }

    /** Opens a web page in Chrome (for the SIMULATED practice portal); falls back to any browser. */
    @PluginMethod
    public void openBrowser(PluginCall call) {
        String url = call.getString("url", "");
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            call.reject("Only web addresses can be opened");
            return;
        }
        Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            getActivity().startActivity(new Intent(view).setPackage("com.android.chrome"));
        } catch (ActivityNotFoundException e) {
            getActivity().startActivity(view);
        }
        call.resolve();
    }

    /** Reports (PDF/XLSX): the WebView cannot download, so write to the app cache and open the share sheet. */
    @PluginMethod
    public void shareFile(PluginCall call) {
        String name = call.getString("name", "aura-file");
        String mime = call.getString("mime", "application/octet-stream");
        String data = call.getString("data", "");
        String safe = name.replaceAll("[^A-Za-z0-9._-]", "_");
        if (safe.isEmpty() || safe.startsWith(".")) safe = "aura-file";
        try {
            File dir = new File(getContext().getCacheDir(), "shared");
            if (!dir.isDirectory() && !dir.mkdirs()) throw new IOException("no cache dir");
            File f = new File(dir, safe);
            try (FileOutputStream out = new FileOutputStream(f)) {
                out.write(Base64.decode(data, Base64.DEFAULT));
            }
            Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", f);
            Intent send = new Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            getActivity().startActivity(Intent.createChooser(send, safe));
            call.resolve();
        } catch (Exception e) {
            call.reject("Could not share the file", e);
        }
    }
}
