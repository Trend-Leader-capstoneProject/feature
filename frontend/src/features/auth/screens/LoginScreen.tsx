import axios from "axios";
import { useRef, useState } from "react";
import {
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { RootStackParamList } from "../../../app/navigation/RootNavigator";
import { appImages } from "../../../assets";
import {
  PrimaryButton,
  ScreenContainer,
} from "../../../shared/components";
import {
  borders,
  colors,
  radius,
  sizes,
  spacing,
  textLineLimits,
  typography,
} from "../../../shared/constants";
import { useLogin } from "../hooks/useLogin";
import type {
  LoginErrorResponse
} from "../types/auth";

type FocusedField =
  | "loginId"
  | "password"
  | null;

type LoginScreenProps = NativeStackScreenProps<
  RootStackParamList,
  "Login"
>;

interface LoginErrorPresentation {
  message: string;
  highlightFields: boolean;
}

function getLoginErrorPresentation(
  error: unknown,
): LoginErrorPresentation {
  if (!axios.isAxiosError<LoginErrorResponse>(error)) {
    return {
      message:
        "로그인 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
      highlightFields: false,
    };
  }

  const errorResponse = error.response?.data;

  if (!errorResponse) {
    return {
      message:
        "서버에 연결할 수 없습니다. 네트워크 상태를 확인해 주세요.",
      highlightFields: false,
    };
  }

  switch (errorResponse.statusCode) {
    case 401:
      return {
        message: errorResponse.message,
        highlightFields: true,
      };

    case 422:
      return {
        message: errorResponse.message,
        highlightFields: true,
      };

    case 500:
      return {
        message: errorResponse.message,
        highlightFields: false,
      };
  }
}



export function LoginScreen({
  navigation,
}: LoginScreenProps) {
  const loginMutation = useLogin();

  const passwordInputRef =
    useRef<TextInput>(null);

  const [loginId, setLoginId] =
    useState("");
  const [password, setPassword] =
    useState("");
  const [focusedField, setFocusedField] =
    useState<FocusedField>(null);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);
  const [
    shouldHighlightFields,
    setShouldHighlightFields,
  ] = useState(false);

  const hasLoginId =
    loginId.trim().length > 0;
  const hasPassword =
    password.length > 0;

  const isSubmitDisabled =
    !hasLoginId ||
    !hasPassword ||
    loginMutation.isPending;

  function clearLoginError(): void {
    if (
      errorMessage === null &&
      !shouldHighlightFields
    ) {
      return;
    }

    setErrorMessage(null);
    setShouldHighlightFields(false);
  }

  function handleLoginIdChange(
    value: string,
  ): void {
    setLoginId(value);
    clearLoginError();
  }

  function handlePasswordChange(
    value: string,
  ): void {
    setPassword(value);
    clearLoginError();
  }

  function handleLogin(): void {
    if (isSubmitDisabled) {
      return;
    }

    setErrorMessage(null);
    setShouldHighlightFields(false);

    loginMutation.mutate(
      {
        login_id: loginId,
        password,
      },
      {
        onSuccess: (result) => {
          setPassword("");

          if (
            result.next_step ===
            "INTEREST_SELECTION"
          ) {
            navigation.replace(
              "InterestSelect",
            );
            return;
          }

          Alert.alert(
            "로그인 완료",
            `${result.user.name}님, 로그인되었습니다.\n메인 화면은 구현 후 연결할 예정입니다.`,
          );
        },
        onError: (error) => {
          const presentation =
            getLoginErrorPresentation(error);

          setErrorMessage(
            presentation.message,
          );
          setShouldHighlightFields(
            presentation.highlightFields,
          );
        },
      },
    );
  }

  return (
    <ScreenContainer>
      <KeyboardAvoidingView
        behavior={
          Platform.OS === "ios"
            ? "padding"
            : undefined
        }
        style={styles.keyboardAvoidingView}
      >
        <ScrollView
          contentContainerStyle={
            styles.scrollContent
          }
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.logoRegion}>
            <Image
              accessible={false}
              resizeMode="contain"
              source={
                appImages.trendLeaderLogo
              }
              style={styles.logo}
            />
          </View>

          <View style={styles.header}>
            <Text
              accessibilityRole="header"
              numberOfLines={
                textLineLimits.screenTitle
              }
              style={styles.title}
            >
              로그인
            </Text>

            <Text style={styles.description}>
              관심 분야의 최신 트렌드를
              빠르게 확인해 보세요.
            </Text>
          </View>

          <View style={styles.form}>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                아이디
              </Text>

              <TextInput
                accessibilityLabel="아이디"
                autoCapitalize="none"
                autoComplete="username"
                autoCorrect={false}
                editable={
                  !loginMutation.isPending
                }
                maxLength={50}
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={
                  handleLoginIdChange
                }
                onFocus={() =>
                  setFocusedField(
                    "loginId",
                  )
                }
                onSubmitEditing={() =>
                  passwordInputRef.current?.focus()
                }
                placeholder="아이디를 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="next"
                style={[
                  styles.input,
                  focusedField ===
                    "loginId" &&
                    styles.inputFocused,
                  shouldHighlightFields &&
                    styles.inputError,
                ]}
                textContentType="username"
                value={loginId}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                비밀번호
              </Text>

              <TextInput
                ref={passwordInputRef}
                accessibilityLabel="비밀번호"
                autoCapitalize="none"
                autoComplete="current-password"
                autoCorrect={false}
                editable={
                  !loginMutation.isPending
                }
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={
                  handlePasswordChange
                }
                onFocus={() =>
                  setFocusedField(
                    "password",
                  )
                }
                onSubmitEditing={
                  handleLogin
                }
                placeholder="비밀번호를 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="done"
                secureTextEntry
                style={[
                  styles.input,
                  focusedField ===
                    "password" &&
                    styles.inputFocused,
                  shouldHighlightFields &&
                    styles.inputError,
                ]}
                textContentType="password"
                value={password}
              />
            </View>

            {errorMessage !== null && (
              <Text
                accessibilityLiveRegion="polite"
                accessibilityRole="alert"
                style={styles.errorMessage}
              >
                {errorMessage}
              </Text>
            )}

            <PrimaryButton
              disabled={isSubmitDisabled}
              label={
                loginMutation.isPending
                  ? "로그인 중..."
                  : "로그인"
              }
              loading={
                loginMutation.isPending
              }
              onPress={handleLogin}
              style={styles.loginButton}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  keyboardAvoidingView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: spacing.space4,
  },
  logoRegion: {
    alignItems: "center",
    marginTop: spacing.space4,
    marginBottom: spacing.space10,
  },
  logo: {
    width: 112,
    height: 112,
  },
  header: {
    gap: spacing.contentGap,
    marginBottom: spacing.sectionGap,
  },
  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },
  description: {
    ...typography.body,
    color: colors.textSecondary,
  },
  form: {
    gap: spacing.space5,
  },
  fieldGroup: {
    gap: spacing.space2,
  },
  label: {
    ...typography.label,
    color: colors.textStrongSecondary,
  },
  input: {
    minHeight: sizes.inputHeight,
    paddingHorizontal: spacing.space4,
    borderWidth: borders.borderWidthDefault,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.backgroundSurface,
    ...typography.input,
    color: colors.textPrimary,
  },
  inputFocused: {
    borderWidth: borders.borderWidthStrong,
    borderColor: colors.focusRing,
  },
  inputError: {
    borderWidth: borders.borderWidthStrong,
    borderColor: colors.borderError,
  },
  errorMessage: {
    ...typography.caption,
    color: colors.statusNegative,
  },
  loginButton: {
    marginTop: spacing.space2,
  },
});