import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from "./ui/breadcrumb";

import { useUrlStore } from "@/stores/url.store";

export default function AppHeader() {
    const pageName = useUrlStore((state) => state.pageName);

    return (
        <header className="flex h-14 w-full shrink-0 items-center border-b border-white/[0.07]">
            <div className="flex items-center gap-2 px-1">
                <Breadcrumb>
                    <BreadcrumbList>
                        <BreadcrumbItem className="hidden md:block">
                            <BreadcrumbLink
                                className="tracking-widest text-zinc-400 hover:text-zinc-200"
                                render={<a href="#" />}
                            >
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
        </header>
    );
}
