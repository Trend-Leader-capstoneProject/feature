import type {
    NativeStackScreenProps,
} from "@react-navigation/native-stack";
import {
    useRef,
    useState,
} from "react";
import {
    KeyboardAvoidingView,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    TextInput,
    View,
} from "react-native";

import type {
    AuthStackParamList,
} from "../../../app/navigation/AuthNavigator";
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
    typography,
} from "../../../shared/constants";
import {
    useCheckLoginId,
} from "../hooks/useCheckLoginId";

type SignupScreenProps =
  NativeStackScreenProps<
    AuthStackParamList,
    "Signup"
  >;

type SignupField =
  | "loginId"
  | "password"
  | "passwordConfirm"
  | "name"
  | "email";

type SignupFieldErrors =
  Partial<Record<SignupField, string>>;

type LoginIdCheckFeedback =
  | {
      loginId: string;
      status: "AVAILABLE";
    }
  | {
      loginId: string;
      status: "DUPLICATED";
    }
  | {
      loginId: string;
      status: "ERROR";
      message: string;
    }
  | null;

const LOGIN_ID_PATTERN =
  /^[a-z][a-z0-9_]*$/;

const EMAIL_PATTERN =
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getLoginIdValidationError(
  loginId: string,
): string | null {
  if (loginId.length < 4) {
    return "아이디는 4자 이상이어야 합니다.";
  }

  if (loginId.length > 50) {
    return "아이디는 50자 이하여야 합니다.";
  }

  if (!LOGIN_ID_PATTERN.test(loginId)) {
    return (
      "아이디는 영문 소문자로 시작하고, " +
      "영문 소문자·숫자·밑줄(_)만 사용할 수 있습니다."
    );
  }

  return null;
}

function validateSignupForm({
  loginId,
  password,
  passwordConfirm,
  name,
  email,
}: {
  loginId: string;
  password: string;
  passwordConfirm: string;
  name: string;
  email: string;
}): SignupFieldErrors {
  const errors: SignupFieldErrors = {};

  const loginIdError =
    getLoginIdValidationError(loginId);

  if (loginIdError !== null) {
    errors.loginId = loginIdError;
  }

  if (password.length < 15) {
    errors.password =
      "비밀번호는 15자 이상이어야 합니다.";
  } else if (password.length > 128) {
    errors.password =
      "비밀번호는 128자 이하여야 합니다.";
  }

  if (passwordConfirm !== password) {
    errors.passwordConfirm =
      "비밀번호 확인이 일치하지 않습니다.";
  }

  const normalizedName = name.trim();

  if (normalizedName.length === 0) {
    errors.name =
      "이름을 입력해 주세요.";
  } else if (normalizedName.length > 50) {
    errors.name =
      "이름은 50자 이하여야 합니다.";
  }

  const normalizedEmail = email.trim();

  if (normalizedEmail.length > 0) {
    if (normalizedEmail.length > 255) {
      errors.email =
        "이메일은 255자 이하여야 합니다.";
    } else if (
      !EMAIL_PATTERN.test(normalizedEmail)
    ) {
      errors.email =
        "올바른 이메일 형식을 입력해 주세요.";
    }
  }

  return errors;
}

export function SignupScreen({
  navigation,
}: SignupScreenProps) {
  const checkLoginIdMutation =
    useCheckLoginId();

  const passwordInputRef =
    useRef<TextInput>(null);
  const passwordConfirmInputRef =
    useRef<TextInput>(null);
  const nameInputRef =
    useRef<TextInput>(null);
  const emailInputRef =
    useRef<TextInput>(null);

  const loginIdValueRef =
    useRef("");

  const [loginId, setLoginId] =
    useState("");
  const [password, setPassword] =
    useState("");
  const [
    passwordConfirm,
    setPasswordConfirm,
  ] = useState("");
  const [name, setName] =
    useState("");
  const [email, setEmail] =
    useState("");

  const [
    focusedField,
    setFocusedField,
  ] = useState<SignupField | null>(null);

  const [
    fieldErrors,
    setFieldErrors,
  ] = useState<SignupFieldErrors>({});

  const [
    loginIdCheckFeedback,
    setLoginIdCheckFeedback,
  ] = useState<LoginIdCheckFeedback>(null);

  const currentLoginIdCheckFeedback =
    loginIdCheckFeedback?.loginId === loginId
      ? loginIdCheckFeedback
      : null;

  const isCurrentLoginIdAvailable =
    currentLoginIdCheckFeedback?.status ===
    "AVAILABLE";

  const loginIdValidationError =
    getLoginIdValidationError(loginId);

  const canCheckLoginId =
    loginId.length > 0 &&
    loginIdValidationError === null &&
    !checkLoginIdMutation.isPending;

  function clearFieldError(
    field: SignupField,
  ): void {
    if (!fieldErrors[field]) {
      return;
    }

    setFieldErrors((current) => {
      const next = {
        ...current,
      };

      delete next[field];

      return next;
    });
  }

  function handleLoginIdChange(
    value: string,
  ): void {
    loginIdValueRef.current = value;

    setLoginId(value);
    clearFieldError("loginId");

    setLoginIdCheckFeedback(null);
  }

  function handleCheckLoginId(): void {
    const validationError =
      getLoginIdValidationError(loginId);

    if (validationError !== null) {
      setFieldErrors((current) => ({
        ...current,
        loginId: validationError,
      }));

      setLoginIdCheckFeedback(null);
      return;
    }

    clearFieldError("loginId");

    const requestedLoginId = loginId;

    setLoginIdCheckFeedback(null);

    checkLoginIdMutation.mutate(
      {
        login_id: requestedLoginId,
      },
      {
        onSuccess: (result) => {
          if (
            loginIdValueRef.current !==
            requestedLoginId
          ) {
            return;
          }

          setLoginIdCheckFeedback({
            loginId: requestedLoginId,
            status: result.is_available
              ? "AVAILABLE"
              : "DUPLICATED",
          });
        },
        onError: (error) => {
          if (
            loginIdValueRef.current !==
            requestedLoginId
          ) {
            return;
          }

          let message =
            "아이디 중복 확인 중 문제가 발생했습니다.";

          if (!error.response) {
            message =
              "서버에 연결할 수 없습니다. 네트워크 상태를 확인해 주세요.";
          } else if (
            error.response.status === 422
          ) {
            message =
              "아이디 형식을 확인해 주세요.";
          } else if (
            error.response.status >= 500
          ) {
            message =
              "서버 오류로 아이디를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.";
          }

          setLoginIdCheckFeedback({
            loginId: requestedLoginId,
            status: "ERROR",
            message,
          });
        },
      },
    );
  }

  function handleSignup(): void {
    const errors = validateSignupForm({
      loginId,
      password,
      passwordConfirm,
      name,
      email,
    });

    if (
      !errors.loginId &&
      !isCurrentLoginIdAvailable
    ) {
      errors.loginId =
        currentLoginIdCheckFeedback
          ?.status === "DUPLICATED"
          ? "이미 사용 중인 아이디입니다."
          : "아이디 중복 확인을 완료해 주세요.";
    }

    setFieldErrors(errors);

    if (
      Object.keys(errors).length > 0
    ) {
      return;
    }

    // Phase 3-5c에서 실제 Signup Mutation 연결
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
          <View style={styles.header}>
            <Text
              accessibilityRole="header"
              style={styles.title}
            >
              회원가입
            </Text>

            <Text style={styles.description}>
              Trend Leader 계정을 만들어
              관심 분야의 트렌드를 확인해 보세요.
            </Text>
          </View>

          <View style={styles.form}>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                아이디
              </Text>

              <View
                style={styles.loginIdInputRow}
              >
                <TextInput
                  accessibilityLabel="아이디"
                  autoCapitalize="none"
                  autoComplete="username-new"
                  autoCorrect={false}
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
                    styles.loginIdInput,
                    focusedField ===
                      "loginId" &&
                      styles.inputFocused,
                    (
                      fieldErrors.loginId ||
                      currentLoginIdCheckFeedback
                        ?.status ===
                        "DUPLICATED"
                    ) &&
                      styles.inputError,
                  ]}
                  textContentType="username"
                  value={loginId}
                />

                <PrimaryButton
                  disabled={
                    !canCheckLoginId
                  }
                  label="중복 확인"
                  loading={
                    checkLoginIdMutation
                      .isPending
                  }
                  onPress={
                    handleCheckLoginId
                  }
                  style={
                    styles.checkLoginIdButton
                  }
                  textStyle={
                    styles.checkLoginIdButtonText
                  }
                />
              </View>

              {fieldErrors.loginId ? (
                <Text
                  accessibilityLiveRegion="polite"
                  style={styles.errorText}
                >
                  {fieldErrors.loginId}
                </Text>
              ) : currentLoginIdCheckFeedback
                  ?.status ===
                "AVAILABLE" ? (
                <Text
                  accessibilityLiveRegion="polite"
                  style={styles.availableText}
                >
                  사용 가능한 아이디입니다.
                </Text>
              ) : currentLoginIdCheckFeedback
                  ?.status ===
                "DUPLICATED" ? (
                <Text
                  accessibilityLiveRegion="polite"
                  style={styles.errorText}
                >
                  이미 사용 중인 아이디입니다.
                </Text>
              ) : currentLoginIdCheckFeedback
                  ?.status === "ERROR" ? (
                <Text
                  accessibilityLiveRegion="polite"
                  style={styles.errorText}
                >
                  {
                    currentLoginIdCheckFeedback.message
                  }
                </Text>
              ) : (
                <Text style={styles.helperText}>
                  영문 소문자로 시작하는
                  4~50자의 영문 소문자·숫자·밑줄(_)을
                  사용할 수 있습니다.
                </Text>
              )}
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                비밀번호
              </Text>

              <TextInput
                ref={passwordInputRef}
                accessibilityLabel="비밀번호"
                autoCapitalize="none"
                autoComplete="new-password"
                autoCorrect={false}
                maxLength={128}
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={(value) => {
                  setPassword(value);
                  clearFieldError(
                    "password",
                  );

                  if (
                    fieldErrors.passwordConfirm
                  ) {
                    clearFieldError(
                      "passwordConfirm",
                    );
                  }
                }}
                onFocus={() =>
                  setFocusedField(
                    "password",
                  )
                }
                onSubmitEditing={() =>
                  passwordConfirmInputRef
                    .current?.focus()
                }
                placeholder="비밀번호를 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="next"
                secureTextEntry
                style={[
                  styles.input,
                  focusedField ===
                    "password" &&
                    styles.inputFocused,
                  fieldErrors.password &&
                    styles.inputError,
                ]}
                textContentType="newPassword"
                value={password}
              />

              <Text style={styles.helperText}>
                15자 이상 128자 이하로 입력해 주세요.
              </Text>

              {fieldErrors.password && (
                <Text style={styles.errorText}>
                  {fieldErrors.password}
                </Text>
              )}
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                비밀번호 확인
              </Text>

              <TextInput
                ref={
                  passwordConfirmInputRef
                }
                accessibilityLabel="비밀번호 확인"
                autoCapitalize="none"
                autoComplete="new-password"
                autoCorrect={false}
                maxLength={128}
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={(value) => {
                  setPasswordConfirm(value);
                  clearFieldError(
                    "passwordConfirm",
                  );
                }}
                onFocus={() =>
                  setFocusedField(
                    "passwordConfirm",
                  )
                }
                onSubmitEditing={() =>
                  nameInputRef.current?.focus()
                }
                placeholder="비밀번호를 다시 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="next"
                secureTextEntry
                style={[
                  styles.input,
                  focusedField ===
                    "passwordConfirm" &&
                    styles.inputFocused,
                  fieldErrors.passwordConfirm &&
                    styles.inputError,
                ]}
                textContentType="newPassword"
                value={passwordConfirm}
              />

              {fieldErrors.passwordConfirm && (
                <Text style={styles.errorText}>
                  {
                    fieldErrors.passwordConfirm
                  }
                </Text>
              )}
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                이름
              </Text>

              <TextInput
                ref={nameInputRef}
                accessibilityLabel="이름"
                autoCorrect={false}
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={(value) => {
                  setName(value);
                  clearFieldError("name");
                }}
                onFocus={() =>
                  setFocusedField("name")
                }
                onSubmitEditing={() =>
                  emailInputRef.current?.focus()
                }
                placeholder="이름을 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="next"
                style={[
                  styles.input,
                  focusedField === "name" &&
                    styles.inputFocused,
                  fieldErrors.name &&
                    styles.inputError,
                ]}
                value={name}
              />

              {fieldErrors.name && (
                <Text style={styles.errorText}>
                  {fieldErrors.name}
                </Text>
              )}
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>
                이메일
                <Text
                  style={styles.optionalText}
                >
                  {"  "}(선택)
                </Text>
              </Text>

              <TextInput
                ref={emailInputRef}
                accessibilityLabel="이메일"
                autoCapitalize="none"
                autoComplete="email"
                autoCorrect={false}
                keyboardType="email-address"
                onBlur={() =>
                  setFocusedField(null)
                }
                onChangeText={(value) => {
                  setEmail(value);
                  clearFieldError("email");
                }}
                onFocus={() =>
                  setFocusedField("email")
                }
                onSubmitEditing={
                  handleSignup
                }
                placeholder="이메일을 입력하세요"
                placeholderTextColor={
                  colors.textDisabled
                }
                returnKeyType="done"
                style={[
                  styles.input,
                  focusedField === "email" &&
                    styles.inputFocused,
                  fieldErrors.email &&
                    styles.inputError,
                ]}
                textContentType="emailAddress"
                value={email}
              />

              {fieldErrors.email && (
                <Text style={styles.errorText}>
                  {fieldErrors.email}
                </Text>
              )}
            </View>

            <PrimaryButton
              label="회원가입"
              onPress={handleSignup}
              style={styles.signupButton}
            />

            <View style={styles.loginPrompt}>
              <Text
                style={styles.loginPromptText}
              >
                이미 계정이 있으신가요?
              </Text>

              <Pressable
                accessibilityRole="button"
                hitSlop={8}
                onPress={() =>
                  navigation.goBack()
                }
              >
                <Text style={styles.loginLink}>
                  로그인
                </Text>
              </Pressable>
            </View>
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
    paddingVertical: spacing.space6,
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
  optionalText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  loginIdInputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.space2,
  },
  input: {
    minHeight: sizes.inputHeight,
    paddingHorizontal: spacing.space4,
    borderWidth:
      borders.borderWidthDefault,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor:
      colors.backgroundSurface,
    ...typography.input,
    color: colors.textPrimary,
  },
  loginIdInput: {
    flex: 1,
  },
  inputFocused: {
    borderWidth:
      borders.borderWidthStrong,
    borderColor: colors.focusRing,
  },
  inputError: {
    borderWidth:
      borders.borderWidthStrong,
    borderColor: colors.borderError,
  },
  helperText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  availableText: {
    ...typography.caption,
    color: colors.statusPositive,
  },
  errorText: {
    ...typography.caption,
    color: colors.statusNegative,
  },
  checkLoginIdButton: {
    minWidth: 112,
    paddingHorizontal: spacing.space3,
  },
  checkLoginIdButtonText: {
    ...typography.label,
  },
  signupButton: {
    marginTop: spacing.space2,
  },
  loginPrompt: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.space2,
  },
  loginPromptText: {
    ...typography.body,
    color: colors.textSecondary,
  },
  loginLink: {
    ...typography.bodyStrong,
    color: colors.textLink,
  },
});
