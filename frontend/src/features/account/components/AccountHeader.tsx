import { useEffect, useRef, useState } from "react";
import {
  Alert, Animated, Modal, Pressable, StyleSheet, Text, View, useWindowDimensions,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { useAuth } from "../../../app/providers/AuthProvider";
import { useMyProfile } from "../hooks/useMyProfile";
import { ProtectedAvatar } from "./ProtectedAvatar";

export function AccountHeader() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const [open, setOpen] = useState(false);
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const offset = useRef(new Animated.Value(-width)).current;
  const { logout } = useAuth();
  const profile = useMyProfile();
  useEffect(() => {
    if (open) {
      offset.setValue(-width);
      Animated.timing(offset, { toValue: 0, duration: 180, useNativeDriver: true }).start();
    }
  }, [offset, open, width]);
  function confirmLogout() {
    Alert.alert("로그아웃할까요?", undefined, [
      { text: "취소", style: "cancel" },
      { text: "로그아웃", onPress: () => { setOpen(false); void logout().catch(() => undefined); } },
    ]);
  }
  function settings() { setOpen(false); navigation.navigate("AppSettings"); }
  return <>
    <View style={styles.header}>
      <Pressable accessibilityRole="button" accessibilityLabel="사이드바 열기" onPress={() => setOpen(true)} style={styles.icon}><Text style={styles.blue}>☰</Text></Pressable>
      <Text accessibilityRole="header" style={styles.logo}>T·L</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="앱 설정" onPress={settings} style={styles.icon}><Text style={styles.blue}>⚙</Text></Pressable>
    </View>
    <Modal visible={open} transparent animationType="none" onRequestClose={() => setOpen(false)}>
      <View style={styles.overlay}>
        <Pressable accessibilityRole="button" accessibilityLabel="사이드바 닫기" style={StyleSheet.absoluteFill} onPress={() => setOpen(false)} />
        <Animated.View accessibilityViewIsModal style={[styles.drawer, { width: Math.min(width * .78, 360), paddingTop: insets.top, transform: [{ translateX: offset }] }]}>
          <View style={styles.header}><Text style={styles.logo}>T·L</Text><Pressable accessibilityRole="button" accessibilityLabel="앱 설정" onPress={settings} style={styles.icon}><Text style={styles.blue}>⚙</Text></Pressable></View>
          <View style={styles.identity}>
            <ProtectedAvatar url={profile.data?.profile_image_url} size={72} />
            <Text style={styles.nickname}>{profile.data?.nickname ?? (profile.isError ? "프로필 조회 실패" : "불러오는 중…")}</Text>
          </View>
          <Pressable style={styles.row} accessibilityRole="button" onPress={() => { setOpen(false); navigation.navigate("MyInfo"); }}><Text style={styles.label}>내 정보</Text></Pressable>
          <Pressable style={styles.row} accessibilityRole="button" onPress={confirmLogout}><Text style={styles.label}>로그아웃</Text></Pressable>
        </Animated.View>
      </View>
    </Modal>
  </>;
}
const styles = StyleSheet.create({
  header: { minHeight: 56, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 12, borderBottomWidth: 1, borderColor: "#9B95FF" },
  icon: { minWidth: 48, minHeight: 48, justifyContent: "center", alignItems: "center" },
  blue: { color: "#3324DB", fontSize: 28 },
  logo: { color: "#414DB1", fontSize: 28, fontWeight: "800" },
  overlay: { flex: 1, backgroundColor: "#0006" },
  drawer: { height: "100%", backgroundColor: "white" },
  identity: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, paddingVertical: 40, gap: 18 },
  nickname: { fontSize: 18, flexShrink: 1, textDecorationLine: "underline" },
  row: { paddingHorizontal: 28, minHeight: 64, justifyContent: "center", borderTopWidth: 1, borderColor: "#DDD" },
  label: { fontSize: 18, color: "#111" },
});
