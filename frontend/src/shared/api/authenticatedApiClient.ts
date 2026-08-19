import { getAccessToken } from "../storage/tokenStorage";
import { createApiClient } from "./createApiClient";

export const authenticatedApiClient =
  createApiClient();

authenticatedApiClient.interceptors.request.use(
  async (config) => {
    const accessToken =
      await getAccessToken();

    if (accessToken) {
      config.headers.set(
        "Authorization",
        `Bearer ${accessToken}`,
      );
    }

    return config;
  },
);
