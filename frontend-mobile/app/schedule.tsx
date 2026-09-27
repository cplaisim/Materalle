import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useState, useEffect } from "react";
import { Ionicons } from "@expo/vector-icons";
import { getWeeklySchedule, generateWeeklySchedule } from "@/lib/api";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const AGENT_COLORS: Record<string, string> = { sage: "#7A9B6D", grace: "#C48DB8", patience: "#7BAAC4" };

interface ScheduleEntry {
  id: number;
  title: string;
  agent: string;
  start_time: string;
  scheduled_date: string;
}

export default function ScheduleScreen() {
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => { loadSchedule(); }, []);

  const loadSchedule = async () => {
    try {
      const data = await getWeeklySchedule();
      setEntries(Array.isArray(data) ? data : data.entries || []);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    Alert.alert("Generate Schedule", "This will generate activities for the week using AI. Continue?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Generate",
        onPress: async () => {
          setGenerating(true);
          try {
            await generateWeeklySchedule();
            await loadSchedule();
            Alert.alert("Success", "Weekly schedule generated!");
          } catch {
            Alert.alert("Error", "Failed to generate schedule");
          } finally {
            setGenerating(false);
          }
        },
      },
    ]);
  };

  // Group entries by day
  const byDay: Record<string, ScheduleEntry[]> = {};
  for (const entry of entries) {
    const day = entry.scheduled_date;
    if (!byDay[day]) byDay[day] = [];
    byDay[day].push(entry);
  }

  if (loading) {
    return <View style={styles.centered}><ActivityIndicator size="large" color="#7A9B6D" /></View>;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Weekly Schedule</Text>
        <TouchableOpacity style={styles.genBtn} onPress={handleGenerate} disabled={generating}>
          {generating ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="sparkles" size={16} color="#fff" />}
          <Text style={styles.genBtnText}>{generating ? "Generating..." : "Generate"}</Text>
        </TouchableOpacity>
      </View>

      {entries.length > 0 ? (
        Object.entries(byDay).sort().map(([date, dayEntries]) => (
          <View key={date} style={styles.daySection}>
            <Text style={styles.dayTitle}>{date}</Text>
            {dayEntries.sort((a, b) => a.start_time.localeCompare(b.start_time)).map((entry) => (
              <View key={entry.id} style={styles.entryRow}>
                <Text style={styles.entryTime}>{entry.start_time}</Text>
                <View style={[styles.agentDot, { backgroundColor: AGENT_COLORS[entry.agent] || "#999" }]} />
                <Text style={styles.entryTitle}>{entry.title}</Text>
              </View>
            ))}
          </View>
        ))
      ) : (
        <View style={styles.emptyState}>
          <Ionicons name="calendar-outline" size={48} color="#ccc" />
          <Text style={styles.emptyText}>No schedule generated yet.</Text>
          <Text style={styles.emptySubtext}>Tap Generate to create this week's activities.</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16, paddingBottom: 32 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  title: { fontSize: 24, fontWeight: "700", color: "#333" },
  genBtn: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#7A9B6D", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  genBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  daySection: { marginBottom: 20 },
  dayTitle: { fontSize: 16, fontWeight: "600", color: "#333", marginBottom: 8, borderBottomWidth: 1, borderBottomColor: "#e8e0d8", paddingBottom: 6 },
  entryRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 8, paddingHorizontal: 4 },
  entryTime: { fontSize: 12, color: "#888", width: 55, fontWeight: "500" },
  agentDot: { width: 8, height: 8, borderRadius: 4 },
  entryTitle: { fontSize: 14, color: "#444", flex: 1 },
  emptyState: { alignItems: "center", padding: 40, gap: 8 },
  emptyText: { fontSize: 15, color: "#999" },
  emptySubtext: { fontSize: 13, color: "#bbb" },
});
