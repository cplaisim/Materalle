import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useState, useEffect, useCallback } from "react";
import { AuthContext } from "@/lib/auth";
import { User } from "@/lib/types";
import { setToken } from "@/lib/api";

export default function RootLayout() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setAuthToken] = useState<string | null>(null);
  const [isLoading] = useState(false);
  const router = useRouter();
  const segments = useSegments();

  const signIn = useCallback((t: string, userData: User) => {
    setAuthToken(t);
    setToken(t);
    setUser(userData);
  }, []);

  const signOut = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (isLoading) return;
    const inAuthGroup = segments[0] === "(auth)";
    if (!user && !inAuthGroup) {
      router.replace("/(auth)/login");
    } else if (user && inAuthGroup) {
      router.replace("/(tabs)");
    }
  }, [user, segments, isLoading]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, signIn, signOut }}>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#FDF8F3" },
          headerTintColor: "#333",
          contentStyle: { backgroundColor: "#FDF8F3" },
        }}
      >
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="child/[id]" options={{ title: "Child Dashboard" }} />
        <Stack.Screen name="child/activities" options={{ title: "Activities" }} />
        <Stack.Screen name="enroll" options={{ title: "Enroll Child" }} />
        <Stack.Screen name="schedule" options={{ title: "Weekly Schedule" }} />
        <Stack.Screen name="grocery" options={{ title: "Grocery List" }} />
        <Stack.Screen name="menu" options={{ title: "Menu Generator" }} />
      </Stack>
    </AuthContext.Provider>
  );
}
