import { useState } from "react";
import { Image, Linking, Pressable, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { PrimaryButton } from "../../../shared/components";
import { typography } from "../../../shared/constants";
import { useAppTheme, type ThemePreference } from "../../../shared/theme/ThemeProvider";
import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { useScreenReturn } from "../../account/hooks/useScreenReturn";
import { SettingsLayout } from "../components/SettingsLayout";
import { APP_NAME, APP_VERSION, CONTACT_URL, FAQ, OPEN_SOURCE, PROJECT_URL } from "../appDetails";

import { appImages } from "../../../assets";

const THEME_OPTIONS: { value: ThemePreference; label: string; detail: string }[] = [
  { value: "SYSTEM", label: "기기 설정 따르기", detail: "휴대폰의 라이트·다크 설정을 사용합니다." },
  { value: "LIGHT", label: "라이트 모드", detail: "밝은 화면으로 표시합니다." },
  { value: "DARK", label: "다크 모드", detail: "어두운 화면으로 표시합니다." },
];
export function AppSettingsScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "AppSettings">) {
  const back = useScreenReturn(navigation);
  const theme = useAppTheme();
  const { styles } = useStyles();
  return <SettingsLayout title="앱 설정" onBack={back.goBack} disabled={back.disabled}>
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>화면 테마</Text>
      <Text style={styles.description}>선택한 테마는 이 기기에 저장됩니다.</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel="화면 테마" style={styles.card}>
        {THEME_OPTIONS.map(option => {
          const selected = theme.preference === option.value;
          return <Pressable key={option.value} accessibilityRole="radio" accessibilityLabel={option.label}
            accessibilityState={{ checked: selected, disabled: !theme.ready || theme.saving }}
            disabled={!theme.ready || theme.saving} onPress={() => void theme.setPreference(option.value)}
            style={({ pressed }) => [styles.option, selected && styles.selected, pressed && styles.pressed]}>
            <View style={styles.flex}>
              <Text style={styles.label}>{option.label}</Text>
              <Text style={styles.description}>{option.detail}</Text>
            </View>
            <Text accessible={false} style={styles.check}>{selected ? "●" : "○"}</Text>
          </Pressable>;
        })}
      </View>
      {!theme.ready && <Text style={styles.description}>설정을 불러오는 중…</Text>}
      {theme.saving && <Text accessibilityLiveRegion="polite" style={styles.description}>저장 중…</Text>}
      {!!theme.error && <View style={styles.section}>
        <Text accessibilityRole="alert" style={styles.error}>{theme.error}</Text>
        <PrimaryButton label="설정 다시 불러오기" disabled={theme.saving || !theme.ready}
          onPress={theme.retryRestore} style={styles.compact} />
      </View>}
    </View>
    <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel="앱 정보" disabled={back.disabled}
        style={styles.linkRow} onPress={() => back.run(() => navigation.navigate("AppInfo"))}>
        <Text style={styles.label}>앱 정보</Text><Text style={styles.chevron}>›</Text>
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="도움말 / 문의" disabled={back.disabled}
        style={styles.linkRow} onPress={() => back.run(() => navigation.navigate("HelpSupport"))}>
        <Text style={styles.label}>도움말 / 문의</Text><Text style={styles.chevron}>›</Text>
      </Pressable>
    </View>
  </SettingsLayout>;
}

function useExternalLink() {
  const [error, setError] = useState("");
  const [opening, setOpening] = useState(false);
  async function open(url: string) {
    if (opening) return;
    setError(""); setOpening(true);
    try { await Linking.openURL(url); }
    catch { setError("링크를 열지 못했습니다. 인터넷 연결과 브라우저를 확인한 뒤 다시 눌러 주세요."); }
    finally { setOpening(false); }
  }
  return { error, opening, open };
}
export function AppInfoScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "AppInfo">) {
  const back = useScreenReturn(navigation);
  const { styles } = useStyles();
  const link = useExternalLink();
  return <SettingsLayout title="앱 정보" onBack={back.goBack} disabled={back.disabled}>
    <View style={styles.identity}>
      <Image accessible accessibilityLabel="Trend Leader 로고" source={appImages.trendLeaderLogo} resizeMode="contain" style={styles.brand} />
      <Text accessibilityRole="header" style={styles.appName}>{APP_NAME}</Text>
      <Text style={styles.description}>버전 {APP_VERSION}</Text>
    </View>
    <Text style={styles.body}>관심사에 맞는 트렌드와 최신 이슈를 한곳에서 살펴보는 개인화 트렌드 큐레이션 앱입니다.</Text>
    <PrimaryButton label="프로젝트 페이지 열기" onPress={() => void link.open(PROJECT_URL)} disabled={link.opening} style={styles.compact} />
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>주요 오픈소스</Text>
      <Text style={styles.description}>항목을 누르면 외부 브라우저에서 라이선스를 확인할 수 있습니다.</Text>
      <View style={styles.card}>
        {OPEN_SOURCE.map(item => <Pressable key={item.name} accessibilityRole="link"
          accessibilityLabel={item.name + " 라이선스 열기"} disabled={link.opening}
          onPress={() => void link.open(item.url)} style={styles.linkRow}>
          <Text style={[styles.body, styles.flex]}>{item.name}</Text><Text style={styles.license}>{item.license} ↗</Text>
        </Pressable>)}
      </View>
    </View>
    {!!link.error && <Text accessibilityRole="alert" style={styles.error}>{link.error}</Text>}
  </SettingsLayout>;
}
export function HelpSupportScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "HelpSupport">) {
  const back = useScreenReturn(navigation);
  const { styles } = useStyles();
  const link = useExternalLink();
  const [expanded, setExpanded] = useState<number | null>(null);
  return <SettingsLayout title="도움말 / 문의" onBack={back.goBack} disabled={back.disabled}>
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>자주 묻는 질문</Text>
      <View style={styles.card}>
        {FAQ.map((item, index) => <View key={item.question}>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: expanded === index }}
            accessibilityLabel={item.question} onPress={() => setExpanded(expanded === index ? null : index)} style={styles.linkRow}>
            <Text style={[styles.body, styles.flex]}>{item.question}</Text><Text style={styles.chevron}>{expanded === index ? "−" : "+"}</Text>
          </Pressable>
          {expanded === index && <Text style={styles.answer}>{item.answer}</Text>}
        </View>)}
      </View>
    </View>
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>문의하기</Text>
      <Text style={styles.body}>GitHub 공개 문의 게시판으로 이동합니다. 작성하려면 GitHub 로그인이 필요합니다.</Text>
      <Text style={styles.description}>문의 내용은 누구나 볼 수 있습니다. 비밀번호·로그인 토큰·연락처 등 개인정보를 적지 마세요.</Text>
      <PrimaryButton label="GitHub에서 문의 작성" disabled={link.opening} onPress={() => void link.open(CONTACT_URL)} style={styles.compact} />
    </View>
    {!!link.error && <Text accessibilityRole="alert" style={styles.error}>{link.error}</Text>}
  </SettingsLayout>;
}
const useStyles = createThemedStyles(colors => ({
  section: { gap: 12 },
  sectionTitle: { ...typography.sectionTitle, color: colors.textPrimary },
  description: { ...typography.caption, color: colors.textSecondary },
  body: { ...typography.body, color: colors.textPrimary },
  label: { ...typography.bodyStrong, color: colors.textPrimary },
  card: { borderWidth: 1, borderColor: colors.borderDefault, borderRadius: 14, overflow: "hidden", backgroundColor: colors.backgroundSurface },
  option: { flexDirection: "row", alignItems: "center", padding: 16, gap: 12, minHeight: 76 },
  selected: { backgroundColor: colors.backgroundSelected },
  pressed: { opacity: .75 },
  check: { fontSize: 23, color: colors.textBrand },
  flex: { flex: 1, gap: 4 },
  linkRow: { minHeight: 58, padding: 16, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, borderBottomWidth: 1, borderColor: colors.dividerDefault },
  chevron: { color: colors.textSecondary, fontSize: 24 },
  error: { ...typography.body, color: colors.statusNegative },
  compact: { alignSelf: "center", minHeight: 44, paddingHorizontal: 18 },
  identity: { alignItems: "center", gap: 8, paddingVertical: 12 },
  brand: { width: 80, height: 80, tintColor: colors.textBrand },
  appName: { ...typography.screenTitle, color: colors.textPrimary },
  license: { ...typography.caption, color: colors.textLink },
  answer: { ...typography.body, color: colors.textStrongSecondary, padding: 16, paddingTop: 8, backgroundColor: colors.backgroundSubtle },
}));
