import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useState, useEffect, useCallback } from "react";
import { Ionicons } from "@expo/vector-icons";
import { getActivityDashboard, rateActivity } from "@/lib/api";

interface DayTab {
  offset: number;
  short: string;
  date: string;
  is_active: boolean;
  is_today: boolean;
}

interface ActivityEntry {
  id: number;
  title: string;
  description?: string;
  activity_type?: string;
  agent: string;
  start_time?: string;
  child_ratings_json: Record<string, { rating: number }>;
}

interface ChildInfo {
  child_id: number;
  child_name: string;
}

const AGENT_COLORS: Record<string, string> = {
  sage: "#7A9B6D",
  grace: "#C48DB8",
  patience: "#7BAAC4",
};

const RATING_EMOJIS = [
  { rating: 3, emoji: "😄", label: "Like" },
  { rating: 2, emoji: "😐", label: "Okay" },
  { rating: 1, emoji: "😞", label: "Dislike" },
];

export default function DashboardScreen() {
  const [dayOffset, setDayOffset] = useState(0);
  const [dayTabs, setDayTabs] = useState<DayTab[]>([]);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [children, setChildren] = useState<ChildInfo[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [ratingsMap, setRatingsMap] = useState<Record<number, Record<number, number>>>({});
  const [saving, setSaving] = useState(false);

  const loadDashboard = useCallback(async (offset: number) => {
    setLoading(true);
    try {
      const data = await getActivityDashboard(offset);
      setDayTabs(data.day_tabs || []);
      setActivities(data.all_activities || []);
      setChildren(data.children || []);
      setCurrentIdx(0);
      // Build ratings map from activities
      const map: Record<number, Record<number, number>> = {};
      for (const act of (data.all_activities || [])) {
        map[act.id] = {};
        for (const [childId, info] of Object.entries(act.child_ratings_json || {})) {
          map[act.id][Number(childId)] = (info as { rating: number }).rating;
        }
      }
      setRatingsMap(map);
    } catch {
      // Fallback: show empty state
      setActivities([]);
      setChildren([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard(dayOffset);
  }, [dayOffset, loadDashboard]);

  const currentActivity = activities[currentIdx];

  const handleRate = (childId: number, rating: number) => {
    if (!currentActivity) return;
    setRatingsMap((prev) => ({
      ...prev,
      [currentActivity.id]: { ...prev[currentActivity.id], [childId]: rating },
    }));
  };

  const saveAllRatings = async () => {
    if (!currentActivity) return;
    setSaving(true);
    let saved = 0;
    const entryRatings = ratingsMap[currentActivity.id] || {};
    for (const [childId, rating] of Object.entries(entryRatings)) {
      try {
        await rateActivity(currentActivity.id, Number(childId), rating);
        saved++;
      } catch {
        // continue
      }
    }
    setSaving(false);
    if (saved > 0) Alert.alert("Saved", `${saved} rating${saved > 1 ? "s" : ""} saved!`);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#7A9B6D" />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Activity Dashboard</Text>

      {/* Day Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dayTabsRow} contentContainerStyle={styles.dayTabsContent}>
        {dayTabs.map((tab) => (
          <TouchableOpacity
            key={tab.offset}
            style={[styles.dayTab, tab.is_active && styles.dayTabActive, tab.is_today && !tab.is_active && styles.dayTabToday]}
            onPress={() => setDayOffset(tab.offset)}
          >
            <Text style={[styles.dayTabText, tab.is_active && styles.dayTabTextActive]}>{tab.short}</Text>
            <Text style={[styles.dayTabDate, tab.is_active && styles.dayTabTextActive]}>{tab.date}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {activities.length > 0 ? (
        <>
          {/* Activity Carousel */}
          <View style={styles.card}>
            <View style={styles.carouselHeader}>
              <TouchableOpacity onPress={() => setCurrentIdx((currentIdx - 1 + activities.length) % activities.length)}>
                <Ionicons name="chevron-back" size={22} color="#666" />
              </TouchableOpacity>
              <Text style={styles.counter}>{currentIdx + 1} / {activities.length}</Text>
              <TouchableOpacity onPress={() => setCurrentIdx((currentIdx + 1) % activities.length)}>
                <Ionicons name="chevron-forward" size={22} color="#666" />
              </TouchableOpacity>
            </View>

            {currentActivity && (
              <View style={styles.activityContent}>
                <View style={styles.badgeRow}>
                  <View style={[styles.agentBadge, { backgroundColor: AGENT_COLORS[currentActivity.agent] || "#999" }]}>
                    <Text style={styles.agentBadgeText}>{currentActivity.agent}</Text>
                  </View>
                  {currentActivity.start_time && <Text style={styles.timeText}>{currentActivity.start_time}</Text>}
                  {currentActivity.activity_type && (
                    <View style={styles.typeBadge}>
                      <Text style={styles.typeBadgeText}>{currentActivity.activity_type}</Text>
                    </View>
                  )}
                </View>
                <Text style={styles.activityTitle}>{currentActivity.title}</Text>
                {currentActivity.description && <Text style={styles.activityDesc}>{currentActivity.description}</Text>}
              </View>
            )}
          </View>

          {/* Child Ratings */}
          <View style={styles.card}>
            <View style={styles.participantsHeader}>
              <Text style={styles.participantsTitle}>Participants</Text>
              <TouchableOpacity style={styles.saveBtn} onPress={saveAllRatings} disabled={saving}>
                <Ionicons name="checkmark" size={16} color="#fff" />
                <Text style={styles.saveBtnText}>{saving ? "Saving..." : "Save All"}</Text>
              </TouchableOpacity>
            </View>

            {children.length > 0 ? (
              children.map((child) => {
                const childRating = currentActivity ? (ratingsMap[currentActivity.id]?.[child.child_id]) : undefined;
                return (
                  <View key={child.child_id} style={styles.childRow}>
                    <Text style={styles.childName}>{child.child_name}</Text>
                    <View style={styles.ratingBtns}>
                      {RATING_EMOJIS.map(({ rating, emoji }) => (
                        <TouchableOpacity
                          key={rating}
                          style={[styles.rateBtn, childRating === rating && styles.rateBtnSelected]}
                          onPress={() => handleRate(child.child_id, rating)}
                        >
                          <Text style={styles.rateEmoji}>{emoji}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                );
              })
            ) : (
              <Text style={styles.emptyText}>No children checked in.</Text>
            )}
          </View>
        </>
      ) : (
        <View style={styles.emptyCard}>
          <Ionicons name="calendar-outline" size={48} color="#ccc" />
          <Text style={styles.emptyText}>No activities scheduled for this day.</Text>
          <TouchableOpacity onPress={() => loadDashboard(dayOffset)}>
            <Text style={styles.retryText}>Tap to refresh</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },
  title: { fontSize: 24, fontWeight: "700", color: "#333", marginBottom: 12 },
  dayTabsRow: { marginBottom: 16 },
  dayTabsContent: { gap: 6 },
  dayTab: {
    backgroundColor: "#fff",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 8,
    minWidth: 70,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  dayTabActive: { backgroundColor: "#333", borderColor: "#333" },
  dayTabToday: { borderColor: "#7A9B6D" },
  dayTabText: { fontSize: 13, fontWeight: "600", color: "#555" },
  dayTabDate: { fontSize: 10, color: "#999", marginTop: 2 },
  dayTabTextActive: { color: "#fff" },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  carouselHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  counter: { fontSize: 14, fontWeight: "600", color: "#555" },
  activityContent: {},
  badgeRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  agentBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  agentBadgeText: { color: "#fff", fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  typeBadge: { backgroundColor: "#f0f0f0", borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  typeBadgeText: { fontSize: 11, color: "#666" },
  timeText: { fontSize: 12, color: "#999" },
  activityTitle: { fontSize: 18, fontWeight: "600", color: "#333", marginBottom: 4 },
  activityDesc: { fontSize: 14, color: "#666", lineHeight: 20 },
  participantsHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  participantsTitle: { fontSize: 16, fontWeight: "600", color: "#333" },
  saveBtn: { flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: "#7A9B6D", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  saveBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  childRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0ece8" },
  childName: { fontSize: 15, fontWeight: "500", color: "#333" },
  ratingBtns: { flexDirection: "row", gap: 4 },
  rateBtn: { padding: 6, borderRadius: 8, opacity: 0.4 },
  rateBtnSelected: { opacity: 1, backgroundColor: "#f0ece8" },
  rateEmoji: { fontSize: 20 },
  emptyCard: { alignItems: "center", padding: 40, gap: 12 },
  emptyText: { fontSize: 14, color: "#999", textAlign: "center" },
  retryText: { fontSize: 14, color: "#7A9B6D", fontWeight: "500" },
});
