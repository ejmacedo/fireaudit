import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { authStorage } from "@/lib/api/auth-storage";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = authStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = authStorage.getRefreshToken();
  if (!refreshToken) return null;

  try {
    const { data } = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/v1/auth/refresh`,
      { refresh_token: refreshToken }
    );
    authStorage.setTokens(data.access_token, data.refresh_token);
    return data.access_token as string;
  } catch {
    return null;
  }
}

// Auth endpoints manage their own error handling (e.g. the login form shows
// "Email or password is incorrect."). A 401 from these is never an expired
// session, so it must never trigger the refresh-token/redirect-to-login flow
// below — that flow does a full-page navigation, which would wipe out the
// login form's own error message almost instantly.
const AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH = ["/v1/auth/login", "/v1/auth/refresh"];

function isExcludedFromRefreshFlow(url: string | undefined): boolean {
  if (!url) return false;
  return AUTH_ENDPOINTS_EXCLUDED_FROM_REFRESH.some((path) => url.includes(path));
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;

    if (isExcludedFromRefreshFlow(originalRequest?.url)) {
      return Promise.reject(error);
    }

    if (error.response?.status !== 401 || !originalRequest || originalRequest._retried) {
      if (error.response?.status === 401) {
        authStorage.clear();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
      }
      return Promise.reject(error);
    }

    originalRequest._retried = true;

    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const newAccessToken = await refreshPromise;

    if (!newAccessToken) {
      authStorage.clear();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      return Promise.reject(error);
    }

    originalRequest.headers = originalRequest.headers ?? {};
    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
    return apiClient(originalRequest);
  }
);
