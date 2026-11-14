import { useState } from "react";
import {
  Alert, Image, KeyboardAvoidingView, Modal, Platform,
  Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { resetPhoto, saveNickname, savePhoto } from "../api/accountApi";
import { useNicknameDraft, normalizeNickname } from "../hooks/useNicknameDraft";
import { useProfileWrite } from "../hooks/useProfileWrite";
import { useMyProfile } from "../hooks/useMyProfile";
import { ProtectedAvatar } from "./ProtectedAvatar";
import type { Profile, SelectedPhoto } from "../types/account";

export function ProfileEditorModal({ type, profile, onClose }: {
  type: "PHOTO" | "NICKNAME"; profile: Profile; onClose: () => void;
}) {
  const nickname = useNicknameDraft(profile.nickname, true);
  const write = useProfileWrite();
  const current = useMyProfile();
  const [photo, setPhoto] = useState<SelectedPhoto | null>(null);
  const [photoAction, setPhotoAction] = useState<"REPLACE" | "RESET" | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const dirty = type === "NICKNAME" ? nickname.value !== profile.nickname : photoAction !== null;
  const validNickname = (() => { try { return normalizeNickname(nickname.value); } catch { return null; } })();
  function close() {
    if (write.busy.current) return;
    if (dirty) Alert.alert("변경 내용을 버릴까요?", write.uncertain ? "저장 결과는 확인되지 않았습니다. 창을 닫아도 서버에서 처리된 결과가 취소되지는 않습니다." : undefined, [
      { text: "계속 수정", style: "cancel" }, { text: "버리기", style: "destructive", onPress: onClose },
    ]); else onClose();
  }
  async function pick() {
    if (write.busy.current) return;
    setSelectionError("");
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"], allowsEditing: false, allowsMultipleSelection: false, quality: 1,
      });
      if (result.canceled || !result.assets[0]) return;
      const asset = result.assets[0];
      if (asset.fileSize && asset.fileSize > 5_000_000) { setSelectionError("사진은 5MB 이하여야 합니다."); return; }
      if (asset.mimeType && !["image/jpeg", "image/png", "image/jpg"].includes(asset.mimeType)) { setSelectionError("JPEG·PNG 사진을 선택해 주세요."); return; }
      setPhoto({ uri: asset.uri, name: asset.fileName ?? "profile.jpg", type: asset.mimeType === "image/png" ? "image/png" : "image/jpeg" });
      setPhotoAction("REPLACE");
    } catch { setSelectionError("사진을 선택하지 못했습니다. 기기의 사진 접근 설정을 확인하고 다시 시도해 주세요."); }
  }
  async function save() {
    if (write.busy.current) return;
    const operation = type === "NICKNAME"
      ? () => saveNickname(validNickname!)
      : photoAction === "RESET" ? resetPhoto : () => savePhoto(photo!);
    if (await write.run(operation) === "SUCCESS") onClose();
    else if (type === "NICKNAME") nickname.invalidate("저장 전 중복 확인을 다시 해 주세요.");
  }
  const canSave = dirty && !write.pending && (!write.uncertain || write.verified) &&
    (type === "PHOTO" ? photoAction !== null : !!validNickname && nickname.available === validNickname);
  return <Modal visible transparent animationType="fade" onRequestClose={close}>
    <KeyboardAvoidingView style={styles.overlay} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Pressable accessibilityLabel="프로필 변경창 닫기" style={StyleSheet.absoluteFill} onPress={close} />
      <View style={styles.card} accessibilityViewIsModal>
        <ScrollView keyboardShouldPersistTaps="handled">
          <Text accessibilityRole="header" style={styles.title}>{type === "PHOTO" ? "프로필 사진 변경" : "닉네임 변경"}</Text>
          {type === "PHOTO" ? <>
            <View style={styles.preview}>
              {photoAction === "REPLACE" && photo ? <Image source={{ uri: photo.uri }} style={styles.photo} /> :
                <ProtectedAvatar url={photoAction === "RESET" ? null : profile.profile_image_url} size={96} />}
            </View>
            <Pressable accessibilityRole="button" disabled={write.pending} onPress={() => void pick()} style={styles.secondary}><Text>갤러리에서 사진 선택</Text></Pressable>
            <Pressable accessibilityRole="button" disabled={write.pending} onPress={() => { setPhoto(null); setPhotoAction("RESET"); }} style={styles.secondary}><Text>기본 이미지로 되돌리기</Text></Pressable>
            <Text style={styles.helper}>정지 JPEG·PNG · 최대 5MB · 2,000만 화소</Text>
          </> : <>
            <TextInput accessibilityLabel="새 닉네임" value={nickname.value} onChangeText={nickname.update} editable={!write.pending} autoCapitalize="none" autoCorrect={false} style={styles.input} />
            <Text style={styles.helper}>2~10자 · 한글·영문·숫자·밑줄</Text>
            <Pressable accessibilityRole="button" disabled={nickname.checking || write.pending} onPress={() => void nickname.check()} style={styles.secondary}><Text>{nickname.checking ? "확인 중…" : "중복 확인"}</Text></Pressable>
            <Text accessibilityLiveRegion="polite">{nickname.feedback}</Text>
          </>}
          {!!selectionError && <Text style={styles.error}>{selectionError}</Text>}
          {!!write.message && <Text accessibilityLiveRegion="polite" style={styles.error}>{write.message}</Text>}
          {write.uncertain && <>
            {write.verified && <View style={styles.current}>
              <Text>현재 서버 닉네임: {current.data?.nickname}</Text>
              <ProtectedAvatar url={current.data?.profile_image_url} size={48} />
            </View>}
            <Pressable accessibilityRole="button" disabled={write.pending} onPress={() => void write.checkResult()} style={styles.secondary}><Text>저장 결과 확인</Text></Pressable>
          </>}
          <View style={styles.buttons}>
            <Pressable accessibilityRole="button" disabled={write.pending} onPress={close} style={styles.secondary}><Text>취소</Text></Pressable>
            <Pressable accessibilityRole="button" disabled={!canSave} onPress={() => void save()} style={[styles.save, !canSave && styles.disabled]}><Text style={styles.white}>{write.pending ? "처리 중…" : "저장"}</Text></Pressable>
          </View>
        </ScrollView>
      </View>
    </KeyboardAvoidingView>
  </Modal>;
}
const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: "#0007", justifyContent: "center", alignItems: "center", padding: 24 },
  card: { width: "100%", maxWidth: 420, maxHeight: "85%", padding: 24, borderRadius: 14, backgroundColor: "white" },
  title: { fontSize: 21, fontWeight: "700", marginBottom: 22 },
  preview: { alignItems: "center", marginBottom: 20 },
  photo: { width: 96, height: 96, borderRadius: 48 },
  input: { minHeight: 48, borderWidth: 1, borderColor: "#AAA", borderRadius: 8, padding: 12 },
  secondary: { minHeight: 48, paddingHorizontal: 12, justifyContent: "center", alignItems: "center" },
  helper: { color: "#666", marginVertical: 8, lineHeight: 20 },
  error: { color: "#A62828", marginVertical: 10, lineHeight: 22 },
  buttons: { flexDirection: "row", justifyContent: "flex-end", gap: 12, marginTop: 16 },
  save: { minHeight: 48, paddingHorizontal: 24, justifyContent: "center", backgroundColor: "#4031D8", borderRadius: 8 },
  white: { color: "white", fontWeight: "600" },
  disabled: { opacity: .4 }, current: { gap: 10 },
});
