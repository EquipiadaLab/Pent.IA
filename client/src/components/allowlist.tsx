import { api, getApiErrorMessage } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import {
    AlertTriangle,
    CircleCheck,
    LoaderCircle,
    LockKeyhole,
    RefreshCw,
} from "lucide-react";
import { useEffect } from "react";
import type { Scope } from "./campanha/types";
import { DashboardHeader } from "./dashboard.header";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export default function Allowlist() {
    const scopeQuery = useQuery({
        queryKey: ["scope"],
        queryFn: async () => (await api.get<Scope>("/scope")).data,
    });

    useEffect(() => {
        const handleRefresh = () => void scopeQuery.refetch();
        window.addEventListener("scope:refresh", handleRefresh);
        return () => window.removeEventListener("scope:refresh", handleRefresh);
    }, [scopeQuery.refetch]);

    const scope = scopeQuery.data;
    const isLoading = scopeQuery.isPending;
    const isRefreshing = scopeQuery.isFetching;

    return (
        <main className="mx-auto w-full max-w-[1500px] pb-10">
            <DashboardHeader
                title="Escopo e allowlist"
                description="O agente só enxerga as origens autorizadas pela configuração do servidor."
                actions={
                    <Button
                        aria-label="Atualizar allowlist"
                        variant="outline"
                        size="icon-sm"
                        className="border-white/10 bg-white/[0.03] text-zinc-400 hover:bg-white/10 hover:text-white"
                        disabled={isRefreshing}
                        onClick={() => void scopeQuery.refetch()}
                    >
                        <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
                    </Button>
                }
            />

            {scopeQuery.isError && (
                <div
                    role="alert"
                    className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
                >
                    <span>{getApiErrorMessage(scopeQuery.error)}</span>
                    <Button
                        variant="outline"
                        size="sm"
                        className="border-rose-500/30 text-rose-200 hover:bg-rose-500/10"
                        onClick={() => void scopeQuery.refetch()}
                    >
                        Tentar novamente
                    </Button>
                </div>
            )}

            <div className="mt-5 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
                <Card className="border-white/10 bg-zinc-950/80">
                    <CardHeader className="border-b border-white/[0.07]">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-rose-500">
                                    <span className="size-1.5 rounded-full bg-rose-500" />
                                    Origens permitidas
                                </p>
                                <CardTitle className="mt-2 text-sm text-zinc-100">
                                    {scope?.authorized_targets.length ?? 0} origem(ns) autorizada(s)
                                </CardTitle>
                            </div>
                            <span className="rounded border border-emerald-500/20 bg-emerald-500/[0.08] px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                                Escopo ativo
                            </span>
                        </div>
                    </CardHeader>
                    <CardContent className="pt-2">
                        {isLoading ? (
                            <div className="flex min-h-28 items-center justify-center text-zinc-500">
                                <LoaderCircle className="size-5 animate-spin" />
                            </div>
                        ) : scope?.authorized_targets.length ? (
                            <ul className="divide-y divide-white/[0.07]">
                                {scope.authorized_targets.map((origin) => (
                                    <li
                                        key={origin}
                                        className="flex items-center gap-3 py-3"
                                    >
                                        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                                            <CircleCheck className="size-4" />
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <p className="break-all text-sm text-zinc-200">
                                                {origin}
                                            </p>
                                            <p className="mt-1 text-[10px] uppercase tracking-wider text-zinc-500">
                                                Origem autorizada
                                            </p>
                                        </div>
                                        <span className="rounded border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                                            ALLOW
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div className="flex min-h-28 flex-col items-center justify-center gap-2 text-center">
                                <LockKeyhole className="size-5 text-zinc-500" />
                                <p className="text-sm text-zinc-400">
                                    Nenhuma origem externa configurada.
                                </p>
                                <p className="text-xs text-zinc-600">
                                    O servidor continua restrito ao ambiente local.
                                </p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <div className="flex flex-col gap-4">
                    <Card className="border-rose-500/15 bg-rose-500/[0.035]">
                        <CardHeader className="flex flex-row items-start gap-3">
                            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-400" />
                            <div>
                                <CardTitle className="text-sm text-zinc-100">
                                    Fora do escopo
                                </CardTitle>
                                <p className="mt-1 text-xs leading-relaxed text-zinc-500">
                                    Destinos não autorizados são bloqueados pelo servidor.
                                    Esta tela é somente leitura; a lista é carregada do
                                    endpoint /scope.
                                </p>
                            </div>
                        </CardHeader>
                        <CardContent className="pt-0">
                            <div className="flex items-center justify-between border-t border-white/[0.07] pt-3 text-xs">
                                <span className="text-zinc-500">Métodos permitidos</span>
                                <span className="font-mono text-zinc-300">
                                    {scope?.allowed_methods.join(" · ") || "—"}
                                </span>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </main>
    );
}
