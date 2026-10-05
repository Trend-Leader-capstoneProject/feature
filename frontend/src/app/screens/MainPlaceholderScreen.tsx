import {
  useState,
} from "react";
import {
  Alert,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { NativeStackScreenProps } from "@react-navigation/native-stack";
import {
  PrimaryButton,
  ScreenContainer,
} from "../../shared/components";
import {
  colors,
  spacing,
  typography,
} from "../../shared/constants";
import { AppStackParamList } from "../navigation/AppNavigator";
import {
  useAuth,
} from "../providers/AuthProvider";

type MainPlaceholderScreenProps =
  NativeStackScreenProps<
    AppStackParamList,
   "Main"
  >;

export function MainPlaceholderScreen({
  navigation,
}: MainPlaceholderScreenProps) {
  const {
    authState,
    logout,
  } = useAuth();

  const [
    isLoggingOut,
    setIsLoggingOut,
  ] = useState(false);

  async function handleLogout(): Promise<void> {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      setIsLoggingOut(false);

      Alert.alert(
        "로그아웃 실패",
        "저장된 인증 정보를 삭제하지 못했습니다. 다시 시도해 주세요.",
      );
    }
  }

  const userName =
    authState.status === "AUTHENTICATED"
      ? authState.session.user.name
      : null;

  return (
    <ScreenContainer
      contentStyle={styles.container}
    >
      <View style={styles.content}>
        <Text
          accessibilityRole="header"
          style={styles.title}
        >
          Trend Leader
        </Text>

        <Text style={styles.description}>
          {userName
            ? `${userName}님, 로그인되어 있습니다.`
            : "로그인 세션이 정상적으로 복원되었습니다."}
          {"\n"}
          최신 트렌드 목록을 확인해 보세요.
        </Text>

        <PrimaryButton
          label="로그아웃"
          loading={isLoggingOut}
          onPress={() => {
            void handleLogout();
          }}
        />

        <PrimaryButton
          label="최신 트렌드 보기"
          onPress={() =>
            navigation.navigate(
              "LatestTrend",
            )
          }
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
  },
  content: {
    gap: spacing.contentGap,
  },
  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },
  description: {
    ...typography.body,
    color: colors.textSecondary,
  },
});
