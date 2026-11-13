/** Estado de autenticação guardado no navegador (token JWT) e tipos de usuário. */

export type UserRole = "admin" | "operator";

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
  created_at?: string | null;
}

const TOKEN_KEY = "pentia_token";

/** Evento disparado quando a API responde 401 com um token presente. */
export const UNAUTHORIZED_EVENT = "pentia-unauthorized";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignora storage indisponível (modo privado) */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignora */
  }
}
