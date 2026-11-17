import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { useCallback, useState } from "react";
import { Alert, BackHandler, Pressable, ScrollView, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { useAuth } from "../../../app/providers/AuthProvider";
import { ScreenContainer, LoadingView, ErrorView } from "../../../shared/components";
import { AccountHeader } from "../components/AccountHeader";
import { ProtectedAvatar } from "../components/ProtectedAvatar";
import { ProfileEditorModal } from "../components/ProfileEditorModal";
import { WithdrawalModal } from "../components/WithdrawalModal";
import { useMyProfile } from "../hooks/useMyProfile";
import { useNavigationTransitionGuard } from "../hooks/useNavigationTransitionGuard";

export function MyInfoScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "MyInfo">) {
  const { styles } = useStyles();
  const profile = useMyProfile();
  const transition = useNavigationTransitionGuard(navigation);
  const { logout } = useAuth();
  const [editor, setEditor] = useState<"PHOTO" | "NICKNAME" | null>(null);
  const [withdrawal, setWithdrawal] = useState(false);
  const goToMain = useCallback(() => {
    transition.run(() => navigation.popTo("Main"));
  }, [navigation, transition.run]);
  useFocusEffect(useCallback(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      // Native Modal이 열려 있으면 해당 onRequestClose가 먼저 처리한다.
      goToMain();
      return true;
    });
    return () => subscription.remove();
  }, [goToMain]));
  function confirmLogout() {
    Alert.alert("로그아웃할까요?", undefined, [
      { text: "취소", style: "cancel" },
      { text: "로그아웃", onPress: () => void logout().catch(() => undefined) },
    ]);
  }
  const rows = [
    { title: "비밀번호 변경", navigates: true, action: () => navigation.navigate("PasswordChange") },
    { title: "관심사 재설정", navigates: true, action: () => navigation.navigate("InterestEdit") },
    { title: "로그아웃", action: confirmLogout },
    { title: "회원 탈퇴", action: () => setWithdrawal(true) },
  ];
  return <ScreenContainer contentStyle={styles.container}>
    <AccountHeader onBack={goToMain} backDisabled={transition.disabled} />
    <ScrollView contentContainerStyle={styles.scroll}>
      {profile.isPending ? <LoadingView message="내 정보를 불러오고 있습니다." /> :
        profile.isError ? <ErrorView title="내 정보를 불러오지 못했습니다." message="연결 상태를 확인하고 다시 시도해 주세요." onRetry={() => void profile.refetch()} /> :
        profile.data && <>
          <View style={styles.identity}>
            <View>
              <ProtectedAvatar url={profile.data.profile_image_url} size={88} />
              <Pressable accessibilityRole="button" accessibilityLabel="프로필 사진 변경" disabled={transition.disabled} onPress={() => setEditor("PHOTO")} style={styles.plus}><Text style={styles.plusText}>＋</Text></Pressable>
            </View>
            <View style={styles.nicknameRow}>
              <Text style={styles.nickname}>{profile.data.nickname}</Text>
              <Pressable accessibilityRole="button" accessibilityLabel="닉네임 변경" disabled={transition.disabled} onPress={() => setEditor("NICKNAME")} style={styles.change}><Text style={styles.blue}>변경</Text></Pressable>
            </View>
          </View>
          {rows.map(row => <Pressable key={row.title} accessibilityRole="button" style={styles.row} disabled={transition.disabled} onPress={() => row.navigates ? transition.run(row.action) : row.action()}><Text style={styles.label}>{row.title}</Text></Pressable>)}
        </>}
    </ScrollView>
    {editor && profile.data && <ProfileEditorModal type={editor} profile={profile.data} onClose={() => setEditor(null)} />}
    {withdrawal && <WithdrawalModal onClose={() => setWithdrawal(false)} />}
  </ScreenContainer>;
}
const useStyles = createThemedStyles((colors) => ({
  container: { paddingHorizontal: 0, paddingTop: 0, paddingBottom: 0, backgroundColor: colors.backgroundSurface },
  scroll: { paddingBottom: 28 }, identity: { alignItems: "center", paddingTop: 32, paddingBottom: 34, gap: 24 },
  plus: { position: "absolute", bottom: -8, right: -12, backgroundColor: colors.backgroundBrandMuted, borderRadius: 24, width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  plusText: { color: colors.textLink, fontSize: 28 }, nicknameRow: { flexDirection: "row", alignItems: "center", gap: 22 },
  nickname: { color: colors.textPrimary, fontSize: 21, textDecorationLine: "underline", flexShrink: 1 }, change: { padding: 12, backgroundColor: colors.backgroundBrandMuted, borderRadius: 8, minHeight: 48 },
  blue: { color: colors.textLink, fontSize: 18 }, row: { borderTopWidth: 1, borderColor: colors.dividerDefault, minHeight: 58, justifyContent: "center", paddingHorizontal: 24 },
  label: { fontSize: 18, color: colors.textPrimary },
}));
