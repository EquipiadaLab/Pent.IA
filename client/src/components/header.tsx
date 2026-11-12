import { Play, RefreshCcw, Settings2, Square } from "lucide-react";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "./ui/breadcrumb";

import { useAgentStore } from "@/stores/agent.store";
import { useUrlStore } from "@/stores/url.store";
import { Button } from "./ui/button";

export default function AppHeader() {
    const pageName = useUrlStore((state) => state.pageName);
    const agentIsRunning = useAgentStore((state) => state.isRunning);
    const setIsRunning = useAgentStore((s) => s.setIsRunning);

    return (
        <header className="shrink-0 w-full border-b border-accent h-24 flex items-center justify-between">
            <div className="flex items-center gap-2 px-4">
                <Breadcrumb>
                    <BreadcrumbList>
                        <BreadcrumbItem className="hidden md:block">
                            <BreadcrumbLink className="tracking-widest" render={<a href="#" />}>
                                PENTE.IA
                            </BreadcrumbLink>
                        </BreadcrumbItem>
                        <BreadcrumbSeparator className="hidden md:block" />
                        <BreadcrumbItem>
                            <BreadcrumbPage className="uppercase tracking-widest">
                                {pageName}
                            </BreadcrumbPage>
                        </BreadcrumbItem>
                    </BreadcrumbList>
                </Breadcrumb>
            </div>
            <div className="flex gap-2">
                <Button variant="outline" size="icon-lg"><RefreshCcw /></Button>
                <Button variant="outline" size="icon-lg"><Settings2 /></Button>
                <Button className={!agentIsRunning ? "bg-green-800/50 hover:bg-green-800/70" : ""} onClick={() => setIsRunning(!agentIsRunning)} variant={agentIsRunning ? "destructive" : "default"} size="lg">{agentIsRunning ? <><Square /> Parar agente</> : <><Play /> Iniciar agente</>}</Button>
            </div>
        </header>
    );
}