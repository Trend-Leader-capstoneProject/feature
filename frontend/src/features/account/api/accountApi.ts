import { authenticatedApiClient } from "../../../shared/api/authenticatedApiClient";
import { publicApiClient } from "../../../shared/api/publicApiClient";
import type { CommonResponse } from "../../../shared/types/api";
import { API_BASE_URL } from "../../../app/config/apiConfig";
import type { NicknameAvailability, Profile, SelectedPhoto } from "../types/account";

export async function getProfile(): Promise<Profile> {
  return (await authenticatedApiClient.get<CommonResponse<Profile>>("/users/me")).data.data;
}
export async function checkNickname(nickname: string, own: boolean): Promise<NicknameAvailability> {
  const client = own ? authenticatedApiClient : publicApiClient;
  return (await client.get<CommonResponse<NicknameAvailability>>(
    own ? "/users/me/check-nickname" : "/auth/check-nickname", { params: { nickname } },
  )).data.data;
}
export async function saveNickname(nickname: string): Promise<Profile> {
  return (await authenticatedApiClient.patch<CommonResponse<Profile>>(
    "/users/me/nickname", { nickname },
  )).data.data;
}
export async function savePhoto(photo: SelectedPhoto): Promise<Profile> {
  const form = new FormData();
  form.append("image", { uri: photo.uri, name: photo.name, type: photo.type } as unknown as Blob);
  return (await authenticatedApiClient.put<CommonResponse<Profile>>(
    "/users/me/profile-image", form, { headers: { "Content-Type": "multipart/form-data" } },
  )).data.data;
}
export async function resetPhoto(): Promise<Profile> {
  return (await authenticatedApiClient.delete<CommonResponse<Profile>>("/users/me/profile-image")).data.data;
}
export async function changePassword(current: string, next: string, confirm: string): Promise<void> {
  await authenticatedApiClient.put("/users/me/password", {
    current_password: current, new_password: next, new_password_confirm: confirm,
  });
}
export async function verifyWithdrawal(password: string): Promise<void> {
  await authenticatedApiClient.post("/users/me/withdrawal/verify-password", { current_password: password });
}
export async function withdraw(password: string): Promise<void> {
  await authenticatedApiClient.post("/users/me/withdrawal", { current_password: password });
}
function base64(bytes: Uint8Array): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let output = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i], b = bytes[i + 1] ?? 0, c = bytes[i + 2] ?? 0;
    output += alphabet[a >> 2] + alphabet[((a & 3) << 4) | (b >> 4)] +
      (i + 1 < bytes.length ? alphabet[((b & 15) << 2) | (c >> 6)] : "=") +
      (i + 2 < bytes.length ? alphabet[c & 63] : "=");
  }
  return output;
}
export async function getProtectedPhoto(path: string): Promise<string> {
  const url = new URL(path, API_BASE_URL + "/");
  if (url.origin !== new URL(API_BASE_URL).origin || url.username || url.password) throw new Error("잘못된 사진 주소입니다.");
  const response = await authenticatedApiClient.get<ArrayBuffer>(url.toString(), { responseType: "arraybuffer" });
  const type = response.headers["content-type"]?.toString().split(";")[0];
  if (!["image/png", "image/jpeg"].includes(type ?? "") || response.data.byteLength > 5_000_000) throw new Error("사진 응답을 확인하지 못했습니다.");
  return `data:${type};base64,${base64(new Uint8Array(response.data))}`;
}
