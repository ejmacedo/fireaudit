import { apiClient } from "@/lib/api/client";

export interface OpenFindingsBySeverity {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface Firewall {
  id: string;
  organization_id: string;
  name: string;
  status: string;
  pfsense_version: string | null;
  last_seen_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  open_findings_by_severity: OpenFindingsBySeverity;
}

export interface ListFirewallsResponse {
  firewalls: Firewall[];
  next_cursor: string | null;
}

export async function listFirewalls(): Promise<ListFirewallsResponse> {
  const { data } = await apiClient.get<ListFirewallsResponse>("/v1/firewalls");
  return data;
}

export async function getFirewall(id: string): Promise<Firewall> {
  const { data } = await apiClient.get<Firewall>(`/v1/firewalls/${id}`);
  return data;
}

export interface CreateFirewallResponse {
  firewall: Firewall;
  agent_token: string;
}

export async function createFirewall(name: string): Promise<CreateFirewallResponse> {
  const { data } = await apiClient.post<CreateFirewallResponse>("/v1/firewalls", { name });
  return data;
}

export async function renameFirewall(id: string, name: string): Promise<Firewall> {
  const { data } = await apiClient.patch<Firewall>(`/v1/firewalls/${id}`, { name });
  return data;
}

export async function deleteFirewall(id: string): Promise<void> {
  await apiClient.delete(`/v1/firewalls/${id}`);
}

export interface RotateTokenResponse {
  agent_token: string;
}

export async function rotateToken(id: string): Promise<RotateTokenResponse> {
  const { data } = await apiClient.post<RotateTokenResponse>(`/v1/firewalls/${id}/rotate-token`);
  return data;
}
