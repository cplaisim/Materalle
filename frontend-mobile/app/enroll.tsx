import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, Alert, ActivityIndicator, Switch } from "react-native";
import { useState } from "react";
import { router } from "expo-router";
import { enrollChild } from "@/lib/api";

type FormState = Record<string, string | boolean>;

const INITIAL_FORM: FormState = {
  // Enrollment dates
  date_of_enrollment: new Date().toISOString().split("T")[0],
  date_of_withdrawal: "",
  // Child info
  child_name: "",
  date_of_birth: "",
  child_address: "",
  child_gender: "M",
  // Primary parent/guardian
  parent_name: "",
  parent_address: "",
  parent_phone: "",
  parent_email: "",
  ok_to_text: true,
  parent: true,
  caretaker: false,
  relative: false,
  guardian: false,
  other: false,
  // Emergency contact 1
  parent_name_1: "",
  parent_phone_1: "",
  parent_email_1: "",
  ok_to_text_1: false,
  authorized_pickup_1: false,
  // Emergency contact 2
  parent_name_2: "",
  parent_phone_2: "",
  parent_email_2: "",
  ok_to_text_2: false,
  authorized_pickup_2: false,
  // Emergency contact 3
  parent_name_3: "",
  parent_phone_3: "",
  parent_email_3: "",
  ok_to_text_3: false,
  authorized_pickup_3: false,
  // Medical
  child_physician: "",
  child_physician_phone: "",
  preferred_hospital: "",
  hospital_phone: "",
  child_dentist: "",
  dentist_phone: "",
  child_allergies: "",
  // Therapy
  speech_therapy: false,
  physical_therapy: false,
  early_intervention: false,
  other_therapy: false,
  none_therapy: true,
  // Additional info
  info_to_share: "",
  // Consents
  consent_to_treat: true,
  consent_to_transport: true,
  consent_to_trip: true,
  understand_permissions: true,
  agree_to_update: true,
  agree_policies: true,
  photo_release: true,
  // Signature
  signature: "",
  date_signed: new Date().toISOString().split("T")[0],
};

function Field({ label, value, onChange, placeholder, keyboardType, multiline, required }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
  keyboardType?: "default" | "email-address" | "phone-pad"; multiline?: boolean; required?: boolean;
}) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.fieldLabel}>{label}{required ? " *" : ""}</Text>
      <TextInput
        style={[styles.input, multiline && styles.multiline]}
        placeholder={placeholder || label}
        placeholderTextColor="#bbb"
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType || "default"}
        autoCapitalize={keyboardType === "email-address" ? "none" : "sentences"}
        multiline={multiline}
      />
    </View>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ false: "#ddd", true: "#7A9B6D" }} thumbColor="#fff" />
    </View>
  );
}

function GenderPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.fieldLabel}>Gender *</Text>
      <View style={styles.genderRow}>
        {[{ k: "M", l: "Male" }, { k: "F", l: "Female" }].map((g) => (
          <TouchableOpacity
            key={g.k}
            style={[styles.genderBtn, value === g.k && styles.genderBtnActive]}
            onPress={() => onChange(g.k)}
          >
            <Text style={[styles.genderBtnText, value === g.k && styles.genderBtnTextActive]}>{g.l}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

export default function EnrollScreen() {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);

  const set = (key: string, value: string | boolean) => setForm((p) => ({ ...p, [key]: value }));

  const handleSubmit = async () => {
    const required = ["child_name", "date_of_birth", "child_address", "parent_name",
      "parent_address", "parent_phone", "parent_email", "child_physician",
      "child_physician_phone", "preferred_hospital", "hospital_phone",
      "child_dentist", "dentist_phone", "child_allergies", "signature"];
    const missing = required.filter((f) => !String(form[f] || "").trim());
    if (missing.length) {
      Alert.alert("Missing Fields", `Please fill in: ${missing.map((f) => f.replace(/_/g, " ")).join(", ")}`);
      return;
    }
    // Need at least one emergency contact
    if (!form.parent_name_1 && !form.parent_name_2 && !form.parent_name_3) {
      Alert.alert("Error", "At least one emergency contact is required");
      return;
    }
    setLoading(true);
    try {
      await enrollChild(form);
      Alert.alert("Success", "Child enrolled successfully!", [
        { text: "OK", onPress: () => router.back() },
      ]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Enrollment failed";
      Alert.alert("Error", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

      {/* Enrollment Dates */}
      <Text style={styles.sectionTitle}>Enrollment Dates</Text>
      <View style={styles.card}>
        <Field label="Date of Enrollment" value={String(form.date_of_enrollment)} onChange={(v) => set("date_of_enrollment", v)} placeholder="YYYY-MM-DD" required />
        <Field label="Date of Withdrawal" value={String(form.date_of_withdrawal)} onChange={(v) => set("date_of_withdrawal", v)} placeholder="YYYY-MM-DD" />
      </View>

      {/* Child Information */}
      <Text style={styles.sectionTitle}>Child Information</Text>
      <View style={styles.card}>
        <Field label="Child's Full Name" value={String(form.child_name)} onChange={(v) => set("child_name", v)} required />
        <Field label="Date of Birth" value={String(form.date_of_birth)} onChange={(v) => set("date_of_birth", v)} placeholder="YYYY-MM-DD" required />
        <Field label="Child's Address" value={String(form.child_address)} onChange={(v) => set("child_address", v)} required />
        <GenderPicker value={String(form.child_gender)} onChange={(v) => set("child_gender", v)} />
      </View>

      {/* Primary Parent/Guardian */}
      <Text style={styles.sectionTitle}>Primary Parent / Guardian</Text>
      <View style={styles.card}>
        <Field label="Parent Name" value={String(form.parent_name)} onChange={(v) => set("parent_name", v)} required />
        <Field label="Parent Address" value={String(form.parent_address)} onChange={(v) => set("parent_address", v)} required />
        <Field label="Parent Phone" value={String(form.parent_phone)} onChange={(v) => set("parent_phone", v)} keyboardType="phone-pad" required />
        <Field label="Parent Email" value={String(form.parent_email)} onChange={(v) => set("parent_email", v)} keyboardType="email-address" required />
        <Toggle label="OK to text" value={!!form.ok_to_text} onChange={(v) => set("ok_to_text", v)} />
        <Text style={styles.subLabel}>Relationship to child:</Text>
        <Toggle label="Parent" value={!!form.parent} onChange={(v) => set("parent", v)} />
        <Toggle label="Caretaker" value={!!form.caretaker} onChange={(v) => set("caretaker", v)} />
        <Toggle label="Relative" value={!!form.relative} onChange={(v) => set("relative", v)} />
        <Toggle label="Guardian" value={!!form.guardian} onChange={(v) => set("guardian", v)} />
        <Toggle label="Other" value={!!form.other} onChange={(v) => set("other", v)} />
      </View>

      {/* Emergency Contact 1 */}
      <Text style={styles.sectionTitle}>Emergency Contact 1 *</Text>
      <View style={styles.card}>
        <Field label="Name" value={String(form.parent_name_1)} onChange={(v) => set("parent_name_1", v)} />
        <Field label="Phone" value={String(form.parent_phone_1)} onChange={(v) => set("parent_phone_1", v)} keyboardType="phone-pad" />
        <Field label="Email" value={String(form.parent_email_1)} onChange={(v) => set("parent_email_1", v)} keyboardType="email-address" />
        <Toggle label="OK to text" value={!!form.ok_to_text_1} onChange={(v) => set("ok_to_text_1", v)} />
        <Toggle label="Authorized pickup" value={!!form.authorized_pickup_1} onChange={(v) => set("authorized_pickup_1", v)} />
      </View>

      {/* Emergency Contact 2 */}
      <Text style={styles.sectionTitle}>Emergency Contact 2</Text>
      <View style={styles.card}>
        <Field label="Name" value={String(form.parent_name_2)} onChange={(v) => set("parent_name_2", v)} />
        <Field label="Phone" value={String(form.parent_phone_2)} onChange={(v) => set("parent_phone_2", v)} keyboardType="phone-pad" />
        <Field label="Email" value={String(form.parent_email_2)} onChange={(v) => set("parent_email_2", v)} keyboardType="email-address" />
        <Toggle label="OK to text" value={!!form.ok_to_text_2} onChange={(v) => set("ok_to_text_2", v)} />
        <Toggle label="Authorized pickup" value={!!form.authorized_pickup_2} onChange={(v) => set("authorized_pickup_2", v)} />
      </View>

      {/* Emergency Contact 3 */}
      <Text style={styles.sectionTitle}>Emergency Contact 3</Text>
      <View style={styles.card}>
        <Field label="Name" value={String(form.parent_name_3)} onChange={(v) => set("parent_name_3", v)} />
        <Field label="Phone" value={String(form.parent_phone_3)} onChange={(v) => set("parent_phone_3", v)} keyboardType="phone-pad" />
        <Field label="Email" value={String(form.parent_email_3)} onChange={(v) => set("parent_email_3", v)} keyboardType="email-address" />
        <Toggle label="OK to text" value={!!form.ok_to_text_3} onChange={(v) => set("ok_to_text_3", v)} />
        <Toggle label="Authorized pickup" value={!!form.authorized_pickup_3} onChange={(v) => set("authorized_pickup_3", v)} />
      </View>

      {/* Medical Information */}
      <Text style={styles.sectionTitle}>Medical Information</Text>
      <View style={styles.card}>
        <Field label="Physician Name" value={String(form.child_physician)} onChange={(v) => set("child_physician", v)} required />
        <Field label="Physician Phone" value={String(form.child_physician_phone)} onChange={(v) => set("child_physician_phone", v)} keyboardType="phone-pad" required />
        <Field label="Preferred Hospital" value={String(form.preferred_hospital)} onChange={(v) => set("preferred_hospital", v)} required />
        <Field label="Hospital Phone" value={String(form.hospital_phone)} onChange={(v) => set("hospital_phone", v)} keyboardType="phone-pad" required />
        <Field label="Dentist Name" value={String(form.child_dentist)} onChange={(v) => set("child_dentist", v)} required />
        <Field label="Dentist Phone" value={String(form.dentist_phone)} onChange={(v) => set("dentist_phone", v)} keyboardType="phone-pad" required />
        <Field label="Allergies" value={String(form.child_allergies)} onChange={(v) => set("child_allergies", v)} required />
      </View>

      {/* Therapy Services */}
      <Text style={styles.sectionTitle}>Therapy Services</Text>
      <View style={styles.card}>
        <Toggle label="Speech Therapy" value={!!form.speech_therapy} onChange={(v) => set("speech_therapy", v)} />
        <Toggle label="Physical Therapy" value={!!form.physical_therapy} onChange={(v) => set("physical_therapy", v)} />
        <Toggle label="Early Intervention" value={!!form.early_intervention} onChange={(v) => set("early_intervention", v)} />
        <Toggle label="Other Therapy" value={!!form.other_therapy} onChange={(v) => set("other_therapy", v)} />
        <Toggle label="None" value={!!form.none_therapy} onChange={(v) => set("none_therapy", v)} />
        <Field label="Additional Info to Share" value={String(form.info_to_share)} onChange={(v) => set("info_to_share", v)} multiline />
      </View>

      {/* Consents & Agreements */}
      <Text style={styles.sectionTitle}>Consents & Agreements</Text>
      <View style={styles.card}>
        <Toggle label="Consent to treat" value={!!form.consent_to_treat} onChange={(v) => set("consent_to_treat", v)} />
        <Toggle label="Consent to transport" value={!!form.consent_to_transport} onChange={(v) => set("consent_to_transport", v)} />
        <Toggle label="Consent for field trips" value={!!form.consent_to_trip} onChange={(v) => set("consent_to_trip", v)} />
        <Toggle label="Understand permissions" value={!!form.understand_permissions} onChange={(v) => set("understand_permissions", v)} />
        <Toggle label="Agree to update info" value={!!form.agree_to_update} onChange={(v) => set("agree_to_update", v)} />
        <Toggle label="Agree to policies" value={!!form.agree_policies} onChange={(v) => set("agree_policies", v)} />
        <Toggle label="Photo release" value={!!form.photo_release} onChange={(v) => set("photo_release", v)} />
      </View>

      {/* Signature */}
      <Text style={styles.sectionTitle}>Signature</Text>
      <View style={styles.card}>
        <Field label="Signature (typed name)" value={String(form.signature)} onChange={(v) => set("signature", v)} required />
        <Field label="Date Signed" value={String(form.date_signed)} onChange={(v) => set("date_signed", v)} placeholder="YYYY-MM-DD" required />
      </View>

      <TouchableOpacity style={styles.submitBtn} onPress={handleSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitBtnText}>Submit Enrollment</Text>}
      </TouchableOpacity>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16, paddingBottom: 40 },
  sectionTitle: { fontSize: 17, fontWeight: "700", color: "#333", marginBottom: 8, marginTop: 20 },
  subLabel: { fontSize: 13, color: "#888", marginTop: 8, marginBottom: 4 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  fieldWrap: { marginBottom: 10 },
  fieldLabel: { fontSize: 13, fontWeight: "500", color: "#555", marginBottom: 4 },
  input: {
    backgroundColor: "#FAFAF7",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 11,
    fontSize: 15,
    borderWidth: 1,
    borderColor: "#e8e0d8",
    color: "#333",
  },
  multiline: { minHeight: 70, textAlignVertical: "top" },
  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#f0ece6",
  },
  toggleLabel: { fontSize: 14, color: "#444", flex: 1 },
  genderRow: { flexDirection: "row", gap: 10 },
  genderBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e8e0d8",
    alignItems: "center",
    backgroundColor: "#FAFAF7",
  },
  genderBtnActive: { backgroundColor: "#7A9B6D", borderColor: "#7A9B6D" },
  genderBtnText: { fontSize: 14, color: "#555" },
  genderBtnTextActive: { color: "#fff", fontWeight: "600" },
  submitBtn: {
    backgroundColor: "#7A9B6D",
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 24,
  },
  submitBtnText: { color: "#fff", fontSize: 17, fontWeight: "700" },
});
