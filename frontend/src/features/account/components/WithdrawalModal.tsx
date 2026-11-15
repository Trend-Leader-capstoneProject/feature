import axios from "axios";
import { useRef, useState } from "react";
import { Alert, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useAuth } from "../../../app/providers/AuthProvider";
import { getErrorReason } from "../../../shared/api/authenticatedApiClient";
import { getAuthEpoch } from "../../../shared/handler/authRequestGate";
import { useAccountActions } from "../hooks/useAccountActions";

export function WithdrawalModal({ onClose }: { onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [unknown, setUnknown] = useState(false);
  const busy = useRef(false);
  const actions = useAccountActions();
  const { clearLocalSession } = useAuth();
  const pending = actions.verify.isPending || actions.withdrawal.isPending;
  function close() { if (!busy.current) { setPassword(""); onClose(); } }
  async function execute(value: string, epoch: number) {
    if (busy.current || epoch !== getAuthEpoch()) return;
    busy.current = true;
    try {
      await actions.withdrawal.mutateAsync(value);
      if (epoch !== getAuthEpoch()) return;
      setPassword("");
      try {
        await clearLocalSession();
        Alert.alert("회원 탈퇴 완료", "계정과 연결 데이터가 삭제됐습니다.");
      } catch { Alert.alert("기기 정보 정리 필요", "서버 탈퇴는 완료됐습니다. 기기에 남은 로그인 정보 정리를 다시 시도해 주세요."); }
    } catch (error) {
      if (epoch !== getAuthEpoch()) return;
      if (getErrorReason(error) === "CURRENT_PASSWORD_MISMATCH") setMessage("현재 비밀번호가 올바르지 않습니다.");
      else if (axios.isAxiosError(error) && error.response && error.response.status < 500) setMessage("입력과 로그인 상태를 확인해 주세요.");
      else { setUnknown(true); setMessage("탈퇴 결과를 확인하지 못했습니다. 자동으로 다시 요청하지 않습니다. 로그인 화면에서 계정 상태를 확인해 주세요."); }
    } finally { busy.current = false; }
  }
  async function verify() {
    if (busy.current || !password) return;
    busy.current = true; setMessage("");
    const epoch = getAuthEpoch();
    try {
      await actions.verify.mutateAsync(password);
      if (epoch !== getAuthEpoch()) return;
      const value = password;
      Alert.alert("정말 탈퇴할까요?", "계정과 연결된 정보가 삭제되며 되돌릴 수 없습니다.", [
        { text: "취소", style: "cancel" },
        { text: "회원 탈퇴", style: "destructive", onPress: () => void execute(value, epoch) },
      ]);
    } catch (error) {
      if (epoch === getAuthEpoch()) setMessage(getErrorReason(error) === "CURRENT_PASSWORD_MISMATCH" ? "현재 비밀번호가 올바르지 않습니다." : "비밀번호 확인에 실패했습니다. 다시 시도해 주세요.");
    } finally { busy.current = false; }
  }
  return <Modal visible transparent animationType="fade" onRequestClose={close}>
    <View style={styles.overlay}><View style={styles.card} accessibilityViewIsModal>
      <Text accessibilityRole="header" style={styles.title}>회원 탈퇴</Text>
      <Text>현재 비밀번호를 확인한 뒤 최종 탈퇴를 진행합니다.</Text>
      <TextInput accessibilityLabel="탈퇴 현재 비밀번호" secureTextEntry value={password} onChangeText={setPassword} editable={!pending && !unknown} autoCapitalize="none" style={styles.input} />
      {!!message && <Text accessibilityLiveRegion="polite" style={styles.message}>{message}</Text>}
      {unknown ? <Pressable accessibilityRole="button" style={styles.button} onPress={() => { setPassword(""); void clearLocalSession().catch(() => undefined); }}><Text>로그인 화면에서 확인</Text></Pressable> :
        <Pressable accessibilityRole="button" disabled={pending || !password} style={styles.button} onPress={() => void verify()}><Text>{pending ? "처리 중…" : "비밀번호 확인"}</Text></Pressable>}
      <Pressable accessibilityRole="button" disabled={pending} style={styles.button} onPress={close}><Text>취소</Text></Pressable>
    </View></View>
  </Modal>;
}
const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0007", padding: 24 },
  card: { padding: 24, borderRadius: 12, backgroundColor: "white", width: "100%", maxWidth: 420, gap: 16 },
  title: { fontSize: 22, fontWeight: "700" }, input: { borderWidth: 1, borderColor: "#AAA", minHeight: 48, padding: 12, borderRadius: 8 },
  message: { color: "#A62828", lineHeight: 22 }, button: { minHeight: 48, alignItems: "center", justifyContent: "center" },
});
