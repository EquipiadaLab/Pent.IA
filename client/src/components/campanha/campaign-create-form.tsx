import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, Play, Shield } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "../ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { Input } from "../ui/input";
import { ApiErrorState } from "./api-error-state";

const campaignFormSchema = z.object({
  authorizedBy: z
    .string()
    .trim()
    .min(1, "Informe quem autorizou a campanha.")
    .max(120, "Use até 120 caracteres."),
});

export type CampaignFormValues = z.infer<typeof campaignFormSchema>;

interface CampaignCreateFormProps {
  /** Alvo travado no servidor (locked_target). O front não envia URL. */
  lockedTarget: string | null;
  isSubmitting: boolean;
  apiError: string;
  scopeError: string;
  onRetryScope: () => void;
  onSubmit: (values: CampaignFormValues) => void;
}

export function CampaignCreateForm({
  lockedTarget,
  isSubmitting,
  apiError,
  scopeError,
  onRetryScope,
  onSubmit,
}: CampaignCreateFormProps) {
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues: {
      authorizedBy: "",
    },
  });

  return (
    <Card
      id="campaign-create"
      className="mt-5 border-rose-500/25 bg-zinc-950/80"
    >
      <CardHeader className="border-b border-white/[0.07] pb-4">
        <div className="flex items-center gap-2">
          <div className="grid size-8 place-items-center rounded-lg bg-rose-500/10 text-rose-400">
            <Shield className="size-4" />
          </div>
          <div>
            <CardTitle className="text-sm text-zinc-100">
              Configurar campanha autorizada
            </CardTitle>
            <p className="mt-1 text-xs text-zinc-500">
              O alvo é travado no servidor. A tela não envia nenhuma URL.
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {scopeError && (
          <div className="mb-4">
            <ApiErrorState
              compact
              message={`Não foi possível carregar o escopo: ${scopeError}`}
              onRetry={onRetryScope}
            />
          </div>
        )}
        <form
          id="create-campaign-form"
          onSubmit={handleSubmit(onSubmit)}
          className="grid gap-4 sm:grid-cols-[1fr_1fr_auto]"
          noValidate
        >
          <label className="grid content-start gap-2 text-xs text-zinc-400">
            Alvo autorizado
            <div className="flex h-10 items-center gap-2 rounded-md border border-white/10 bg-zinc-900/60 px-3">
              <Lock className="size-3.5 shrink-0 text-emerald-400" />
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-zinc-200">
                {lockedTarget || "Definido pelo servidor"}
              </span>
            </div>
            <span className="text-[11px] text-zinc-600">
              Alvo travado (locked_target). Só este endereço é testado.
            </span>
          </label>
          <label className="grid content-start gap-2 text-xs text-zinc-400">
            Quem autorizou
            <Controller
              control={control}
              name="authorizedBy"
              render={({ field }) => (
                <Input
                  {...field}
                  placeholder="Organização / responsável"
                  autoComplete="organization"
                  aria-invalid={Boolean(errors.authorizedBy)}
                  className="h-10 border-white/10 bg-zinc-900 text-zinc-100 placeholder:text-zinc-600 aria-invalid:border-rose-500"
                  maxLength={120}
                />
              )}
            />
            {errors.authorizedBy && (
              <span className="text-[11px] text-rose-300">
                {errors.authorizedBy.message}
              </span>
            )}
          </label>
          <div className="grid content-start gap-2">
            <span className="text-xs text-transparent" aria-hidden="true">
              Ação
            </span>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="h-10 bg-rose-600 text-white hover:bg-rose-500"
            >
              <Play />
              {isSubmitting ? "Iniciando..." : "Iniciar campanha"}
            </Button>
            {apiError && (
              <span role="alert" className="text-[11px] text-rose-300">
                {apiError}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
