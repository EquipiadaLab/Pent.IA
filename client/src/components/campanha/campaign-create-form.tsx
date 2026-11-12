import { zodResolver } from "@hookform/resolvers/zod";
import { Play, Shield } from "lucide-react";
import { useEffect, useMemo } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { ApiErrorState } from "./api-error-state";

function createCampaignFormSchema(targets: string[]) {
  return z.object({
    origin: z
      .string()
      .url("Informe uma URL válida.")
      .refine(
        (origin) => targets.includes(origin),
        "Selecione uma origem presente na allowlist.",
      ),
    authorizedBy: z
      .string()
      .trim()
      .min(1, "Informe quem autorizou a campanha.")
      .max(120, "Use até 120 caracteres."),
  });
}

export type CampaignFormValues = z.infer<
  ReturnType<typeof createCampaignFormSchema>
>;

interface CampaignCreateFormProps {
  targets: string[];
  defaultOrigin: string;
  isSubmitting: boolean;
  apiError: string;
  scopeError: string;
  onRetryScope: () => void;
  onSubmit: (values: CampaignFormValues) => void;
}

export function CampaignCreateForm({
  targets,
  defaultOrigin,
  isSubmitting,
  apiError,
  scopeError,
  onRetryScope,
  onSubmit,
}: CampaignCreateFormProps) {
  const campaignFormSchema = useMemo(
    () => createCampaignFormSchema(targets),
    [targets],
  );
  const {
    control,
    handleSubmit,
    getFieldState,
    setValue,
    formState: { errors },
  } = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues: {
      origin: defaultOrigin,
      authorizedBy: "",
    },
  });

  useEffect(() => {
    if (!getFieldState("origin").isDirty) {
      setValue("origin", defaultOrigin);
    }
  }, [defaultOrigin, getFieldState, setValue]);

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
              Os alvos disponíveis vêm da allowlist retornada pelo servidor.
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
            Site autorizado
            <Controller
              control={control}
              name="origin"
              render={({ field }) => (
                <Select
                  name={field.name}
                  value={field.value || null}
                  onValueChange={(value) => field.onChange(value ?? "")}
                >
                  <SelectTrigger
                    ref={field.ref}
                    onBlur={field.onBlur}
                    aria-invalid={Boolean(errors.origin)}
                  >
                    <SelectValue placeholder="Selecione um alvo" />
                  </SelectTrigger>
                  <SelectContent>
                    {targets.map((target) => (
                      <SelectItem key={target} value={target}>
                        {target}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.origin ? (
              <span className="text-[11px] text-rose-300">
                {errors.origin.message}
              </span>
            ) : (
              <span className="text-[11px] text-zinc-600">
                Apenas origens listadas em authorized_targets podem ser selecionadas.
              </span>
            )}
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
