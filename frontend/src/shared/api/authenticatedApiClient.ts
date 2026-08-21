import axios, {
  type InternalAxiosRequestConfig,
} from "axios";

import {
  notifyAuthFailure,
} from "../handler/authFailureHandler";
import {
  getAccessToken,
} from "../storage/tokenStorage";
import {
  createApiClient,
} from "./createApiClient";

export const authenticatedApiClient =
  createApiClient();

function getRequestAccessToken(
  config:
    | InternalAxiosRequestConfig
    | undefined,
): string | null {
  const authorization =
    config?.headers.get("Authorization");

  if (
    typeof authorization !== "string"
  ) {
    return null;
  }

  const match =
    /^Bearer\s+(\S+)$/i.exec(
      authorization.trim(),
    );

  return match?.[1] ?? null;
}

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

authenticatedApiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (
      !axios.isAxiosError(error) ||
      error.response?.status !== 401
    ) {
      return Promise.reject(error);
    }

    const requestAccessToken =
      getRequestAccessToken(
        error.config,
      );

    if (!requestAccessToken) {
      return Promise.reject(error);
    }

    let currentAccessToken:
      string | null;

    try {
      currentAccessToken =
        await getAccessToken();
    } catch {
      return Promise.reject(error);
    }

    if (
      currentAccessToken !==
      requestAccessToken
    ) {
      return Promise.reject(error);
    }

    notifyAuthFailure();

    return Promise.reject(error);
  },
);
