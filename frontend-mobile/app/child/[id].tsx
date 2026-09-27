import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useState, useEffect, useCallback } from "react";
import { useLocalSearchParams, router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getChildDashboard, getChildren, generateChildSummary } from "@/lib/api";
import AgentStatsCard from "@/components/AgentStatsCard";
import { ChildDashboard, AgentStats, Child } from "@/lib/types";

const emptyStats: AgentStats = { likes: 0, normals: 0, dislikes: 0, total: 0 };

export default function ChildDashboardScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [child, setChild] = useState<ChildDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<string | null>(null);
  const [generatingSummary, setGeneratingSummary] = useState(false);

  // Child cycling state
  const [allChildren, setAllChildren] = useState<Child[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);

  useEffect(() => {
    loadAllChildren();
  }, []);

  useEffect(() => {
    if (id) {
      setLoading(true);
      setSummary(null);
      loadChild(Number(id));
    }
  }, [id]);

  const loadAllChildren = async () => {
    try {
      const children = await getChildren();
      setAllChildren(children);
      const idx = children.findIndex((c) => c.child_id === Number(id));
      setCurrentIndex(idx);
    } catch {
      // Non-critical — cycling just won't be available
    }
  };

  const loadChild = async (childId: number) => {
    try {
      const data = await getChildDashboard(childId);
      setChild(data);
      // Update index when data loads
      const idx = allChildren.findIndex((c) => c.child_id === childId);
      if (idx >= 0) setCurrentIndex(idx);
    } catch {
      Alert.alert("Error", "Failed to load child data");
    } finally {
      setLoading(false);
    }
  };

  const goToPreviousChild = useCallback(() => {
    if (allChildren.length <= 1) return;
    const prevIndex = currentIndex <= 0 ? allChildren.length - 1 : currentIndex - 1;
    const prevChild = allChildren[prevIndex];
    router.setParams({ id: String(prevChild.child_id) });
  }, [allChildren, currentIndex]);

  const goToNextChild = useCallback(() => {
    if (allChildren.length <= 1) return;
    const nextIndex = currentIndex >= allChildren.length - 1 ? 0 : currentIndex + 1;
    const nextChild = allChildren[nextIndex];
    router.setParams({ id: String(nextChild.child_id) });
  }, [allChildren, currentIndex]);

  const handleGenerateSummary = async () => {
    setGeneratingSummary(true);
    try {
      const data = await generateChildSummary(Number(id));
      setSummary(data.summary);
    } catch {
      Alert.alert("Error", "Failed to generate summary");
    } finally {
      setGeneratingSummary(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#7A9B6D" />
      </View>
    );
  }

  if (!child) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>Child not found</Text>
      </View>
    );
  }

  const hasCycling = allChildren.length > 1;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Child Navigation Header */}
      <View style={styles.navRow}>
        {hasCycling ? (
          <TouchableOpacity style={styles.navArrow} onPress={goToPreviousChild}>
            <Ionicons name="chevron-back-circle" size={36} color="#7A9B6D" />
          </TouchableOpacity>
        ) : (
          <View style={styles.navArrowPlaceholder} />
        )}

        <View style={styles.headerCenter}>
          <Text style={styles.childName}>{child.child_name}</Text>
          {hasCycling && (
            <Text style={styles.childCounter}>
              {currentIndex + 1} of {allChildren.length}
            </Text>
          )}
        </View>

        {hasCycling ? (
          <TouchableOpacity style={styles.navArrow} onPress={goToNextChild}>
            <Ionicons name="chevron-forward-circle" size={36} color="#7A9B6D" />
          </TouchableOpacity>
        ) : (
          <View style={styles.navArrowPlaceholder} />
        )}
      </View>

      {/* Child Info */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.childInfo}>DOB: {child.date_of_birth}</Text>
          {child.allergies ? <Text style={styles.allergies}>Allergies: {child.allergies}</Text> : null}
        </View>
        <View style={[styles.statusBadge, child.is_checked_in ? styles.checkedIn : styles.checkedOut]}>
          <Text style={styles.statusText}>{child.is_checked_in ? "Checked In" : "Not Checked In"}</Text>
        </View>
      </View>

      {/* Agent Stats Cards */}
      <Text style={styles.sectionTitle}>Development Areas</Text>
      <AgentStatsCard
        agent="sage"
        stats={child.sage_stats || emptyStats}
        onPress={() => router.push(`/child/activities?id=${id}&agent=sage`)}
      />
      <AgentStatsCard
        agent="grace"
        stats={child.grace_stats || emptyStats}
        onPress={() => router.push(`/child/activities?id=${id}&agent=grace`)}
      />
      <AgentStatsCard
        agent="patience"
        stats={child.patience_stats || emptyStats}
        onPress={() => router.push(`/child/activities?id=${id}&agent=patience`)}
      />

      {/* Generate Report */}
      <Text style={styles.sectionTitle}>Developmental Summary</Text>
      <TouchableOpacity style={styles.reportBtn} onPress={handleGenerateSummary} disabled={generatingSummary}>
        {generatingSummary ? (
          <>
            <ActivityIndicator size="small" color="#fff" />
            <Text style={styles.reportBtnText}>Generating...</Text>
          </>
        ) : (
          <>
            <Ionicons name="document-text-outline" size={18} color="#fff" />
            <Text style={styles.reportBtnText}>Generate Report</Text>
          </>
        )}
      </TouchableOpacity>

      {summary && (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryText}>{summary}</Text>
        </View>
      )}

      {/* Recent Attendance */}
      {child.recent_attendance && child.recent_attendance.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Recent Attendance</Text>
          {child.recent_attendance.map((log, i) => (
            <View key={i} style={styles.attendanceRow}>
              <Text style={styles.attendanceDate}>{log.date}</Text>
              <Text style={styles.attendanceTime}>In: {log.check_in}</Text>
              {log.check_out ? (
                <Text style={styles.attendanceTime}>Out: {log.check_out}</Text>
              ) : (
                <View style={styles.stillHereBadge}><Text style={styles.stillHereText}>Still here</Text></View>
              )}
            </View>
          ))}
        </>
      )}

      {/* Child Info */}
      {child.parent_name && (
        <>
          <Text style={styles.sectionTitle}>Parent Info</Text>
          <View style={styles.infoCard}>
            <Text style={styles.infoLabel}>Parent: {child.parent_name}</Text>
            {child.parent_email && <Text style={styles.infoLabel}>Email: {child.parent_email}</Text>}
            {child.parent_phone && <Text style={styles.infoLabel}>Phone: {child.parent_phone}</Text>}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16, paddingBottom: 32 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },
  errorText: { fontSize: 15, color: "#999" },

  // Navigation row for cycling
  navRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  navArrow: {
    padding: 4,
  },
  navArrowPlaceholder: {
    width: 44,
  },
  headerCenter: {
    flex: 1,
    alignItems: "center",
  },
  childName: { fontSize: 24, fontWeight: "700", color: "#333", textAlign: "center" },
  childCounter: { fontSize: 13, color: "#999", marginTop: 2 },

  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
  childInfo: { fontSize: 14, color: "#888", marginTop: 2 },
  allergies: { fontSize: 13, color: "#c0392b", marginTop: 2 },
  statusBadge: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 5 },
  checkedIn: { backgroundColor: "#27ae60" },
  checkedOut: { backgroundColor: "#bbb" },
  statusText: { color: "#fff", fontSize: 12, fontWeight: "600" },
  sectionTitle: { fontSize: 18, fontWeight: "600", color: "#333", marginBottom: 12, marginTop: 16 },
  reportBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#7A9B6D",
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignSelf: "flex-start",
  },
  reportBtnText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  summaryCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  summaryText: { fontSize: 14, color: "#444", lineHeight: 22 },
  attendanceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#fff",
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
  },
  attendanceDate: { fontSize: 13, fontWeight: "600", color: "#333", width: 80 },
  attendanceTime: { fontSize: 13, color: "#666" },
  stillHereBadge: { backgroundColor: "#27ae60", borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  stillHereText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  infoCard: { backgroundColor: "#fff", borderRadius: 12, padding: 16, gap: 4 },
  infoLabel: { fontSize: 14, color: "#555" },
});
