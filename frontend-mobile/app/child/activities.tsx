import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator } from "react-native";
import { useState, useEffect } from "react";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getChildActivities } from "@/lib/api";
import { ChildActivity } from "@/lib/types";

const AGENTS = ["sage", "grace", "patience"] as const;
const AGENT_CONFIG: Record<string, { label: string; color: string }> = {
  sage: { label: "Sage", color: "#7A9B6D" },
  grace: { label: "Grace", color: "#C48DB8" },
  patience: { label: "Patience", color: "#7BAAC4" },
};

const RATING_LABELS: Record<number, string> = { 3: "😄 Liked", 2: "😐 Okay", 1: "😞 Disliked" };

export default function ChildActivitiesScreen() {
  const { id, agent: initialAgent } = useLocalSearchParams<{ id: string; agent: string }>();
  const [agent, setAgent] = useState(initialAgent || "sage");
  const [activities, setActivities] = useState<ChildActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivities();
  }, [agent]);

  const loadActivities = async () => {
    setLoading(true);
    try {
      const data = await getChildActivities(Number(id), agent);
      setActivities(Array.isArray(data) ? data : []);
    } catch {
      setActivities([]);
    } finally {
      setLoading(false);
    }
  };

  const cycleAgent = (direction: number) => {
    const idx = AGENTS.indexOf(agent as typeof AGENTS[number]);
    const next = (idx + direction + AGENTS.length) % AGENTS.length;
    setAgent(AGENTS[next]);
  };

  const config = AGENT_CONFIG[agent] || AGENT_CONFIG.sage;
  const likes = activities.filter((a) => a.rating === 3).length;
  const normals = activities.filter((a) => a.rating === 2).length;
  const dislikes = activities.filter((a) => a.rating === 1).length;

  return (
    <View style={styles.container}>
      {/* Agent Navigation */}
      <View style={[styles.agentHeader, { backgroundColor: config.color }]}>
        <TouchableOpacity onPress={() => cycleAgent(-1)}>
          <Ionicons name="chevron-back" size={24} color="#fff" />
        </TouchableOpacity>
        <View style={styles.agentHeaderCenter}>
          <Text style={styles.agentTitle}>{config.label} Activities</Text>
          <Text style={styles.agentSubtitle}>Total: {activities.length} | 😄 {likes} | 😐 {normals} | 😞 {dislikes}</Text>
        </View>
        <TouchableOpacity onPress={() => cycleAgent(1)}>
          <Ionicons name="chevron-forward" size={24} color="#fff" />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={config.color} />
        </View>
      ) : (
        <FlatList
          data={activities}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.activityCard}>
              <View style={styles.activityHeader}>
                <Text style={styles.activityDate}>{item.date}</Text>
                {item.activity_type && (
                  <View style={[styles.typeBadge, { backgroundColor: config.color + "20" }]}>
                    <Text style={[styles.typeBadgeText, { color: config.color }]}>{item.activity_type}</Text>
                  </View>
                )}
                {item.rating ? (
                  <Text style={styles.ratingLabel}>{RATING_LABELS[item.rating] || "—"}</Text>
                ) : (
                  <Text style={styles.noRating}>—</Text>
                )}
              </View>
              <Text style={styles.activityTitle}>{item.title}</Text>
              {item.description && <Text style={styles.activityDesc} numberOfLines={3}>{item.description}</Text>}
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No activities found for {config.label}.</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  agentHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  agentHeaderCenter: { alignItems: "center", flex: 1 },
  agentTitle: { fontSize: 18, fontWeight: "700", color: "#fff" },
  agentSubtitle: { fontSize: 12, color: "rgba(255,255,255,0.8)", marginTop: 2 },
  list: { padding: 16 },
  activityCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  activityHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  activityDate: { fontSize: 12, color: "#888", fontWeight: "500" },
  typeBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  typeBadgeText: { fontSize: 11, fontWeight: "600" },
  ratingLabel: { fontSize: 13, marginLeft: "auto" },
  noRating: { fontSize: 13, color: "#ccc", marginLeft: "auto" },
  activityTitle: { fontSize: 15, fontWeight: "600", color: "#333", marginBottom: 4 },
  activityDesc: { fontSize: 13, color: "#666", lineHeight: 18 },
  emptyState: { alignItems: "center", padding: 40 },
  emptyText: { fontSize: 14, color: "#999" },
});
