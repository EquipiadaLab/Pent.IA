import { FileSearchCorner, History, KeyRound, LayoutDashboard, Shield, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "./ui/sidebar";

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

    useEffect(() => {
        // Função para atualizar o hash se ele mudar na navegação
        const handleHashChange = () => {
            setHashValue(window.location.hash);
        };

        window.addEventListener('hashchange', handleHashChange);

        return () => {
            window.removeEventListener('hashchange', handleHashChange);
        };
    }, []);

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
        </Sidebar>
    );
}