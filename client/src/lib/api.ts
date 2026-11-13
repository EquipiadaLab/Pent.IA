import axios from "axios";
import { clearToken, getToken, UNAUTHORIZED_EVENT } from "./auth";

const baseURL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export const api = axios.create({
  baseURL,
  timeout: 45_000,
});

// Anexa o token JWT em toda requisição autenticada.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 com token presente (fora do /auth/login) => sessão expirou: desloga.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? "";
      if (!url.includes("/auth/login") && getToken()) {
        clearToken();
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
      }
    }
    return Promise.reject(error);
  },
);

export function getApiErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return "A API excedeu o tempo limite. Tente novamente.";
    }

    if (!error.response) {
      return "Não foi possível conectar à API. Verifique se o servidor está disponível.";
    }

    const detail = error.response?.data?.detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item: unknown) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String(item.msg);
          }
          return String(item);
        })
        .join("; ");
    }
    if (typeof detail === "string" && detail) return detail;
    return `A API respondeu com erro HTTP ${error.response.status}.`;
  }

  return error instanceof Error
    ? error.message
    : "Falha na comunicação com a API.";
}
