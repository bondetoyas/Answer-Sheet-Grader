import { useCallback } from "react";

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "grader_token";

export function readToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function saveToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the login lasts for this page only */
  }
}

/** fetch() wrapper that sends the login token and logs out when it expires. */
export function useApi(token, onLogout) {
  return useCallback(
    async (path, options = {}) => {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) onLogout();
      return response;
    },
    [token, onLogout]
  );
}

/** Turn a failed response into a readable Error message. */
export async function readError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  if (Array.isArray(data.detail)) return "Please check the values entered.";
  return data.detail || fallback;
}
