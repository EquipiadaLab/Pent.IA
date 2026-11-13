import { create } from "zustand";
import { api } from "@/lib/api";
import {
  clearToken,
  getToken,
  setToken,
  UNAUTHORIZED_EVENT,
  type AuthUser,
} from "@/lib/auth";

type AuthStatus = "loading" | "authed" | "anon";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

interface AuthState {
  user: AuthUser | null;
  status: AuthStatus;
  /** Verifica o token salvo chamando /auth/me (chamado uma vez no boot). */
  bootstrap: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: "loading",
  bootstrap: async () => {
    if (!getToken()) {
      set({ status: "anon", user: null });
      return;
    }
    try {
      const { data } = await api.get<AuthUser>("/auth/me");
      set({ user: data, status: "authed" });
    } catch {
      clearToken();
      set({ status: "anon", user: null });
    }
  },
  login: async (username, password) => {
    const { data } = await api.post<LoginResponse>("/auth/login", {
      username,
      password,
    });
    setToken(data.access_token);
    set({ user: data.user, status: "authed" });
  },
  logout: () => {
    clearToken();
    set({ user: null, status: "anon" });
  },
}));

// Sessão expirada (401 vindo do interceptor): volta para a tela de login.
if (typeof window !== "undefined") {
  window.addEventListener(UNAUTHORIZED_EVENT, () => {
    useAuth.getState().logout();
  });
}
