import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_STORAGE_KEY =
    "trend-leader.access-token";

export async function saveAccessToken(
    accessToken: string,
): Promise<void> {
    await SecureStore.setItemAsync(
        ACCESS_TOKEN_STORAGE_KEY,
        accessToken,
    );
}

export async function getAccessToken(): Promise<
    string | null
> {
    return SecureStore.getItemAsync(
        ACCESS_TOKEN_STORAGE_KEY,
    );
}

export async function deleteAccessToken(): Promise<void> {
    await SecureStore.deleteItemAsync(
        ACCESS_TOKEN_STORAGE_KEY,
    );
}