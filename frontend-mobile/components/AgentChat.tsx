import { View, Text, TextInput, TouchableOpacity, FlatList, ScrollView, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator } from "react-native";
import { useState, useRef } from "react";
import { Ionicons } from "@expo/vector-icons";
import { sendAgentMessage } from "@/lib/api";

type Message = { id: string; text: string; isUser: boolean };

export interface QuickAction {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  prompt: string;
}

interface AgentChatProps {
  agent: "sage" | "grace" | "patience";
  agentName: string;
  agentColor: string;
  greeting: string;
  placeholder: string;
  quickActions?: QuickAction[];
}

export default function AgentChat({ agent, agentName, agentColor, greeting, placeholder, quickActions }: AgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    { id: "0", text: greeting, isUser: false },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const sendMessage = async (text?: string) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;

    const userMsg: Message = { id: Date.now().toString(), text: msg, isUser: true };
    setMessages((prev) => [...prev, userMsg]);
    if (!text) setInput("");
    setLoading(true);

    try {
      const data = await sendAgentMessage(agent, msg);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), text: data.message || "No response", isUser: false },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), text: "Connection error. Is the server running?", isUser: false },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const showQuickActions = quickActions && quickActions.length > 0 && messages.length <= 1;

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={90}>
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        renderItem={({ item }) => (
          <View style={[styles.messageBubble, item.isUser ? [styles.userBubble, { backgroundColor: agentColor }] : styles.assistantBubble]}>
            <Text style={[styles.messageText, item.isUser && styles.userText]}>{item.text}</Text>
          </View>
        )}
        ListFooterComponent={
          <>
            {loading && (
              <View style={styles.typingRow}>
                <ActivityIndicator size="small" color={agentColor} />
                <Text style={styles.typingText}>{agentName} is thinking...</Text>
              </View>
            )}
            {showQuickActions && (
              <View style={styles.quickActionsSection}>
                <Text style={styles.quickActionsTitle}>Quick Topics</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.quickActionsRow}>
                  {quickActions.map((action) => (
                    <TouchableOpacity
                      key={action.label}
                      style={[styles.quickActionBtn, { borderColor: agentColor }]}
                      onPress={() => sendMessage(action.prompt)}
                      activeOpacity={0.7}
                    >
                      <Ionicons name={action.icon} size={16} color={agentColor} />
                      <Text style={[styles.quickActionText, { color: agentColor }]}>{action.label}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            )}
          </>
        }
      />
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={placeholder}
          placeholderTextColor="#aaa"
          onSubmitEditing={() => sendMessage()}
          returnKeyType="send"
          editable={!loading}
          multiline
        />
        <TouchableOpacity style={[styles.sendBtn, { backgroundColor: agentColor }]} onPress={() => sendMessage()} disabled={loading}>
          <Ionicons name="send" size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FDF8F3" },
  messageList: { padding: 16, paddingBottom: 8 },
  messageBubble: { maxWidth: "80%", padding: 12, borderRadius: 16, marginBottom: 8 },
  userBubble: { alignSelf: "flex-end" },
  assistantBubble: { alignSelf: "flex-start", backgroundColor: "#fff", borderWidth: 1, borderColor: "#eee" },
  messageText: { fontSize: 15, color: "#333", lineHeight: 21 },
  userText: { color: "#fff" },
  typingRow: { flexDirection: "row", alignItems: "center", gap: 8, padding: 8 },
  typingText: { fontSize: 13, color: "#999" },
  inputRow: { flexDirection: "row", padding: 12, gap: 8, borderTopWidth: 1, borderTopColor: "#eee", backgroundColor: "#fff" },
  input: { flex: 1, backgroundColor: "#f5f5f5", borderRadius: 20, paddingHorizontal: 16, paddingVertical: 10, fontSize: 15, maxHeight: 100 },
  sendBtn: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  // Quick actions
  quickActionsSection: { marginTop: 8, marginBottom: 8 },
  quickActionsTitle: { fontSize: 13, fontWeight: "600", color: "#999", marginBottom: 8, paddingLeft: 4 },
  quickActionsRow: { gap: 8, paddingRight: 16 },
  quickActionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1.5,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: "#fff",
  },
  quickActionText: { fontSize: 13, fontWeight: "600" },
});
