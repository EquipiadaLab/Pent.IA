import { Select as SelectPrimitive } from "@base-ui/react/select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "cn";

function Select(props: SelectPrimitive.Root.Props<string>) {
  return <SelectPrimitive.Root data-slot="select" {...props} />;
}

function SelectTrigger({
  className,
  children,
  ...props
}: SelectPrimitive.Trigger.Props) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        "flex h-10 w-full items-center justify-between gap-2 rounded-xl border border-white/10 bg-zinc-900 px-3 text-left text-sm text-zinc-100 outline-none transition-colors focus-visible:border-rose-500/60 focus-visible:ring-2 focus-visible:ring-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-rose-500",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon>
        <ChevronDown className="size-4 text-zinc-500" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectValue(props: SelectPrimitive.Value.Props) {
  return <SelectPrimitive.Value data-slot="select-value" {...props} />;
}

function SelectContent({
  className,
  children,
  ...props
}: SelectPrimitive.Popup.Props) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner sideOffset={4} className="z-50">
        <SelectPrimitive.Popup
          data-slot="select-content"
          className={cn(
            "max-h-(--available-height) min-w-(--anchor-width) overflow-y-auto rounded-xl border border-white/10 bg-zinc-900 p-1 text-zinc-100 shadow-xl outline-none",
            className,
          )}
          {...props}
        >
          <SelectPrimitive.List>{children}</SelectPrimitive.List>
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  );
}

function SelectItem({
  className,
  children,
  ...props
}: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex min-h-9 cursor-default items-center rounded-lg py-1.5 pr-8 pl-2 text-sm outline-none data-highlighted:bg-white/[0.08] data-disabled:pointer-events-none data-disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-2 inline-flex items-center">
        <Check className="size-4" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue };
