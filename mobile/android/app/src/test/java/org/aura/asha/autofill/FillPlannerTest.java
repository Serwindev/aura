package org.aura.asha.autofill;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Map;

import org.junit.Test;

public class FillPlannerTest {
    private static final String PKG = FillPlanner.OWN_PACKAGE;
    private static final String SIM = PKG + ".autofill.SimulatedFormActivity";
    private static final Map<String, String> ANSWERS = FillPlanner.mapOf("date", "16/11/2026", "C2", "2.6 kg", "C3", "98.6 °F (37.0 °C)", "C5", "Yes");

    @Test public void onlyTheSimulatedFormIsAllowListed() {
        assertEquals(1, FillPlanner.ALLOW_LIST.size());
        assertNotNull(FillPlanner.find(PKG, SIM));
        assertNull("the app's own WebView screen is not a fill target", FillPlanner.find(PKG, PKG + ".MainActivity"));
        assertNull("no government app until its terms are checked (D-34)", FillPlanner.find("in.gov.example", SIM));
    }

    @Test public void fillsOnlyConfirmedAnswersAndLeavesBlankBlank() {
        Map<String, String> plan = FillPlanner.plan(FillPlanner.find(PKG, SIM),
                Arrays.asList("beneficiary_id", "visit_date", "baby_weight", "baby_temp", "bcg", "opv", "jaundice", "remarks"), ANSWERS);
        assertEquals("16/11/2026", plan.get("visit_date"));
        assertEquals("2.6 kg", plan.get("baby_weight"));
        assertEquals("Yes", plan.get("bcg"));
        assertFalse("OPV not in the note: stays blank, never 'No'", plan.containsKey("opv"));
        assertFalse(plan.containsKey("jaundice"));
        assertFalse("ID is typed by her", plan.containsKey("beneficiary_id"));
        assertFalse(plan.containsKey("remarks"));
        assertEquals(4, plan.size());
    }

    @Test public void unknownFieldMeansLayoutChangedSoNothingIsFilled() {
        Map<String, String> plan = FillPlanner.plan(FillPlanner.find(PKG, SIM), Arrays.asList("visit_date", "new_field_v2"), ANSWERS);
        assertTrue(plan.isEmpty());
    }

    @Test public void nothingToFillWithoutAnswersOrLayout() {
        assertTrue(FillPlanner.plan(null, Collections.singletonList("visit_date"), ANSWERS).isEmpty());
        assertTrue(FillPlanner.plan(FillPlanner.find(PKG, SIM), Collections.singletonList("visit_date"), Collections.emptyMap()).isEmpty());
        assertTrue(FillPlanner.plan(FillPlanner.find(PKG, SIM), Collections.emptyList(), ANSWERS).isEmpty());
        assertTrue(FillPlanner.plan(FillPlanner.find(PKG, SIM), Collections.singletonList("visit_date"), FillPlanner.mapOf("date", "  ")).isEmpty());
    }

    @Test public void passwordOtpAndPinFieldsAreSensitive() {
        int text = 0x01, number = 0x02;
        assertTrue(FillPlanner.isSensitive(text | 0x80, "x", null, null));          // textPassword
        assertTrue(FillPlanner.isSensitive(text | 0x90, "x", null, null));          // visible password
        assertTrue(FillPlanner.isSensitive(text | 0xe0, "x", null, null));          // web password
        assertTrue(FillPlanner.isSensitive(number | 0x10, "login_pin", null, null)); // numberPassword
        assertTrue(FillPlanner.isSensitive(number, "otp_code", null, null));
        assertTrue(FillPlanner.isSensitive(number, "loginPin", null, null));
        assertTrue(FillPlanner.isSensitive(text, "field1", "Enter OTP", null));
        assertTrue(FillPlanner.isSensitive(text, "f", null, new HashSet<>(Collections.singletonList("password"))));
        assertTrue(FillPlanner.isSensitive(number, "aadhaar_no", null, null));
        assertFalse(FillPlanner.isSensitive(text, "opv", "OPV given?", null));
        assertFalse(FillPlanner.isSensitive(text, "visit_date", "Date of visit", null));
        // Fail-safe on purpose: a hint containing the word "PIN" is skipped even if it is a postal PIN code.
        assertTrue(FillPlanner.isSensitive(number, "village_code", "Village PIN code", null));
        assertFalse(FillPlanner.isSensitive(number, "pincode", null, null));
    }

    @Test public void answersExpire() {
        long now = 1_000_000_000_000L;
        assertFalse(FillPlanner.expired(now - 60_000, now));
        assertTrue(FillPlanner.expired(now - FillPlanner.TTL_MILLIS - 1, now));
        assertTrue(FillPlanner.expired(0, now));
        assertTrue("clock moved back", FillPlanner.expired(now + 60_000, now));
    }
}
