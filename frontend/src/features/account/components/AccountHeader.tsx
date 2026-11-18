import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert, Animated, Image, Modal, Pressable, StyleSheet, Text, View, useWindowDimensions,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { useAuth } from "../../../app/providers/AuthProvider";
import { appImages } from "../../../assets";

import { useMyProfile } from "../hooks/useMyProfile";
import { ProtectedAvatar } from "./ProtectedAvatar";

type AccountHeaderProps = {
  onBack?: () => void;
  backDisabled?: boolean;
  onOpenSettings?: () => void;
  settingsDisabled?: boolean;
};

export function AccountHeader({
  onBack,
  backDisabled = false,
  onOpenSettings,
  settingsDisabled = false,
}: AccountHeaderProps) {
  const { styles } = useStyles();
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const [open, setOpen] = useState(false);
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const offset = useRef(new Animated.Value(-width)).current;
  const dispatchedNavigation = useRef(false);
  const pendingDrawerRoute = useRef<"MyInfo" | "AppSettings" | null>(null);
  const { logout } = useAuth();
  const profile = useMyProfile();
  useEffect(() => {
    if (open) {
      offset.setValue(-width);
      Animated.timing(offset, { toValue: 0, duration: 180, useNativeDriver: true }).start();
    }
  }, [offset, open, width]);
  // Prevent duplicate dispatch until this screen is focused again.
  useEffect(() => navigation.addListener("focus", () => {
    dispatchedNavigation.current = false;
  }), [navigation]);

  const navigateTo = useCallback((route: "MyInfo" | "AppSettings") => {
    if (dispatchedNavigation.current || !navigation.isFocused()) return;
    dispatchedNavigation.current = true;
    if (route === "AppSettings" && onOpenSettings) onOpenSettings();
    else navigation.navigate(route);
  }, [navigation, onOpenSettings]);

  // Close the drawer in React before dispatching the next screen.
  useEffect(() => {
    if (open || pendingDrawerRoute.current === null) return;
    const route = pendingDrawerRoute.current;
    pendingDrawerRoute.current = null;
    navigateTo(route);
  }, [open, navigateTo]);

  function requestNavigation(route: "MyInfo" | "AppSettings") {
    if (
      (route === "AppSettings" && settingsDisabled) ||
      dispatchedNavigation.current ||
      pendingDrawerRoute.current !== null ||
      !navigation.isFocused()
    ) return;

    if (open) {
      pendingDrawerRoute.current = route;
      setOpen(false);
    } else {
      navigateTo(route);
    }
  }

  function confirmLogout() {
    Alert.alert("로그아웃할까요?", undefined, [
      { text: "취소", style: "cancel" },
      { text: "로그아웃", onPress: () => { setOpen(false); void logout().catch(() => undefined); } },
    ]);
  }
  return <>
    <View style={styles.header}>
      {onBack ? (
        <Pressable accessibilityRole="button" accessibilityLabel="메인으로 돌아가기"
          accessibilityState={{ disabled: backDisabled }} disabled={backDisabled}
          onPress={onBack} style={[styles.icon, backDisabled && styles.disabledIcon]}>
          <Text style={styles.blue}>←</Text>
        </Pressable>
      ) : (
        <Pressable accessibilityRole="button" accessibilityLabel="사이드바 열기" onPress={() => setOpen(true)} style={styles.icon}><Text style={styles.blue}>☰</Text></Pressable>
      )}
      <Image accessible accessibilityLabel="Trend Leader 로고" resizeMode="contain" source={appImages.trendLeaderLogo} style={styles.logoImage} />
      <Pressable accessibilityRole="button" accessibilityLabel="앱 설정"
          accessibilityState={{ disabled: settingsDisabled }} disabled={settingsDisabled}
          onPress={() => requestNavigation("AppSettings")} style={styles.icon}><Image accessible={false} resizeMode="contain" source={appImages.settingsIcon} style={styles.settingsIcon} /></Pressable>
    </View>
    {!onBack && <Modal visible={open} transparent animationType="none" onRequestClose={() => setOpen(false)}>
      <View style={styles.overlay}>
        <Pressable accessibilityRole="button" accessibilityLabel="사이드바 닫기" style={StyleSheet.absoluteFill} onPress={() => setOpen(false)} />
        <Animated.View accessibilityViewIsModal style={[styles.drawer, { width: Math.min(width * .78, 360), paddingTop: insets.top, transform: [{ translateX: offset }] }]}>
          <View style={styles.header}><Image accessible accessibilityLabel="Trend Leader 로고" resizeMode="contain" source={appImages.trendLeaderLogo} style={styles.logoImage} /><Pressable accessibilityRole="button" accessibilityLabel="앱 설정"
          accessibilityState={{ disabled: settingsDisabled }} disabled={settingsDisabled}
          onPress={() => requestNavigation("AppSettings")} style={styles.icon}><Image accessible={false} resizeMode="contain" source={appImages.settingsIcon} style={styles.settingsIcon} /></Pressable></View>
          <View style={styles.identity}>
            <ProtectedAvatar url={profile.data?.profile_image_url} size={72} />
            <Text style={styles.nickname}>{profile.data?.nickname ?? (profile.isError ? "프로필 조회 실패" : "불러오는 중…")}</Text>
          </View>
          <Pressable style={styles.row} accessibilityRole="button" onPress={() => requestNavigation("MyInfo")}><Text style={styles.label}>내 정보</Text></Pressable>
          <Pressable style={styles.row} accessibilityRole="button" onPress={confirmLogout}><Text style={styles.label}>로그아웃</Text></Pressable>
        </Animated.View>
      </View>
    </Modal>}
  </>;
}
const useStyles = createThemedStyles((colors) => ({
  header: { minHeight: 56, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 12, borderBottomWidth: 1, borderColor: colors.dividerDefault },
  icon: { minWidth: 48, minHeight: 48, justifyContent: "center", alignItems: "center" },
  blue: { color: colors.textLink, fontSize: 28 },
  disabledIcon: { opacity: 0.4 },
  logoImage: { width: 48, height: 48, tintColor: colors.textBrand },
  settingsIcon: { width: 28, height: 28, tintColor: colors.textLink },
  overlay: { flex: 1, backgroundColor: "#0006" },
  drawer: { height: "100%", backgroundColor: colors.backgroundSurface },
  identity: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, paddingVertical: 40, gap: 18 },
  nickname: { color: colors.textPrimary, fontSize: 18, flexShrink: 1, textDecorationLine: "underline" },
  row: { paddingHorizontal: 28, minHeight: 64, justifyContent: "center", borderTopWidth: 1, borderColor: colors.dividerDefault },
  label: { fontSize: 18, color: colors.textPrimary },
}));
