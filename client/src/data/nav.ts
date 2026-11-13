import {
  History,
  KeyRound,
  LayoutDashboard,
  ScanSearch,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  hash: string;
  label: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  {
    hash: "#",
    label: "Campanha",
    title: "Campanha ao vivo",
    description: "Acompanhe os agentes jogando o pentest, lance a lance.",
    icon: LayoutDashboard,
  },
  {
    hash: "#achados",
    label: "Achados",
    title: "Achados validados",
    description: "Cada risco com evidência, confiança e próximo movimento.",
    icon: ScanSearch,
  },
  {
    hash: "#regras",
    label: "Regras",
    title: "Regras de engajamento",
    description: "Políticas impostas pelo servidor — a tela não as afrouxa.",
    icon: ShieldCheck,
  },
  {
    hash: "#allowlist",
    label: "Escopo",
    title: "Escopo e allowlist",
    description: "O alvo autorizado e os limites de execução.",
    icon: KeyRound,
  },
  {
    hash: "#auditoria",
    label: "Auditoria",
    title: "Trilha de auditoria",
    description: "Tudo que aconteceu, em ordem cronológica e imutável.",
    icon: History,
  },
];

export function normalizeHash(hash: string): string {
  if (!hash || hash === "#" || hash === "") return "#";
  return hash;
}

export function navItemForHash(hash: string): NavItem {
  const normalized = normalizeHash(hash);
  return NAV_ITEMS.find((item) => item.hash === normalized) ?? NAV_ITEMS[0];
}
