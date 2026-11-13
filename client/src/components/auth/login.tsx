import { useState } from "react";
import { motion } from "motion/react";
import { LoaderCircle, Lock, LogIn, Shield, User } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api";
import { AmbientBackground } from "@/components/layout/ambient-background";
import { Button } from "@/components/ui/button";

export function Login() {
  const login = useAuth((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setSubmitting(true);
    setError("");
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-svh items-center justify-center px-4 text-foreground">
      <AmbientBackground />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="grid size-14 place-items-center rounded-2xl border border-primary/30 bg-primary/10 text-primary shadow-[0_0_30px_-8px_var(--primary)]">
            <Shield className="size-7" />
          </span>
          <h1 className="mt-4 text-xl font-bold tracking-[0.18em]">
            PENT<span className="text-primary">.IA</span>
          </h1>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Pente fino no sistema
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-border/60 bg-card/60 p-6 backdrop-blur-xl"
          noValidate
        >
          <h2 className="text-sm font-semibold text-foreground">Entrar</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Acesso restrito. As contas são criadas pelo sistema.
          </p>

          <label className="mt-5 grid gap-1.5 text-xs text-muted-foreground">
            Usuário
            <div className="flex h-10 items-center gap-2 rounded-md border border-border/60 bg-background/50 px-3 focus-within:border-primary/50">
              <User className="size-3.5 shrink-0 text-muted-foreground" />
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                className="h-full min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/60"
                placeholder="seu usuário"
              />
            </div>
          </label>

          <label className="mt-3 grid gap-1.5 text-xs text-muted-foreground">
            Senha
            <div className="flex h-10 items-center gap-2 rounded-md border border-border/60 bg-background/50 px-3 focus-within:border-primary/50">
              <Lock className="size-3.5 shrink-0 text-muted-foreground" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="h-full min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/60"
                placeholder="••••••••"
              />
            </div>
          </label>

          {error && (
            <p role="alert" className="mt-3 text-xs text-rose-300">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={submitting}
            className="mt-5 w-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {submitting ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <LogIn />
            )}
            Entrar
          </Button>
        </form>
      </motion.div>
    </div>
  );
}
