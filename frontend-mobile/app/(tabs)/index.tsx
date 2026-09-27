import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "@/lib/auth";

const quickActions = [
  { label: "Activity Dashboard", icon: "grid-outline" as const, route: "/(tabs)/dashboard" },
  { label: "Children", icon: "people-outline" as const, route: "/(tabs)/children" },
  { label: "Enroll Child", icon: "person-add-outline" as const, route: "/enroll" },
  { label: "Weekly Schedule", icon: "calendar-outline" as const, route: "/schedule" },
  { label: "Grocery List", icon: "cart-outline" as const, route: "/grocery" },
  { label: "Menu Generator", icon: "restaurant-outline" as const, route: "/menu" },
];

const agents = [
  { name: "Sage", description: "Nutrition & menu planning", color: "#7A9B6D", route: "/(tabs)/sage", icon: "🌿" },
  { name: "Grace", description: "Social-emotional development", color: "#C48DB8", route: "/(tabs)/grace", icon: "💜" },
  { name: "Patience", description: "Motor skills & physical development", color: "#7BAAC4", route: "/(tabs)/patience", icon: "💪" },
];

export default function HomeScreen() {
  const { user } = useAuth();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Happy Caterpillars</Text>
      <Text style={styles.subtitle}>Welcome{user ? `, ${user.username}` : ""}!</Text>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionsGrid}>
        {quickActions.map((action) => (
          <TouchableOpacity key={action.label} style={styles.actionCard} onPress={() => router.push(action.route as never)} activeOpacity={0.7}>
            <Ionicons name={action.icon} size={24} color="#7A9B6D" />
            <Text style={styles.actionLabel}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Agent Cards */}
      <Text style={styles.sectionTitle}>AI Agents</Text>
      <View style={styles.cardsContainer}>
        {agents.map((agent) => (
          <TouchableOpacity
            key={agent.name}
            style={[styles.agentCard, { borderLeftColor: agent.color }]}
            onPress={() => router.push(agent.route as never)}
            activeOpacity={0.7}
          >
            <Text style={styles.agentIcon}>{agent.icon}</Text>
            <View style={styles.agentInfo}>
              <Text style={styles.agentName}>{agent.name}</Text>
              <Text style={styles.agentDesc}>{agent.description}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#ccc" />
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 20, paddingTop: 16 },
  title: { fontSize: 28, fontWeight: "700", color: "#333", marginBottom: 2 },
  subtitle: { fontSize: 15, color: "#888", marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: "600", color: "#333", marginBottom: 12, marginTop: 8 },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 24 },
  actionCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    width: "48%",
    flexGrow: 1,
    alignItems: "center",
    gap: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  actionLabel: { fontSize: 13, color: "#555", textAlign: "center", fontWeight: "500" },
  cardsContainer: { gap: 10 },
  agentCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    borderLeftWidth: 4,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  agentIcon: { fontSize: 28, marginRight: 12 },
  agentInfo: { flex: 1 },
  agentName: { fontSize: 17, fontWeight: "600", color: "#333", marginBottom: 2 },
  agentDesc: { fontSize: 13, color: "#888" },
});
