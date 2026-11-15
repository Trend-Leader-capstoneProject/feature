export interface Profile {
  user_id: number;
  nickname: string;
  profile_image_url: string | null;
}
export interface NicknameAvailability {
  nickname: string;
  is_available: boolean;
  reason: "DUPLICATED_NICKNAME" | null;
}
export interface SelectedPhoto { uri: string; name: string; type: string; }
