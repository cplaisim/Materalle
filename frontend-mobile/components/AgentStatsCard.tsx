import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { AgentStats } from "@/lib/types";

interface AgentStatsCardProps {
  agent: "sage" | "grace" | "patience";
  stats: AgentStats;
  onPress?: () => void;
}

const AGENT_CONFIG = {
  sage: { label: "Sage", subtitle: "Nutrition & Planning", color: "#7A9B6D", icon: "🌿" },
  grace: { label: "Grace", subtitle: "Social-Emotional", color: "#C48DB8", icon: "💜" },
  patience: { label: "Patience", subtitle: "Motor & Physical", color: "#7BAAC4", icon: "💪" },
};

export default function AgentStatsCard({ agent, stats, onPress }: AgentStatsCardProps) {
  const config = AGENT_CONFIG[agent];
  const total = stats.total || 1;
  const likeW = (stats.likes / total) * 100;
  const normalW = (stats.normals / total) * 100;
  const dislikeW = (stats.dislikes / total) * 100;

  return (
    <TouchableOpacity style={[styles.card, { borderTopColor: config.color }]} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <Text style={styles.icon}>{config.icon}</Text>
        <View>
          <Text style={styles.title}>{config.label}</Text>
          <Text style={styles.subtitle}>{config.subtitle}</Text>
        </View>
      </View>
      {stats.total > 0 ? (
        <>
          <View style={styles.emojiRow}>
            <Text style={styles.emojiStat}>😄 {stats.likes}</Text>
            <Text style={styles.emojiStat}>😐 {stats.normals}</Text>
            <Text style={styles.emojiStat}>😞 {stats.dislikes}</Text>
          </View>
          <View style={styles.progressBar}>
            {likeW > 0 && <View style={[styles.progressSegment, { width: `${likeW}%`, backgroundColor: "#27ae60" }]} />}
            {normalW > 0 && <View style={[styles.progressSegment, { width: `${normalW}%`, backgroundColor: "#f39c12" }]} />}
            {dislikeW > 0 && <View style={[styles.progressSegment, { width: `${dislikeW}%`, backgroundColor: "#e74c3c" }]} />}
          </View>
        </>
      ) : (
        <Text style={styles.noData}>No ratings yet</Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderTopWidth: 3,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  header: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  icon: { fontSize: 24 },
  title: { fontSize: 16, fontWeight: "600", color: "#333" },
  subtitle: { fontSize: 12, color: "#888" },
  emojiRow: { flexDirection: "row", gap: 16, marginBottom: 8 },
  emojiStat: { fontSize: 14, color: "#555" },
  progressBar: { flexDirection: "row", height: 6, borderRadius: 3, backgroundColor: "#eee", overflow: "hidden" },
  progressSegment: { height: "100%" },
  noData: { fontSize: 13, color: "#bbb", fontStyle: "italic" },
});
