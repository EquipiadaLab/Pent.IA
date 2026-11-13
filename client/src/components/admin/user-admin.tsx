import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, UserPlus, Users } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api";
import type { AuthUser, UserRole } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/** Gestão de contas (somente admin): cadastro é feito aqui, nunca por signup. */
export function UserAdmin() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("operator");
  const [notice, setNotice] = useState("");

  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: async () => (await api.get<AuthUser[]>("/auth/users")).data,
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await api.post<AuthUser>("/auth/users", { username, password, role })
      ).data,
    onSuccess: (user) => {
      setNotice(`Usuário "${user.username}" criado.`);
      setUsername("");
      setPassword("");
      setRole("operator");
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const canSubmit = username.trim().length >= 3 && password.length >= 6;

  return (
    <Card className="border-border/60 bg-card/50">
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          <Users className="size-4" />
          Contas de acesso
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Cadastro é feito pelo sistema: só um admin cria contas. Usuário (mín. 3)
          e senha (mín. 6).
        </p>

        <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto]">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="usuário"
            autoComplete="off"
            className="h-9 rounded-md border border-border/60 bg-background/50 px-2.5 text-sm text-foreground outline-none focus:border-primary/50"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="senha"
            autoComplete="new-password"
            className="h-9 rounded-md border border-border/60 bg-background/50 px-2.5 text-sm text-foreground outline-none focus:border-primary/50"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="h-9 rounded-md border border-border/60 bg-background/50 px-2 text-sm text-foreground outline-none focus:border-primary/50"
          >
            <option value="operator">Operador</option>
            <option value="admin">Admin</option>
          </select>
          <Button
            size="sm"
            disabled={!canSubmit || createMutation.isPending}
            onClick={() => {
              setNotice("");
              createMutation.mutate();
            }}
            className="h-9 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {createMutation.isPending ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <UserPlus />
            )}
            Criar
          </Button>
        </div>

        {createMutation.isError && (
          <p role="alert" className="mt-2 text-xs text-rose-300">
            {getApiErrorMessage(createMutation.error)}
          </p>
        )}
        {notice && <p className="mt-2 text-xs text-emerald-300">{notice}</p>}

        <div className="mt-4 border-t border-border/50 pt-3">
          {usersQuery.isPending ? (
            <div className="flex items-center justify-center py-2 text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" />
            </div>
          ) : usersQuery.isError ? (
            <p className="text-xs text-rose-300">
              {getApiErrorMessage(usersQuery.error)}
            </p>
          ) : (
            <ul className="space-y-1.5">
              {(usersQuery.data ?? []).map((u) => (
                <li
                  key={u.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border/50 bg-background/30 px-3 py-1.5 text-xs"
                >
                  <span className="truncate font-medium text-foreground">
                    {u.username}
                  </span>
                  <span
                    className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${
                      u.role === "admin"
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-border/60 text-muted-foreground"
                    }`}
                  >
                    {u.role === "admin" ? "Admin" : "Operador"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
