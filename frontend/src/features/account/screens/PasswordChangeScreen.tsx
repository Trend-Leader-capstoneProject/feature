import axios from "axios";
import { useRef, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, TextInput } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { PrimaryButton, ScreenContainer } from "../../../shared/components";
import { getErrorReason } from "../../../shared/api/authenticatedApiClient";
import { getAuthEpoch } from "../../../shared/handler/authRequestGate";
import { useAccountActions } from "../hooks/useAccountActions";

export function PasswordChangeScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "PasswordChange">) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const busy = useRef(false);
  const { password } = useAccountActions();
  async function save() {
    if (busy.current) return;
    if (next.length < 8 || next.length > 128) { setMessage("새 비밀번호는 8~128자여야 합니다."); return; }
    if (next !== confirm) { setMessage("새 비밀번호 확인이 일치하지 않습니다."); return; }
    if (current === next) { setMessage("기존 비밀번호와 다른 값을 입력해 주세요."); return; }
    busy.current = true; setMessage("");
    const epoch = getAuthEpoch();
    try {
      await password.mutateAsync({ current, next, confirm });
      if (epoch !== getAuthEpoch()) return;
      setCurrent(""); setNext(""); setConfirm("");
      Alert.alert("비밀번호 변경 완료", "다른 기기에서는 다시 로그인해야 합니다.", [
        { text: "확인", onPress: () => navigation.goBack() },
      ]);
    } catch (error) {
      if (epoch !== getAuthEpoch()) return;
      const reason = getErrorReason(error);
      setMessage(reason === "CURRENT_PASSWORD_MISMATCH" ? "현재 비밀번호가 올바르지 않습니다." :
        reason === "PASSWORD_UNCHANGED" ? "기존 비밀번호와 다른 값을 입력해 주세요." :
        axios.isAxiosError(error) && error.response && error.response.status < 500 ? "입력값을 확인해 주세요." :
        "변경 결과를 확인하지 못했습니다. 자동으로 다시 요청하지 않습니다. 비밀번호와 로그인 상태를 확인한 뒤 다시 시도해 주세요.");
    } finally { busy.current = false; }
  }
  return <ScreenContainer><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
    <Text accessibilityRole="header" style={styles.title}>비밀번호 변경</Text>
    {[
      { label: "현재 비밀번호", value: current, update: setCurrent },
      { label: "새 비밀번호", value: next, update: setNext },
      { label: "새 비밀번호 확인", value: confirm, update: setConfirm },
    ].map(field => <TextInput key={field.label} accessibilityLabel={field.label} placeholder={field.label} value={field.value} onChangeText={field.update} secureTextEntry autoCapitalize="none" autoCorrect={false} editable={!password.isPending} style={styles.input} />)}
    {!!message && <Text accessibilityLiveRegion="polite" style={styles.error}>{message}</Text>}
    <PrimaryButton label="변경 저장" disabled={!current || password.isPending} loading={password.isPending} onPress={() => void save()} />
    <PrimaryButton label="돌아가기" disabled={password.isPending} onPress={() => navigation.goBack()} />
  </ScrollView></ScreenContainer>;
}
const styles = StyleSheet.create({
  content: { gap: 18 }, title: { fontSize: 24, fontWeight: "700" },
  input: { minHeight: 52, padding: 14, borderRadius: 8, borderWidth: 1, borderColor: "#AAA" },
  error: { color: "#A62828", lineHeight: 22 },
});
