import {
    Alert,
    Linking,
} from "react-native";


export async function openTrendSourceUrl(
  url: string,
): Promise<void> {
  try {
    await Linking.openURL(url);
  } catch {
    Alert.alert(
      "원문을 열 수 없습니다.",
      "잠시 후 다시 시도해 주세요.",
    );
  }
}
