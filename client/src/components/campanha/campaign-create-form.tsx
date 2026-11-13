import { Lock, Play, Shield } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";

import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ApiErrorState } from "./api-error-state";

const campaignFormSchema = z.object({
  authorizedBy: z
    .string()
    .trim()
    .min(1, "Informe quem autorizou a campanha.")
    .max(120, "Use até 120 caracteres."),
  moveLimit: z
    .number()
    .int("Use um número inteiro.")
    .min(3, "Mínimo de 3 lances.")
    .max(25, "Máximo de 25 lances.")
    .optional(),
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
      moveLimit: undefined,
    },
  });

  return (
    <Card
      id="campaign-create"
      className="border-primary/25 bg-card/50 backdrop-blur-sm"
    >
      <CardHeader className="border-b border-border/50 pb-4">
        <div className="flex items-center gap-2">
          <div className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
            <Shield className="size-4" />
          </div>
          <div>
            <CardTitle className="text-sm text-foreground">
              Configurar campanha autorizada
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
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
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_0.7fr_auto]"
          noValidate
        >
          <label className="grid content-start gap-2 text-xs text-muted-foreground">
            Alvo autorizado
            <div className="flex h-10 items-center gap-2 rounded-md border border-border/60 bg-background/50 px-3">
              <Lock className="size-3.5 shrink-0 text-emerald-400" />
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground/90">
                {lockedTarget || "Definido pelo servidor"}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground/70">
              Alvo travado (locked_target). Só este endereço é testado.
            </span>
          </label>
          <label className="grid content-start gap-2 text-xs text-muted-foreground">
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
                  className="h-10 border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground/60 aria-invalid:border-rose-500"
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
          <label className="grid content-start gap-2 text-xs text-muted-foreground">
            Número de lances
            <Controller
              control={control}
              name="moveLimit"
              render={({ field }) => (
                <Input
                  type="number"
                  min={8}
                  max={25}
                  inputMode="numeric"
                  placeholder="8 a 25"
                  value={field.value ?? "25"}
                  onChange={(event) =>
                    field.onChange(
                      event.target.value === ""
                        ? undefined
                        : event.target.valueAsNumber,
                    )
                  }
                  onBlur={field.onBlur}
                  name={field.name}
                  ref={field.ref}
                  aria-invalid={Boolean(errors.moveLimit)}
                  className="h-10 border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground/60 aria-invalid:border-rose-500"
                />
              )}
            />
            <span className="text-[11px] text-muted-foreground/70">
              Alvo de 8 a 25. A campanha é encerrada ao atingi-lo.
            </span>
            {errors.moveLimit && (
              <span className="text-[11px] text-rose-300">
                {errors.moveLimit.message}
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
              className="h-10 bg-primary text-primary-foreground hover:bg-primary/90"
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
