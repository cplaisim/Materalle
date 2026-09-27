import { View, Text, TextInput, TouchableOpacity, StyleSheet, SectionList, Alert, ActivityIndicator } from "react-native";
import { useState, useEffect, useMemo } from "react";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getGroceryList, addGroceryItem, removeGroceryItems } from "@/lib/api";
import { GroceryItem } from "@/lib/types";

const CATEGORIES = ["VEGETABLE", "FRUIT", "GRAIN", "PROTEIN", "DRINK", "OTHER"] as const;
const CATEGORY_COLORS: Record<string, string> = {
  VEGETABLE: "#27ae60",
  FRUIT: "#e67e22",
  GRAIN: "#f1c40f",
  PROTEIN: "#e74c3c",
  DRINK: "#3498db",
  OTHER: "#95a5a6",
};
const CATEGORY_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  VEGETABLE: "leaf",
  FRUIT: "nutrition",
  GRAIN: "sunny",
  PROTEIN: "fish",
  DRINK: "water",
  OTHER: "ellipsis-horizontal",
};

export default function GroceryScreen() {
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<string>("OTHER");
  const [adding, setAdding] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectMode, setSelectMode] = useState(false);

  useEffect(() => { loadItems(); }, []);

  const loadItems = async () => {
    try {
      const data = await getGroceryList();
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!name.trim()) return;
    setAdding(true);
    try {
      await addGroceryItem(name.trim(), category);
      setName("");
      await loadItems();
    } catch {
      Alert.alert("Error", "Failed to add item");
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    Alert.alert("Delete", `Remove ${selectedIds.size} item(s)?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await removeGroceryItems(Array.from(selectedIds));
            setItems((prev) => prev.filter((i) => !selectedIds.has(i.id)));
            setSelectedIds(new Set());
            setSelectMode(false);
          } catch {
            Alert.alert("Error", "Failed to remove items");
          }
        },
      },
    ]);
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const sections = useMemo(() => {
    const grouped: Record<string, GroceryItem[]> = {};
    for (const item of items) {
      const cat = item.category || "OTHER";
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(item);
    }
    return Object.entries(grouped).map(([cat, data]) => ({ title: cat, data }));
  }, [items]);

  if (loading) {
    return <View style={styles.centered}><ActivityIndicator size="large" color="#7A9B6D" /></View>;
  }

  return (
    <View style={styles.container}>
      {/* Add Item Row */}
      <View style={styles.addRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Add item..."
          placeholderTextColor="#aaa"
          value={name}
          onChangeText={setName}
          onSubmitEditing={handleAdd}
          returnKeyType="done"
        />
        <TouchableOpacity style={styles.addBtn} onPress={handleAdd} disabled={adding}>
          {adding ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="add" size={22} color="#fff" />}
        </TouchableOpacity>
      </View>

      {/* Category Picker — scrollable chips */}
      <View style={styles.catRow}>
        {CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={[styles.catChip, category === cat && { backgroundColor: CATEGORY_COLORS[cat] }]}
            onPress={() => setCategory(cat)}
          >
            <Ionicons name={CATEGORY_ICONS[cat]} size={14} color={category === cat ? "#fff" : CATEGORY_COLORS[cat]} />
            <Text style={[styles.catChipText, category === cat && { color: "#fff" }]}>
              {cat.charAt(0) + cat.slice(1).toLowerCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Toolbar */}
      <View style={styles.toolbar}>
        <Text style={styles.itemCount}>{items.length} item{items.length !== 1 ? "s" : ""}</Text>
        <View style={styles.toolbarRight}>
          {selectMode && selectedIds.size > 0 && (
            <TouchableOpacity style={styles.deleteBtn} onPress={handleDeleteSelected}>
              <Ionicons name="trash" size={16} color="#fff" />
              <Text style={styles.deleteBtnText}>{selectedIds.size}</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[styles.selectBtn, selectMode && styles.selectBtnActive]}
            onPress={() => { setSelectMode(!selectMode); setSelectedIds(new Set()); }}
          >
            <Text style={[styles.selectBtnText, selectMode && { color: "#fff" }]}>
              {selectMode ? "Done" : "Select"}
            </Text>
          </TouchableOpacity>
          {items.length > 0 && (
            <TouchableOpacity style={styles.menuBtn} onPress={() => router.push("/menu")}>
              <Ionicons name="restaurant" size={16} color="#7A9B6D" />
              <Text style={styles.menuBtnText}>Menu</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Items List */}
      <SectionList
        sections={sections}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <View style={[styles.catDot, { backgroundColor: CATEGORY_COLORS[section.title] || "#999" }]} />
            <Text style={styles.sectionTitle}>{section.title.charAt(0) + section.title.slice(1).toLowerCase()}</Text>
            <Text style={styles.sectionCount}>{section.data.length}</Text>
          </View>
        )}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.itemRow}
            onPress={() => selectMode ? toggleSelect(item.id) : null}
            onLongPress={() => { setSelectMode(true); toggleSelect(item.id); }}
            activeOpacity={selectMode ? 0.6 : 1}
          >
            {selectMode && (
              <Ionicons
                name={selectedIds.has(item.id) ? "checkbox" : "square-outline"}
                size={22}
                color={selectedIds.has(item.id) ? "#7A9B6D" : "#ccc"}
              />
            )}
            <Text style={styles.itemName}>{item.name}</Text>
            {!selectMode && (
              <TouchableOpacity
                onPress={() => {
                  Alert.alert("Delete", `Remove ${item.name}?`, [
                    { text: "Cancel", style: "cancel" },
                    {
                      text: "Delete", style: "destructive",
                      onPress: async () => {
                        try {
                          await removeGroceryItems([item.id]);
                          setItems((prev) => prev.filter((i) => i.id !== item.id));
                        } catch { Alert.alert("Error", "Failed to remove"); }
                      },
                    },
                  ]);
                }}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Ionicons name="close-circle" size={20} color="#ddd" />
              </TouchableOpacity>
            )}
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Ionicons name="cart-outline" size={48} color="#ccc" />
            <Text style={styles.emptyText}>No grocery items yet</Text>
            <Text style={styles.emptySubtext}>Add items above to get started</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#FDF8F3" },

  // Add row
  addRow: { flexDirection: "row", paddingHorizontal: 16, paddingTop: 12, paddingBottom: 6, gap: 8 },
  addInput: {
    flex: 1,
    backgroundColor: "#fff",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 15,
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  addBtn: {
    backgroundColor: "#7A9B6D",
    borderRadius: 12,
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },

  // Category chips
  catRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 6,
  },
  catChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  catChipText: { fontSize: 12, fontWeight: "600", color: "#666" },

  // Toolbar
  toolbar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  toolbarRight: { flexDirection: "row", alignItems: "center", gap: 8 },
  itemCount: { fontSize: 13, color: "#999", fontWeight: "500" },
  selectBtn: {
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e8e0d8",
  },
  selectBtnActive: { backgroundColor: "#7A9B6D", borderColor: "#7A9B6D" },
  selectBtnText: { fontSize: 13, fontWeight: "600", color: "#666" },
  deleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#e74c3c",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  deleteBtnText: { fontSize: 13, fontWeight: "600", color: "#fff" },
  menuBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: "#7A9B6D",
  },
  menuBtnText: { fontSize: 13, fontWeight: "600", color: "#7A9B6D" },

  // List
  list: { paddingHorizontal: 16, paddingBottom: 32 },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    paddingTop: 16,
  },
  catDot: { width: 10, height: 10, borderRadius: 5 },
  sectionTitle: { fontSize: 15, fontWeight: "600", color: "#333" },
  sectionCount: { fontSize: 12, color: "#999" },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#fff",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 4,
  },
  itemName: { flex: 1, fontSize: 15, color: "#444" },

  // Empty
  emptyState: { alignItems: "center", padding: 48, gap: 8 },
  emptyText: { fontSize: 16, fontWeight: "600", color: "#bbb" },
  emptySubtext: { fontSize: 13, color: "#ccc" },
});
