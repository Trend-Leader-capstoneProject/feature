import {
    StyleSheet,
} from "react-native";

import {
    LoadingView,
    ScreenContainer,
} from "../../shared/components";

export function SessionRestoreScreen() {
  return (
    <ScreenContainer
      contentStyle={styles.container}
    >
      <LoadingView
        message="로그인 상태를 확인하고 있습니다."
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
  },
});
