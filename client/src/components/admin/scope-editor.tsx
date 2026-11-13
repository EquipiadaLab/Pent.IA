import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, Save, ShieldCheck } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface AdminScope {
  authorized_targets: string[];
  blocked_scopes: string[];
}

function toText(items: string[]): string {
  return items.join("\n");
}

function toList(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of text.split("\n")) {
    const value = line.trim();
    if (value && !seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
  }
  return out;
}

/** Editor visível apenas para admins: alvos autorizados e escopos bloqueados. */
export function AdminScopeEditor() {
  const queryClient = useQueryClient();
  // `null` = ainda não editado: mostra o valor vindo do servidor.
  const [authorizedDraft, setAuthorizedDraft] = useState<string | null>(null);
  const [blockedDraft, setBlockedDraft] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const scopeQuery = useQuery({
    queryKey: ["admin-scope"],
    queryFn: async () => (await api.get<AdminScope>("/admin/scope")).data,
  });

  const authorized =
    authorizedDraft ?? toText(scopeQuery.data?.authorized_targets ?? []);
  const blocked = blockedDraft ?? toText(scopeQuery.data?.blocked_scopes ?? []);

  const saveMutation = useMutation({
    mutationFn: async () =>
      (
        await api.put<AdminScope>("/admin/scope", {
          authorized_targets: toList(authorized),
          blocked_scopes: toList(blocked),
        })
      ).data,
    onSuccess: (data) => {
      setAuthorizedDraft(toText(data.authorized_targets));
      setBlockedDraft(toText(data.blocked_scopes));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
      void queryClient.invalidateQueries({ queryKey: ["scope"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-scope"] });
    },
  });

  return (
    <Card className="border-primary/25 bg-primary/[0.04]">
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          <ShieldCheck className="size-4" />
          Administração de escopo
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Um endereço por linha. As URLs autorizadas valem quando o alvo não está
          travado por variável de ambiente; os escopos bloqueados são sempre
          recusados.
        </p>

        {scopeQuery.isPending ? (
          <div className="flex min-h-24 items-center justify-center text-muted-foreground">
            <LoaderCircle className="size-5 animate-spin" />
          </div>
        ) : scopeQuery.isError ? (
          <p role="alert" className="mt-4 text-xs text-rose-300">
            {getApiErrorMessage(scopeQuery.error)}
          </p>
        ) : (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              URLs autorizadas
              <textarea
                value={authorized}
                onChange={(e) => setAuthorizedDraft(e.target.value)}
                rows={5}
                spellCheck={false}
                placeholder="https://alvo-autorizado.com"
                className="w-full resize-y rounded-lg border border-border/60 bg-background/50 p-2.5 font-mono text-xs text-foreground outline-none focus:border-primary/50"
              />
            </label>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              Escopos bloqueados
              <textarea
                value={blocked}
                onChange={(e) => setBlockedDraft(e.target.value)}
                rows={5}
                spellCheck={false}
                placeholder="interno.exemplo.com"
                className="w-full resize-y rounded-lg border border-border/60 bg-background/50 p-2.5 font-mono text-xs text-foreground outline-none focus:border-rose-400/50"
              />
            </label>
          </div>
        )}

        {saveMutation.isError && (
          <p role="alert" className="mt-3 text-xs text-rose-300">
            {getApiErrorMessage(saveMutation.error)}
          </p>
        )}

        <div className="mt-4 flex items-center justify-end gap-3">
          {saved && (
            <span className="flex items-center gap-1 text-xs text-emerald-300">
              <Check className="size-3.5" />
              Salvo
            </span>
          )}
          <Button
            size="sm"
            disabled={saveMutation.isPending || scopeQuery.isPending}
            onClick={() => saveMutation.mutate()}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {saveMutation.isPending ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Save />
            )}
            Salvar escopo
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
