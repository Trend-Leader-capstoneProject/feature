const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

if (!apiBaseUrl) {
    throw new Error(
        "EXPO_PUBLIC_API_BASE_URL 환경변수가 설정되지 않았습니다.",
    );
}

export const env = {
    apiBaseUrl,
} as const;