import { Compass } from "lucide-react";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";

export default function NotFound({ url }: { url: string }) {
    return (
        <main className="mx-auto w-full max-w-[1500px] pb-10">
            <Card className="mt-5 border-white/10 bg-zinc-950/80">
                <CardContent className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
                    <span className="grid size-12 place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-zinc-400">
                        <Compass className="size-6" />
                    </span>
                    <div className="space-y-1">
                        <p className="text-sm font-semibold text-zinc-100">
                            Página não encontrada
                        </p>
                        <p className="text-xs text-zinc-500">
                            A rota{" "}
                            <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-zinc-300">
                                {url || "/"}
                            </code>{" "}
                            não existe ou ainda não está disponível.
                        </p>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        className="border-white/10 bg-white/[0.03] text-zinc-300 hover:bg-white/10 hover:text-white"
                        onClick={() => {
                            window.location.hash = "";
                        }}
                    >
                        Voltar para a campanha
                    </Button>
                </CardContent>
            </Card>
        </main>
    );
}
