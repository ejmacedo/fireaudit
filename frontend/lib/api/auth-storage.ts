const ACCESS_TOKEN_KEY = "fireaudit_access_token";
const REFRESH_TOKEN_KEY = "fireaudit_refresh_token";

/**
 * Thin wrapper around localStorage for auth tokens. Centralised so that no
 * other module reaches into localStorage directly (makes it trivial to swap
 * storage strategy later, e.g. httpOnly cookies).
 */
export const authStorage = {
  getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens(accessToken: string, refreshToken: string): void {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clear(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};
