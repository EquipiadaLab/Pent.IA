import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ACTIVE_STATES } from "@/components/campanha/helpers";
import type { Campaign } from "@/components/campanha/types";

/** Lista de campanhas, mais recente primeiro. */
export function useCampaignsList() {
  return useQuery({
    queryKey: ["campaigns"],
    queryFn: async () => {
      const { data } = await api.get<Campaign[]>("/campaigns");
      return [...data].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    },
    refetchInterval: 5000,
  });
}

/** Id da campanha ativa (ou a mais recente) de uma lista. */
export function primaryCampaignId(campaigns: Campaign[]): string {
  return (
    campaigns.find((item) => ACTIVE_STATES.includes(item.state))?.id ||
    campaigns[0]?.id ||
    ""
  );
}

/** Uma campanha específica, com polling enquanto estiver ativa. */
export function useCampaign(id: string, livePolling = true) {
  return useQuery({
    queryKey: ["campaign", id],
    queryFn: async () =>
      (await api.get<Campaign>(`/campaigns/${encodeURIComponent(id)}`)).data,
    enabled: Boolean(id),
    refetchInterval: (query) =>
      livePolling &&
      query.state.data &&
      ACTIVE_STATES.includes(query.state.data.state)
        ? 2500
        : false,
  });
}
