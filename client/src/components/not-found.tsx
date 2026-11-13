import { motion } from "motion/react";
import { Compass } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export default function NotFound({ url }: { url: string }) {
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Card className="border-border/60 bg-card/40">
                <CardContent className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
                    <motion.span
                        animate={{ rotate: [0, 12, -12, 0] }}
                        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                        className="grid size-14 place-items-center rounded-2xl border border-primary/25 bg-primary/10 text-primary"
                    >
                        <Compass className="size-7" />
                    </motion.span>
                    <div className="space-y-1">
                        <p className="text-base font-semibold text-foreground">
                            Página não encontrada
                        </p>
                        <p className="text-xs text-muted-foreground">
                            A rota{" "}
                            <code className="rounded bg-muted/40 px-1.5 py-0.5 font-mono text-foreground/80">
                                {url || "/"}
                            </code>{" "}
                            não existe ou ainda não está disponível.
                        </p>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        className="rounded-xl border-border/60 bg-card/50"
                        onClick={() => {
                            window.location.hash = "";
                        }}
                    >
                        Voltar para a campanha
                    </Button>
                </CardContent>
            </Card>
        </motion.div>
    );
}
