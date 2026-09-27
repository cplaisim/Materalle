import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import { useState } from "react";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import AgentChat from "@/components/AgentChat";

const QUICK_ACTIONS = [
  { label: "Grocery", icon: "cart" as const, route: "/grocery" },
  { label: "Menu", icon: "restaurant" as const, route: "/menu" },
  { label: "Schedule", icon: "calendar" as const, route: "/schedule" },
  { label: "Dashboard", icon: "bar-chart" as const, route: "/(tabs)/dashboard" },
];

export default function SageScreen() {
  const [showChat, setShowChat] = useState(false);

  if (showChat) {
    return (
      <View style={styles.container}>
        <TouchableOpacity style={styles.backBtn} onPress={() => setShowChat(false)}>
          <Ionicons name="arrow-back" size={20} color="#7A9B6D" />
          <Text style={styles.backText}>Sage Tools</Text>
        </TouchableOpacity>
        <AgentChat
          agent="sage"
          agentName="Sage"
          agentColor="#7A9B6D"
          greeting="Hello! I'm Sage, your nutrition and menu planning guide. How can I help today?"
          placeholder="Ask Sage..."
        />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Agent Header */}
      <View style={styles.header}>
        <Text style={styles.agentEmoji}>🌿</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.agentName}>Sage</Text>
          <Text style={styles.agentDesc}>Nutrition, meals & regulatory compliance</Text>
        </View>
      </View>

      {/* Quick Actions Grid */}
      <Text style={styles.sectionTitle}>Tools</Text>
      <View style={styles.grid}>
        {QUICK_ACTIONS.map((action) => (
          <TouchableOpacity
            key={action.label}
            style={styles.actionCard}
            onPress={() => router.push(action.route as any)}
            activeOpacity={0.7}
          >
            <View style={styles.actionIcon}>
              <Ionicons name={action.icon} size={24} color="#7A9B6D" />
            </View>
            <Text style={styles.actionLabel}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Chat Button */}
      <Text style={styles.sectionTitle}>Ask Sage</Text>
      <TouchableOpacity style={styles.chatBtn} onPress={() => setShowChat(true)} activeOpacity={0.7}>
        <Ionicons name="chatbubbles" size={22} color="#fff" />
        <Text style={styles.chatBtnText}>Open Chat</Text>
        <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16, paddingBottom: 32 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 16,
    borderLeftWidth: 4,
    borderLeftColor: "#7A9B6D",
    marginBottom: 8,
  },
  agentEmoji: { fontSize: 36 },
  agentName: { fontSize: 22, fontWeight: "700", color: "#333" },
  agentDesc: { fontSize: 13, color: "#888", marginTop: 2 },
  sectionTitle: { fontSize: 16, fontWeight: "600", color: "#555", marginTop: 20, marginBottom: 10 },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  actionCard: {
    width: "47%",
    backgroundColor: "#fff",
    borderRadius: 14,
    paddingVertical: 20,
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: "rgba(122,155,109,0.1)",
    alignItems: "center",
    justifyContent: "center",
  },
  actionLabel: { fontSize: 14, fontWeight: "600", color: "#444" },
  chatBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#7A9B6D",
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 20,
  },
  chatBtnText: { flex: 1, fontSize: 16, fontWeight: "600", color: "#fff" },
  backBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
    backgroundColor: "#fff",
  },
  backText: { fontSize: 15, fontWeight: "600", color: "#7A9B6D" },
});
