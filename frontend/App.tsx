import { Text, View } from "react-native";

export default function AppEntry() {
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text>Trend Leader</Text>
      <Text>Expo frontend 연결 성공</Text>
    </View>
  );
}