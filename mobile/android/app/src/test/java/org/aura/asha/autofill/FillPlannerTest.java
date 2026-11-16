package org.aura.asha.autofill;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

import org.junit.Test;

public class FillPlannerTest {
    private static final String PKG = FillPlanner.OWN_PACKAGE;

    private static FieldMatcher.Answer ans(String id, String fill, String input, String... words) {
        return new FieldMatcher.Answer(id, fill, input, Arrays.asList(words));
    }

    private static FieldMatcher.Field text(String key, String label) {
        return new FieldMatcher.Field(key, FieldMatcher.TYPE_TEXT, label, "", null);
    }

    private static final List<FieldMatcher.Answer> HBNC = Arrays.asList(
            ans("date", "16-11-2026", "date", "date of visit", "visit date", "भ्रमण की तारीख"),
            ans("C2", "2.6", "number", "weight", "wt", "वज़न", "वजन"),
            ans("C3", "98.6", "number", "temperature", "temp", "तापमान"),
            ans("C5", "Yes", "yesno", "bcg"),
            ans("C6", null, "yesno", "opv")); // not said: must stay blank

    private static Map<String, FieldMatcher.Fill> byKey(List<FieldMatcher.Fill> fills) {
        Map<String, FieldMatcher.Fill> m = new HashMap<>();
        for (FieldMatcher.Fill f : fills) m.put(f.fieldKey, f);
        return m;
    }

    @Test public void appItselfIsNeverFilledButOtherAppsAndThePracticeFormAre() {
        assertFalse(FillPlanner.screenAllowed(PKG, PKG + ".MainActivity"));
        assertTrue(FillPlanner.screenAllowed(PKG, FillPlanner.SIM_ACTIVITY));
        assertTrue(FillPlanner.screenAllowed("in.example.health", "in.example.health.VisitActivity"));
        assertTrue(FillPlanner.screenAllowed("com.android.chrome", "org.chromium.chrome.browser.ChromeTabbedActivity"));
    }

    @Test public void matchesByLabelInEnglishAndHindiAndLeavesBlankBlank() {
        List<FieldMatcher.Field> fields = Arrays.asList(
                text("0", "Beneficiary ID"),
                text("1", "Date of visit"),
                text("2", "वज़न (ग्राम)"),
                text("3", "Temperature (°F)"),
                text("4", "OPV given?"),
                text("5", "Remarks"));
        Map<String, FieldMatcher.Fill> m = byKey(FieldMatcher.plan(fields, HBNC));
        assertEquals("16-11-2026", m.get("1").text);
        assertEquals("2.6", m.get("2").text); // Hindi label, nukta folded
        assertEquals("98.6", m.get("3").text);
        assertNull("not said → blank", m.get("4"));
        assertNull(m.get("0"));
        assertNull(m.get("5"));
        assertEquals(3, m.size());
    }

    @Test public void eachAnswerGoesToOneFieldAndTheBestLabelWins() {
        List<FieldMatcher.Field> fields = Arrays.asList(text("0", "Birth weight (kg)"), text("1", "Weight (kg)"));
        Map<String, FieldMatcher.Fill> m = byKey(FieldMatcher.plan(fields, HBNC));
        assertEquals("2.6", m.get("1").text);
        assertNull("one answer, one field", m.get("0"));
    }

    @Test public void dropdownsAndCheckboxesGetYesNo() {
        FieldMatcher.Field list = new FieldMatcher.Field("0", FieldMatcher.TYPE_LIST, "BCG / बीसीजी", "",
                Arrays.asList("-- Select --", "हाँ", "नहीं"));
        FieldMatcher.Field box = new FieldMatcher.Field("1", FieldMatcher.TYPE_TOGGLE, "Jaundice", "", null);
        List<FieldMatcher.Answer> a = Arrays.asList(ans("C5", "Yes", "yesno", "bcg"), ans("C4", "No", "yesno", "jaundice"));
        Map<String, FieldMatcher.Fill> m = byKey(FieldMatcher.plan(Arrays.asList(list, box), a));
        assertEquals(Integer.valueOf(1), m.get("0").listIndex);
        assertEquals(Boolean.FALSE, m.get("1").toggle);
    }

    @Test public void vaccineDoseLabelsMatchWithOrWithoutDash() {
        List<FieldMatcher.Answer> a = Arrays.asList(ans("opv1", "01-01-2026", "date", "opv 1", "opv1"),
                ans("penta1", "01-01-2026", "date", "penta 1", "penta1"));
        Map<String, FieldMatcher.Fill> m = byKey(FieldMatcher.plan(
                Arrays.asList(text("0", "OPV-1 date"), text("1", "PENTA1"), text("2", "OPV-2 date")), a));
        assertEquals("opv1", m.get("0").answerId);
        assertEquals("penta1", m.get("1").answerId);
        assertNull(m.get("2"));
    }

    @Test public void developerIdsCountButLessThanLabels() {
        FieldMatcher.Field byId = new FieldMatcher.Field("0", FieldMatcher.TYPE_TEXT, "", "txtWeight weight", null);
        FieldMatcher.Field byLabel = new FieldMatcher.Field("1", FieldMatcher.TYPE_TEXT, "Weight", "", null);
        Map<String, FieldMatcher.Fill> m = byKey(FieldMatcher.plan(Arrays.asList(byId, byLabel), HBNC));
        assertEquals("2.6", m.get("1").text);
        assertNull(m.get("0"));
        assertEquals(1, FieldMatcher.plan(Collections.singletonList(byId), HBNC).size());
    }

    @Test public void passwordOtpPinAndLoginFieldsAreSensitive() {
        assertTrue(FillPlanner.isSensitive(0x00000081, "field", null, null)); // text password
        assertTrue(FillPlanner.isSensitive(0x00000012, "field", null, null)); // number password
        assertTrue(FillPlanner.isSensitive(1, "loginPin", null, null));
        assertTrue(FillPlanner.isSensitive(1, "x", "Enter OTP", null));
        assertTrue(FillPlanner.isSensitive(1, "uid", "User ID", null));
        assertTrue(FillPlanner.isSensitive(1, "x", "आधार नंबर", null));
        assertTrue(FillPlanner.isSensitive(1, "x", null, new HashSet<>(Collections.singletonList("password"))));
        assertFalse(FillPlanner.isSensitive(1, "baby_weight", "Weight", null));
        assertFalse(FillPlanner.isSensitive(1, "opinion", "Spinal check", null)); // "pin" inside a word is fine
    }

    @Test public void answersExpire() {
        long now = 1_000_000_000_000L;
        assertFalse(FillPlanner.expired(now - 60_000, now));
        assertTrue(FillPlanner.expired(now - FillPlanner.TTL_MILLIS - 1, now));
        assertTrue(FillPlanner.expired(0, now));
        assertTrue("clock moved back", FillPlanner.expired(now + 60_000, now));
    }

    @Test public void noAnswersNoFills() {
        assertTrue(FieldMatcher.plan(Collections.singletonList(text("0", "Weight")), new ArrayList<>()).isEmpty());
    }
}
