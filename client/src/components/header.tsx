import { Play, RefreshCcw } from "lucide-react";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "./ui/breadcrumb";

import { useUrlStore } from "@/stores/url.store";
import { Button } from "./ui/button";

const CAMPAIGN_ROUTES = ["", "#", "#campanha"];

export default function AppHeader() {
    const pageName = useUrlStore((state) => state.pageName);
    const currentUrl = useUrlStore((state) => state.currentUrl);
    const isCampaign = CAMPAIGN_ROUTES.includes(currentUrl);

    return (
        <header className="flex h-16 w-full shrink-0 items-center justify-between border-b border-white/[0.07]">
            <div className="flex items-center gap-2 px-4">
                <Breadcrumb>
                    <BreadcrumbList>
                        <BreadcrumbItem className="hidden md:block">
                            <BreadcrumbLink className="tracking-widest" render={<a href="#" />}>
                                PENT.IA
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
            <div className="flex gap-2 pr-1">
                <Button
                    variant="outline"
                    size="icon-sm"
                    aria-label="Atualizar campanhas"
                    className="border-white/10 bg-white/[0.03] text-zinc-400 hover:bg-white/10 hover:text-white"
                    onClick={() =>
                        window.dispatchEvent(
                            new Event(isCampaign ? "campaign:refresh" : "scope:refresh"),
                        )
                    }
                >
                    <RefreshCcw />
                </Button>
                {isCampaign && (
                    <Button
                        size="sm"
                        className="bg-rose-600 text-white hover:bg-rose-500"
                        onClick={() => {
                            window.dispatchEvent(new Event("campaign:create"));
                            window.setTimeout(
                                () =>
                                    document
                                        .getElementById("campaign-create")
                                        ?.scrollIntoView({ behavior: "smooth", block: "center" }),
                                0,
                            );
                        }}
                    >
                        <Play />
                        Nova campanha
                    </Button>
                )}
            </div>
        </header>
    );
}