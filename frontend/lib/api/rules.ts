import { apiClient } from "@/lib/api/client";

export interface RulesResponse {
  rules: Record<string, unknown>[];
}

export interface VpnTunnelsResponse {
  vpn_tunnels: Record<string, unknown>[];
}

export async function getFirewallRules(firewallId: string): Promise<RulesResponse> {
  const { data } = await apiClient.get<RulesResponse>(`/v1/firewalls/${firewallId}/rules`);
  return data;
}

export async function getFirewallVpnTunnels(firewallId: string): Promise<VpnTunnelsResponse> {
  const { data } = await apiClient.get<VpnTunnelsResponse>(
    `/v1/firewalls/${firewallId}/vpn-tunnels`
  );
  return data;
}
