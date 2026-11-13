import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { Activity, FileSearchCorner, History, KeyRound, LayoutDashboard, Shield, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "./ui/sidebar";

import { useUrlStore } from "@/stores/url.store";

interface ApiHealth {
    status: "ok" | "degraded";
    version: string;
}

const items = [
    {
        title: "Campanha",
        url: "#",
        icon: LayoutDashboard
    },
    {
        title: "Achados",
        url: "#achados",
        icon: FileSearchCorner
    },
    {
        title: "Regras de segurança",
        url: "#regras",
        icon: ShieldCheck
    },
    {
        title: "Allowlist",
        url: "#allowlist",
        icon: KeyRound
    },
    {
        title: "Auditoria",
        url: "#auditoria",
        icon: History
    },
];

export default function AppSidebar() {
    const [hashValue, setHashValue] = useState(window.location.hash);
    const setCurrentUrl = useUrlStore((state) => state.setCurrentUrl);
    const apiHealthQuery = useQuery({
        queryKey: ["api-health"],
        queryFn: async () => (await api.get<ApiHealth>("/status")).data,
        refetchInterval: 30_000,
    });

    const apiStatus = apiHealthQuery.isError
        ? apiHealthQuery.data
            ? "Falha ao atualizar"
            : "Sem conexão"
        : apiHealthQuery.data?.status === "degraded"
            ? "Degradada"
            : apiHealthQuery.data
                ? "Operacional"
                : "Verificando...";
    const apiStatusColor = apiHealthQuery.isError
        ? apiHealthQuery.data
            ? "bg-amber-400"
            : "bg-rose-400"
        : apiHealthQuery.data?.status === "degraded"
            ? "bg-amber-400"
            : apiHealthQuery.data
                ? "bg-emerald-400"
                : "bg-zinc-500";

    useEffect(() => {
        setCurrentUrl(window.location.hash, items.find(item => item.url === window.location.hash)?.title || "Campanha");
    }, [setCurrentUrl]);

    useEffect(() => {
        // Função para atualizar o hash se ele mudar na navegação
        const handleHashChange = () => {
            setHashValue(window.location.hash);
            setCurrentUrl(window.location.hash, items.find(item => item.url === window.location.hash)?.title || "Campanha");
        };

        window.addEventListener('hashchange', handleHashChange);

        return () => {
            window.removeEventListener('hashchange', handleHashChange);
        };
    }, [setCurrentUrl]);

    return (
        <Sidebar>
            <SidebarHeader className="bg-background">
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton
                            className="data-[slot=sidebar-menu-button]:p-1.5! hover:bg-background active:bg-background"
                            render={
                                <a href="#">
                                    <Shield className="size-5! text-rose-600" />
                                    <div className="flex-col flex">
                                        <span className="text-base font-semibold tracking-[0.16rem]">PENT.<span className="text-rose-600">IA</span></span>
                                        <span className="tracking-[0.16rem] text-chart-2 text-[8px]">PENTE FINO NO SISTEMA</span>
                                    </div>
                                </a>
                            }
                        >
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>
            <SidebarContent className="bg-background">
                <SidebarGroup>
                    <SidebarGroupLabel className="tracking-widest">WORKSPACE</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {items.map((item) => {
                                const isActive = hashValue === "" ? item.url === "#" : hashValue === item.url;
                                return (
                                    <SidebarMenuItem key={item.title}>
                                        <SidebarMenuButton className="group border-l-2 border-l-transparent data-active:border-l-rose-600 data-active:shadow-[inset_3px_0_8px_-4px_rgba(244,63,94,0.8),0_0_10px_rgba(244,63,94,0.25)] data-active:bg-rose-400/10 data-active:hover:bg-rose-400/10 transition hover:bg-muted/50" isActive={isActive} tooltip={item.title} render={
                                            <a href={item.url}>
                                                {item.icon && <item.icon className="text-chart-2 group-data-active:text-white" />}
                                                <span className="text-xs text-chart-2 group-data-active:text-white">{item.title}</span>
                                            </a>
                                        }>
                                        </SidebarMenuButton>
                                    </SidebarMenuItem>
                                )
                            })}
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>
            </SidebarContent>
            <SidebarFooter className="border-t border-white/[0.07] bg-background p-3 group-data-[collapsible=icon]:p-1">
                <div
                    title={`Status da API: ${apiStatus}`}
                    className="relative overflow-hidden rounded-xl border border-rose-500/15 bg-gradient-to-br from-rose-500/[0.08] via-zinc-900/80 to-zinc-950 p-3 group-data-[collapsible=icon]:border-transparent group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:p-0"
                >
                    <div className="flex items-start gap-3 group-data-[collapsible=icon]:justify-center">
                        <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-rose-400/20 bg-rose-500/10 text-rose-300">
                            <Activity className="size-4" />
                        </span>
                        <div className="min-w-0 group-data-[collapsible=icon]:hidden">
                            <p className="text-xs font-semibold text-zinc-100">
                                Saúde da API
                            </p>
                            <div className="mt-2 flex items-center gap-2">
                                <span className={`size-1.5 shrink-0 rounded-full ${apiStatusColor}`} />
                                <span className="truncate text-[11px] text-zinc-300">
                                    {apiStatus}
                                </span>
                            </div>
                            <div className="mt-3 flex items-center justify-between gap-2 border-t border-white/[0.07] pt-2">
                                <span className="text-[9px] uppercase tracking-[0.14em] text-zinc-600">
                                    Atualiza a cada 30 s
                                </span>
                                {apiHealthQuery.data && (
                                    <span className="font-mono text-[9px] text-zinc-600">
                                        v{apiHealthQuery.data.version}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </SidebarFooter>
        </Sidebar>
    );
}