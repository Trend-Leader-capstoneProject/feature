/** Development-only IGDB review; not a production route or published trend. */

import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { ScreenContainer } from "../../../shared/components";
import { spacing, typography } from "../../../shared/constants";
import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { TrendCard } from "../components/TrendCard";
import {
  fetchIgdbDevPreview,
  type IgdbDevPreviewResult,
} from "../dev/igdbDevPreview";
import { openTrendSourceUrl } from "../utils/openTrendSourceUrl";

type LoadState =
  | { kind: "loading" }
  | { kind: "failed" }
  | IgdbDevPreviewResult;

interface IgdbDevPreviewScreenProps {
  navigation?: { goBack: () => void };
}

export function IgdbDevPreviewScreen({
  navigation,
}: IgdbDevPreviewScreenProps) {
  const { styles } = useStyles();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const requestIdRef = useRef(0);

  const reload = useCallback((): void => {
    if (!__DEV__) {
      return;
    }

    const requestId = ++requestIdRef.current;
    setState({ kind: "loading" });
    void fetchIgdbDevPreview()
      .then((result) => {
        if (requestId === requestIdRef.current) {
          setState(result);
        }
      })
      .catch(() => {
        if (requestId === requestIdRef.current) {
          setState({ kind: "failed" });
        }
      });
  }, []);

  useEffect(() => {
    reload();
    return () => {
      requestIdRef.current += 1;
    };
  }, [reload]);

  if (!__DEV__) {
    return null;
  }

  return (
    <ScreenContainer>
      <View style={styles.container}>
        <Text accessibilityRole="header" style={styles.title}>
          IGDB 내부 검증
        </Text>
        <Text style={styles.notice}>
          개발 전용 · 독립 검증 결과 · 미게시 · DB 저장 없음
        </Text>

        {state.kind === "loading" && (
          <ActivityIndicator accessibilityLabel="IGDB 검증 데이터를 조회하는 중" />
        )}
        {state.kind === "empty" && (
          <Text style={styles.message}>현재 적격 게임 후보가 없습니다.</Text>
        )}
        {state.kind === "failed" && (
          <Text style={styles.message}>
            로컬 IGDB 검증 서버에 연결하지 못했습니다.
          </Text>
        )}
        {state.kind === "ready" && (
          <TrendCard
            onOpenSource={(url) => {
              void openTrendSourceUrl(url);
            }}
            trend={state.trend}
          />
        )}

        <Pressable
          accessibilityLabel="IGDB 다시 조회"
          accessibilityRole="button"
          onPress={reload}
          style={styles.button}
        >
          <Text style={styles.buttonText}>다시 조회</Text>
        </Pressable>
        {navigation && (
          <Pressable
            accessibilityLabel="최신 트렌드로 돌아가기"
            accessibilityRole="button"
            onPress={() => navigation.goBack()}
            style={styles.button}
          >
            <Text style={styles.buttonText}>돌아가기</Text>
          </Pressable>
        )}
      </View>
    </ScreenContainer>
  );
}

const useStyles = createThemedStyles((colors) => ({
  container: {
    gap: spacing.space4,
    paddingTop: spacing.space4,
  },
  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },
  notice: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  message: {
    ...typography.body,
    color: colors.textSecondary,
  },
  button: {
    alignSelf: "flex-start",
    padding: spacing.space3,
    borderRadius: 8,
    backgroundColor: colors.actionSecondary,
  },
  buttonText: {
    ...typography.button,
    color: colors.actionSecondaryText,
  },
}));
