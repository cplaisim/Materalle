import AgentChat from "@/components/AgentChat";
import { QuickAction } from "@/components/AgentChat";

const TOPICS: QuickAction[] = [
  { label: "Fine Motor", icon: "hand-left-outline", prompt: "Suggest a fine motor skills activity for today's group." },
  { label: "Gross Motor", icon: "walk-outline", prompt: "Suggest a gross motor activity for the children." },
  { label: "Hand-Eye", icon: "eye-outline", prompt: "Suggest a hand-eye coordination activity for young children." },
  { label: "Balance", icon: "fitness-outline", prompt: "Suggest a balance and coordination activity for the group." },
  { label: "Sensory", icon: "color-palette-outline", prompt: "Suggest a sensory motor activity for the children." },
];

export default function PatienceScreen() {
  return (
    <AgentChat
      agent="patience"
      agentName="Patience"
      agentColor="#7BAAC4"
      greeting="Hello! I'm Patience, your motor skills and physical development guide. How can I help today?"
      placeholder="Ask Patience..."
      quickActions={TOPICS}
    />
  );
}
