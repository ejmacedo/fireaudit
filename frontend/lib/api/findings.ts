import { apiClient } from "@/lib/api/client";

export interface Finding {
  id: string;
  firewall_id: string;
  check_type: string;
  severity: string;
  status: string;
  details: Record<string, unknown>;
  created_at: string | null;
  resolved_at: string | null;
}

export interface ListFindingsResponse {
  findings: Finding[];
}

export interface ListFindingsParams {
  status?: string;
  severity?: string;
  check_type?: string;
}

export async function listFindings(
  firewallId: string,
  params?: ListFindingsParams
): Promise<ListFindingsResponse> {
  const { data } = await apiClient.get<ListFindingsResponse>(
    `/v1/firewalls/${firewallId}/findings`,
    { params }
  );
  return data;
}

export async function resolveFinding(firewallId: string, findingId: string): Promise<Finding> {
  const { data } = await apiClient.patch<Finding>(
    `/v1/firewalls/${firewallId}/findings/${findingId}`,
    { status: "resolved" }
  );
  return data;
}
