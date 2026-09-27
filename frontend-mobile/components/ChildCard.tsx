import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Child } from "@/lib/types";

interface ChildCardProps {
  child: Child;
  onPress?: () => void;
  onCheckIn?: () => void;
  onCheckOut?: () => void;
}

export default function ChildCard({ child, onPress, onCheckIn, onCheckOut }: ChildCardProps) {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.row}>
        <View style={styles.info}>
          <Text style={styles.name}>{child.child_name}</Text>
          <Text style={styles.dob}>DOB: {child.date_of_birth}</Text>
          {child.allergies ? <Text style={styles.allergies}>Allergies: {child.allergies}</Text> : null}
        </View>
        <View style={styles.actions}>
          {child.is_checked_in ? (
            <TouchableOpacity style={[styles.badge, styles.checkedIn]} onPress={onCheckOut}>
              <Ionicons name="checkmark-circle" size={16} color="#fff" />
              <Text style={styles.badgeText}>Checked In</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={[styles.badge, styles.checkedOut]} onPress={onCheckIn}>
              <Ionicons name="log-in-outline" size={16} color="#fff" />
              <Text style={styles.badgeText}>Check In</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  info: { flex: 1 },
  name: { fontSize: 16, fontWeight: "600", color: "#333", marginBottom: 2 },
  dob: { fontSize: 13, color: "#888" },
  allergies: { fontSize: 12, color: "#c0392b", marginTop: 2 },
  actions: { marginLeft: 12 },
  badge: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16 },
  checkedIn: { backgroundColor: "#27ae60" },
  checkedOut: { backgroundColor: "#7f8c8d" },
  badgeText: { color: "#fff", fontSize: 12, fontWeight: "600" },
});
