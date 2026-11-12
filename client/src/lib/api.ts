import axios from "axios";

const baseURL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export const api = axios.create({
  baseURL,
  timeout: 45_000,
});

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
