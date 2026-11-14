import { useQuery } from "@tanstack/react-query";
import { Image, StyleSheet, View } from "react-native";
import { getAuthEpoch } from "../../../shared/handler/authRequestGate";
import { getProtectedPhoto } from "../api/accountApi";

export function ProtectedAvatar({ url, size = 80 }: { url: string | null | undefined; size?: number }) {
  const image = useQuery({
    queryKey: ["protected-photo", getAuthEpoch(), url], queryFn: () => getProtectedPhoto(url!),
    enabled: !!url, retry: false, gcTime: 0,
  });
  return <View accessibilityLabel={image.isError ? "프로필 사진을 불러오지 못했습니다" : "프로필 사진"}
    style={[styles.circle, { width: size, height: size, borderRadius: size / 2 }]}>
    {image.data && <Image source={{ uri: image.data }} style={{ width: size, height: size, borderRadius: size / 2 }} />}
  </View>;
}
const styles = StyleSheet.create({ circle: { backgroundColor: "#D9D9D9", overflow: "hidden" } });
