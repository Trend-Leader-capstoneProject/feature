import Constants from "expo-constants";
import { Platform } from "react-native";

export const APP_NAME = Constants.expoConfig?.name ?? "Trend Leader";
export const APP_VERSION = Constants.expoConfig?.version ?? "알 수 없음";
export const PROJECT_URL = "https://github.com/Trend-Leader-capstoneProject/feature";
export const CONTACT_URL = PROJECT_URL + "/issues/new?" + new URLSearchParams({
  title: "[앱 문의] ",
  body: [
    "문의 유형: 오류 / 사용 방법 / 개선 제안",
    "", "문의 내용:", "", "재현 순서 (오류인 경우):", "",
    "기대했던 동작:", "", "실제 동작:", "",
    "앱 버전: " + APP_VERSION, "플랫폼: " + Platform.OS,
    "", "※ 공개 게시판입니다. 비밀번호, 로그인 토큰, 실명·연락처 등 개인정보를 적지 마세요.",
  ].join("\n"),
}).toString();

export const OPEN_SOURCE = [
  { name: "React", license: "MIT", url: "https://github.com/facebook/react/blob/main/LICENSE" },
  { name: "React Native", license: "MIT", url: "https://github.com/facebook/react-native/blob/main/LICENSE" },
  { name: "Expo", license: "MIT", url: "https://github.com/expo/expo/blob/main/LICENSE" },
  { name: "React Navigation", license: "MIT", url: "https://github.com/react-navigation/react-navigation/blob/main/LICENSE" },
  { name: "TanStack Query", license: "MIT", url: "https://github.com/TanStack/query/blob/main/LICENSE" },
  { name: "Axios", license: "MIT", url: "https://github.com/axios/axios/blob/v1.x/LICENSE" },
  { name: "Lucide 아이콘", license: "ISC", url: "https://github.com/lucide-icons/lucide/blob/main/LICENSE" },
] as const;
export const FAQ = [
  { question: "맞춤 트렌드는 무엇을 기준으로 보여주나요?", answer: "선택한 관심사를 바탕으로 트렌드를 보여줍니다. ‘내 정보 → 관심사 재설정’에서 관심사를 바꿀 수 있습니다." },
  { question: "닉네임과 프로필 사진은 어디서 바꾸나요?", answer: "내 정보에서 닉네임 옆 ‘변경’ 또는 사진의 ‘＋’를 누르세요. 닉네임은 중복 확인 후 저장하며, 사진도 선택 후 저장을 눌러야 반영됩니다. 사진은 정지 JPEG·PNG, 5MB 이하를 지원합니다." },
  { question: "테마 설정은 어디에 저장되나요?", answer: "현재 기기에 저장되며 앱을 다시 열거나 로그아웃해도 유지됩니다. ‘기기 설정 따르기’를 선택하면 휴대폰의 라이트·다크 설정을 따라갑니다." },
  { question: "로딩이 길거나 데이터를 불러오지 못해요.", answer: "인터넷 연결을 확인한 뒤 화면의 다시 시도를 눌러 주세요. 문제가 계속되면 문의에 발생 화면과 재현 순서를 알려주세요. 비밀번호나 로그인 토큰은 보내지 마세요." },
  { question: "비밀번호를 바꾸면 다른 기기도 로그아웃되나요?", answer: "현재 기기의 로그인은 유지하고 다른 기기는 다시 로그인해야 합니다. 내 정보의 ‘비밀번호 변경’에서 현재 비밀번호와 새 비밀번호를 입력해 변경할 수 있습니다." },
] as const;
