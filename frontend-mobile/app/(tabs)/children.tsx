import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, Alert, RefreshControl } from "react-native";
import { useState, useCallback } from "react";
import { router, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getChildren, checkInOut } from "@/lib/api";
import { Child } from "@/lib/types";
import ChildCard from "@/components/ChildCard";

export default function ChildrenScreen() {
  const [children, setChildrenList] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadChildren = useCallback(async () => {
    try {
      const data = await getChildren();
      setChildrenList(Array.isArray(data) ? data : []);
    } catch {
      // Show empty state
      setChildrenList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadChildren();
    }, [loadChildren])
  );

  const handleCheckIn = async (child: Child) => {
    try {
      await checkInOut(child.child_id, "in");
      setChildrenList((prev) => prev.map((c) => c.child_id === child.child_id ? { ...c, is_checked_in: true } : c));
    } catch {
      Alert.alert("Error", "Failed to check in");
    }
  };

  const handleCheckOut = async (child: Child) => {
    try {
      await checkInOut(child.child_id, "out");
      setChildrenList((prev) => prev.map((c) => c.child_id === child.child_id ? { ...c, is_checked_in: false } : c));
    } catch {
      Alert.alert("Error", "Failed to check out");
    }
  };

  const checkedInCount = children.filter((c) => c.is_checked_in).length;

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#7A9B6D" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Children</Text>
          <Text style={styles.subtitle}>{checkedInCount} of {children.length} checked in</Text>
        </View>
        <TouchableOpacity style={styles.enrollBtn} onPress={() => router.push("/enroll")}>
          <Ionicons name="person-add" size={16} color="#fff" />
          <Text style={styles.enrollBtnText}>Enroll</Text>
        </TouchableOpacity>
      </View>

      {/* List */}
      <FlatList
        data={children}
        keyExtractor={(item) => String(item.child_id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadChildren(); }} tintColor="#7A9B6D" />}
        renderItem={({ item }) => (
          <ChildCard
            child={item}
            onPress={() => router.push(`/child/${item.child_id}`)}
            onCheckIn={() => handleCheckIn(item)}
            onCheckOut={() => handleCheckOut(item)}
          />
        )}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Ionicons name="people-outline" size={48} color="#ccc" />
            <Text style={styles.emptyText}>No children enrolled yet.</Text>
            <TouchableOpacity style={styles.enrollBtn} onPress={() => router.push("/enroll")}>
              <Text style={styles.enrollBtnText}>Enroll a Child</Text>
            </TouchableOpacity>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: "700", color: "#333" },
  subtitle: { fontSize: 13, color: "#888", marginTop: 2 },
  enrollBtn: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#7A9B6D", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  enrollBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
  list: { padding: 16, paddingTop: 8 },
  emptyState: { alignItems: "center", padding: 40, gap: 12 },
  emptyText: { fontSize: 15, color: "#999" },
});
