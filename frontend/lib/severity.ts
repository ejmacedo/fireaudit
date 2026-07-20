/** Severity ordering shared by the dashboard and firewall detail screens.
 * Critical-first, per fase6-7-ux-ui.md §3.3 ("dashboard ordenado por urgência"). */
export const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

export type Severity = (typeof SEVERITY_ORDER)[number];

export function severityRank(severity: string): number {
  const index = SEVERITY_ORDER.indexOf(severity as Severity);
  return index === -1 ? SEVERITY_ORDER.length : index;
}
