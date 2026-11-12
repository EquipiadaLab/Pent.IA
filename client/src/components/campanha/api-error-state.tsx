import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "../ui/button";

interface ApiErrorStateProps {
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}

export function ApiErrorState({
  message,
  onRetry,
  compact = false,
}: ApiErrorStateProps) {
  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/[0.07] text-rose-200 ${
        compact ? "p-2 text-xs" : "p-3 text-sm"
      }`}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <p className="min-w-0 flex-1">{message}</p>
      {onRetry && (
        <Button
          variant="ghost"
          size="xs"
          onClick={onRetry}
          className="h-6 shrink-0 px-2 text-rose-200 hover:bg-rose-500/10 hover:text-white"
        >
          <RefreshCw />
          Tentar novamente
        </Button>
      )}
    </div>
  );
}
