import {
    useState,
} from "react";
import {
    Alert,
    StyleSheet,
} from "react-native";

import {
    ErrorView,
    PrimaryButton,
    ScreenContainer,
} from "../../shared/components";
import {
    spacing,
} from "../../shared/constants";
import {
    useAuth,
} from "../providers/AuthProvider";

export function SessionRestoreErrorScreen() {
  const {
    logout,
    restoreSession,
  } = useAuth();

  const [
    isMovingToLogin,
    setIsMovingToLogin,
  ] = useState(false);

  function handleRetry(): void {
    void restoreSession();
  }

  async function handleMoveToLogin(): Promise<void> {
    if (isMovingToLogin) {
      return;
    }

    setIsMovingToLogin(true);

    try {
      await logout();
    } catch {
      setIsMovingToLogin(false);

      Alert.alert(
        "인증 정보 삭제 실패",
        "저장된 인증 정보를 삭제하지 못했습니다. 다시 시도해 주세요.",
      );
    }
  }

  return (
    <ScreenContainer
      contentStyle={styles.container}
    >
      <ErrorView
        title="로그인 상태를 확인할 수 없습니다."
        message={
          "네트워크 상태 또는 서버 연결을 확인한 뒤 다시 시도해 주세요."
        }
        onRetry={handleRetry}
        retryLabel="다시 시도"
      />

      <PrimaryButton
        label={
          isMovingToLogin
            ? "처리 중..."
            : "로그인 화면으로 이동"
        }
        loading={isMovingToLogin}
        onPress={() => {
          void handleMoveToLogin();
        }}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
    gap: spacing.space4,
  },
});
