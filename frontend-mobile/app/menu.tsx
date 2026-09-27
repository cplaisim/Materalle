import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useState, useEffect, useMemo } from "react";
import { Ionicons } from "@expo/vector-icons";
import { getGroceryList, generateMenu } from "@/lib/api";
import { GroceryItem } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  VEGETABLE: "#27ae60",
  FRUIT: "#e67e22",
  GRAIN: "#f1c40f",
  PROTEIN: "#e74c3c",
  DRINK: "#3498db",
  OTHER: "#95a5a6",
};

export default function MenuScreen() {
  const [groceryItems, setGroceryItems] = useState<GroceryItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [period, setPeriod] = useState(4);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [menu, setMenu] = useState<Record<string, Record<string, string>> | null>(null);

  useEffect(() => { loadGroceries(); }, []);

  const loadGroceries = async () => {
    try {
      const data = await getGroceryList();
      const items = Array.isArray(data) ? data : [];
      setGroceryItems(items);
      setSelectedIds(new Set(items.map((i) => i.id)));
    } catch {
      setGroceryItems([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === groceryItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(groceryItems.map((i) => i.id)));
    }
  };

  const grouped = useMemo(() => {
    const map: Record<string, GroceryItem[]> = {};
    for (const item of groceryItems) {
      const cat = item.category || "OTHER";
      if (!map[cat]) map[cat] = [];
      map[cat].push(item);
    }
    return Object.entries(map);
  }, [groceryItems]);

  const handleGenerate = async () => {
    if (selectedIds.size === 0) {
      Alert.alert("Select Ingredients", "Pick at least one grocery item to generate a menu.");
      return;
    }
    setGenerating(true);
    try {
      const data = await generateMenu(Array.from(selectedIds), period);
      setMenu(data.menu || data);
    } catch {
      Alert.alert("Error", "Failed to generate menu");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return <View style={styles.centered}><ActivityIndicator size="large" color="#7A9B6D" /></View>;
  }

  const allSelected = selectedIds.size === groceryItems.length;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <Text style={styles.title}>Menu Generator</Text>
      <Text style={styles.subtitle}>CACFP-compliant menus from your grocery items</Text>

      {/* Period */}
      <View style={styles.periodSection}>
        <Text style={styles.label}>Weeks</Text>
        <View style={styles.periodRow}>
          {[1, 2, 3, 4].map((w) => (
            <TouchableOpacity
              key={w}
              style={[styles.periodBtn, period === w && styles.periodActive]}
              onPress={() => setPeriod(w)}
            >
              <Text style={[styles.periodText, period === w && styles.periodTextActive]}>{w}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Ingredients */}
      <View style={styles.ingredientHeader}>
        <Text style={styles.label}>Ingredients ({selectedIds.size}/{groceryItems.length})</Text>
        <TouchableOpacity onPress={toggleAll} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={styles.toggleAllText}>{allSelected ? "Deselect All" : "Select All"}</Text>
        </TouchableOpacity>
      </View>

      {groceryItems.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="cart-outline" size={32} color="#ccc" />
          <Text style={styles.emptyText}>No grocery items yet.</Text>
          <Text style={styles.emptySubtext}>Add items to the grocery list first.</Text>
        </View>
      ) : (
        grouped.map(([cat, catItems]) => (
          <View key={cat} style={styles.catGroup}>
            <View style={styles.catLabel}>
              <View style={[styles.catDot, { backgroundColor: CATEGORY_COLORS[cat] || "#999" }]} />
              <Text style={styles.catName}>{cat.charAt(0) + cat.slice(1).toLowerCase()}</Text>
            </View>
            <View style={styles.chipWrap}>
              {catItems.map((item) => {
                const selected = selectedIds.has(item.id);
                return (
                  <TouchableOpacity
                    key={item.id}
                    style={[styles.chip, selected && { backgroundColor: CATEGORY_COLORS[cat] || "#7A9B6D", borderColor: CATEGORY_COLORS[cat] || "#7A9B6D" }]}
                    onPress={() => toggleItem(item.id)}
                    activeOpacity={0.6}
                  >
                    <Text style={[styles.chipText, selected && { color: "#fff" }]}>{item.name}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ))
      )}

      {/* Generate */}
      <TouchableOpacity
        style={[styles.generateBtn, generating && { opacity: 0.7 }]}
        onPress={handleGenerate}
        disabled={generating || groceryItems.length === 0}
        activeOpacity={0.7}
      >
        {generating ? (
          <>
            <ActivityIndicator size="small" color="#fff" />
            <Text style={styles.generateText}>Generating Menu...</Text>
          </>
        ) : (
          <>
            <Ionicons name="restaurant" size={20} color="#fff" />
            <Text style={styles.generateText}>Generate {period}-Week Menu</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Menu Results */}
      {menu && (
        <View style={styles.menuSection}>
          <Text style={styles.menuTitle}>Generated Menu</Text>
          {Object.entries(menu).map(([week, meals]) => (
            <View key={week} style={styles.weekCard}>
              <Text style={styles.weekLabel}>{week}</Text>
              {typeof meals === "object" && Object.entries(meals).map(([meal, content]) => (
                <View key={meal} style={styles.mealRow}>
                  <Text style={styles.mealType}>{meal.replace(/_/g, " ")}</Text>
                  <Text style={styles.mealContent}>{typeof content === "string" ? content : JSON.stringify(content)}</Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  content: { padding: 16, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },
  title: { fontSize: 22, fontWeight: "700", color: "#333" },
  subtitle: { fontSize: 13, color: "#999", marginBottom: 16 },

  // Period
  periodSection: { marginBottom: 16 },
  label: { fontSize: 14, fontWeight: "600", color: "#555", marginBottom: 8 },
  periodRow: { flexDirection: "row", gap: 8 },
  periodBtn: {
    flex: 1,
    alignItems: "center",
    borderRadius: 10,
    paddingVertical: 12,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  periodActive: { backgroundColor: "#7A9B6D", borderColor: "#7A9B6D" },
  periodText: { fontSize: 16, fontWeight: "600", color: "#666" },
  periodTextActive: { color: "#fff" },

  // Ingredients
  ingredientHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  toggleAllText: { fontSize: 13, fontWeight: "600", color: "#7A9B6D" },
  catGroup: { marginBottom: 12 },
  catLabel: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  catDot: { width: 8, height: 8, borderRadius: 4 },
  catName: { fontSize: 13, fontWeight: "600", color: "#888" },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: {
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  chipText: { fontSize: 13, fontWeight: "500", color: "#555" },

  // Empty
  emptyCard: {
    alignItems: "center",
    padding: 32,
    backgroundColor: "#fff",
    borderRadius: 12,
    gap: 6,
  },
  emptyText: { fontSize: 15, fontWeight: "600", color: "#bbb" },
  emptySubtext: { fontSize: 13, color: "#ccc" },

  // Generate
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    backgroundColor: "#7A9B6D",
    borderRadius: 14,
    paddingVertical: 16,
    marginTop: 20,
  },
  generateText: { color: "#fff", fontSize: 16, fontWeight: "700" },

  // Menu results
  menuSection: { marginTop: 24 },
  menuTitle: { fontSize: 18, fontWeight: "700", color: "#333", marginBottom: 12 },
  weekCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  weekLabel: { fontSize: 15, fontWeight: "700", color: "#7A9B6D", marginBottom: 8 },
  mealRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#f0ece8" },
  mealType: { fontSize: 11, fontWeight: "700", color: "#999", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 },
  mealContent: { fontSize: 14, color: "#444", lineHeight: 20 },
});
