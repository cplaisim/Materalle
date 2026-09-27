import AgentChat from "@/components/AgentChat";
import { QuickAction } from "@/components/AgentChat";

const TOPICS: QuickAction[] = [
  { label: "Emotional Awareness", icon: "heart-outline", prompt: "Suggest an emotional awareness activity for today's group." },
  { label: "Sharing", icon: "people-outline", prompt: "Suggest a sharing and turn-taking activity for the children." },
  { label: "Empathy", icon: "hand-left-outline", prompt: "Suggest an empathy-building activity for today." },
  { label: "Conflict Resolution", icon: "git-merge-outline", prompt: "Suggest a conflict resolution activity for young children." },
  { label: "Self-Regulation", icon: "bulb-outline", prompt: "Suggest a self-regulation and calming activity for the group." },
  { label: "Social Play", icon: "happy-outline", prompt: "Suggest a cooperative social play activity for the children." },
  { label: "Communication", icon: "chatbubbles-outline", prompt: "Suggest a communication and language activity for the group." },
];

export default function GraceScreen() {
  return (
    <AgentChat
      agent="grace"
      agentName="Grace"
      agentColor="#C48DB8"
      greeting="Hello! I'm Grace, your social-emotional development guide. How can I help today?"
      placeholder="Ask Grace..."
      quickActions={TOPICS}
    />
  );
}
