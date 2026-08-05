import Constants from "expo-constants";

const DEFAULT_API_PORT = "8000";
const DEFAULT_API_PREFIX = "/api";

function normalizeApiPrefix(prefix: string): string {
  const withLeadingSlash = prefix.startsWith("/")
    ? prefix
    : `/${prefix}`;

  return withLeadingSlash.replace(/\/+$/, "");
}

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, "");
}

function getExpoDevelopmentHost(): string | null {
  const hostUri = Constants.expoConfig?.hostUri;

  if (!hostUri) {
    return null;
  }

  try {
    const normalizedHostUri = hostUri.includes("://")
      ? hostUri
      : `http://${hostUri}`;

    return new URL(normalizedHostUri).hostname;
  } catch {
    return null;
  }
}

function resolveApiBaseUrl(): string {
  const explicitApiBaseUrl =
    process.env.EXPO_PUBLIC_API_BASE_URL;

  /*
   * 운영 또는 배포 빌드에서는 Expo 개발 서버 주소에 의존하지 않고,
   * 명시적으로 설정한 API 주소를 사용한다.
   */
  if (!__DEV__) {
    if (!explicitApiBaseUrl) {
      throw new Error(
        "EXPO_PUBLIC_API_BASE_URL이 설정되지 않았습니다.",
      );
    }

    return normalizeBaseUrl(explicitApiBaseUrl);
  }

  /*
   * Expo Go 또는 Development Build의 LAN 개발 환경에서는
   * Metro 서버가 실행되는 PC의 IP를 자동으로 가져온다.
   */
  const developmentHost = getExpoDevelopmentHost();

  if (developmentHost) {
    const apiPort =
      process.env.EXPO_PUBLIC_API_PORT ??
      DEFAULT_API_PORT;

    const apiPrefix = normalizeApiPrefix(
      process.env.EXPO_PUBLIC_API_PREFIX ??
        DEFAULT_API_PREFIX,
    );

    return `http://${developmentHost}:${apiPort}${apiPrefix}`;
  }

  /*
   * Expo 개발 서버 주소를 찾지 못한 경우
   * .env의 명시적인 주소를 fallback으로 사용한다.
   */
  if (explicitApiBaseUrl) {
    return normalizeBaseUrl(explicitApiBaseUrl);
  }

  throw new Error(
    "API 서버 주소를 결정할 수 없습니다. " +
      "Expo 개발 서버 또는 EXPO_PUBLIC_API_BASE_URL을 확인해 주세요.",
  );
}

export const API_BASE_URL = resolveApiBaseUrl();

if (__DEV__) {
  console.log("[Trend Leader API]", API_BASE_URL);
}