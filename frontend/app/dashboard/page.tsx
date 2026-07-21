"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Shield } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listFirewalls, createFirewall, type Firewall } from "@/lib/api/firewalls";
import { getSubscription } from "@/lib/api/subscription";
import { SEVERITY_ORDER, severityRank, type Severity } from "@/lib/severity";
import { statusDotColor, statusLabel, formatLastSeen } from "@/lib/firewall-status";
import { UpgradeTeaser } from "@/components/upgrade-teaser";

function sortFirewalls(firewalls: Firewall[]): Firewall[] {
  return [...firewalls].sort((a, b) => {
    const aRank = Math.min(
      ...SEVERITY_ORDER.filter((sev) => a.open_findings_by_severity[sev] > 0).map(severityRank),
      SEVERITY_ORDER.length
    );
    const bRank = Math.min(
      ...SEVERITY_ORDER.filter((sev) => b.open_findings_by_severity[sev] > 0).map(severityRank),
      SEVERITY_ORDER.length
    );
    if (aRank !== bRank) return aRank - bRank;

    const aTime = a.last_seen_at ? new Date(a.last_seen_at).getTime() : 0;
    const bTime = b.last_seen_at ? new Date(b.last_seen_at).getTime() : 0;
    return bTime - aTime;
  });
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["firewalls"],
    queryFn: listFirewalls,
  });
  const { data: subscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: getSubscription,
  });

  useEffect(() => {
    const checkout = searchParams.get("checkout");
    if (checkout === "success") {
      toast.success("Welcome to Pro! Your account has been upgraded.");
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
      queryClient.invalidateQueries({ queryKey: ["firewalls"] });
      router.replace("/dashboard");
    } else if (checkout === "cancel") {
      toast.info("Checkout canceled — you can upgrade any time.");
      router.replace("/dashboard");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newFirewallName, setNewFirewallName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createdToken, setCreatedToken] = useState<string | null>(null);

  const firewalls = useMemo(() => data?.firewalls ?? [], [data]);
  const sortedFirewalls = useMemo(() => sortFirewalls(firewalls), [firewalls]);

  const totals = useMemo(() => {
    return firewalls.reduce(
      (acc, fw) => {
        acc.critical += fw.open_findings_by_severity.critical;
        acc.certExpiring += fw.open_findings_by_severity.high;
        return acc;
      },
      { critical: 0, certExpiring: 0 }
    );
  }, [firewalls]);

  async function handleCreateFirewall() {
    if (!newFirewallName.trim()) return;
    setIsCreating(true);
    try {
      const result = await createFirewall(newFirewallName.trim());
      setCreatedToken(result.agent_token);
      queryClient.invalidateQueries({ queryKey: ["firewalls"] });
    } catch {
      toast.error("Could not create firewall. Please try again.");
    } finally {
      setIsCreating(false);
    }
  }

  function closeDialog() {
    setDialogOpen(false);
    setNewFirewallName("");
    setCreatedToken(null);
  }

  async function copyToken() {
    if (!createdToken) return;
    await navigator.clipboard.writeText(createdToken);
    toast.success("Token copied to clipboard.");
  }

  return (
    <main className="min-h-screen bg-background p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Your firewalls</h1>
          <p className="text-sm text-muted-foreground">
            {firewalls.length > 0
              ? `${firewalls.length} firewall${firewalls.length === 1 ? "" : "s"} monitored`
              : "Continuous compliance overview"}
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>+ Add firewall</Button>
      </div>

      {subscription?.tier === "free" && (
        <UpgradeTeaser
          totalOpenFindings={totals.critical + totals.certExpiring}
          criticalCount={totals.critical}
          highCount={totals.certExpiring}
        />
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
          <Skeleton className="h-64" />
        </div>
      )}

      {isError && !isLoading && (
        <Alert variant="destructive">
          <AlertTitle>Could not load firewalls</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>Something went wrong while fetching your firewalls.</span>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {!isLoading && !isError && firewalls.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary">
              <Shield className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <p className="font-semibold">Add your first firewall</p>
              <p className="text-sm text-muted-foreground">
                Register a pfSense firewall to start continuous compliance monitoring.
              </p>
            </div>
            <Button onClick={() => setDialogOpen(true)}>+ Add firewall</Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && firewalls.length > 0 && (
        <>
          <div className="mb-6 grid grid-cols-3 gap-4">
            <Card>
              <CardHeader className="p-4 pb-0">
                <p className="text-xs text-muted-foreground">Firewalls monitored</p>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold">{firewalls.length}</p>
              </CardContent>
            </Card>
            <Card className="border-red-200">
              <CardHeader className="p-4 pb-0">
                <p className="text-xs text-muted-foreground">Critical findings</p>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold text-red-600">{totals.critical}</p>
              </CardContent>
            </Card>
            <Card className="border-orange-200">
              <CardHeader className="p-4 pb-0">
                <p className="text-xs text-muted-foreground">High-severity findings</p>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold text-orange-600">{totals.certExpiring}</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Last check-in</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedFirewalls.map((fw) => (
                  <TableRow key={fw.id}>
                    <TableCell className="font-medium">{fw.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {fw.pfsense_version ?? "—"}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className={`h-2 w-2 rounded-full ${statusDotColor(fw.status)}`}
                        />
                        {statusLabel(fw.status)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {SEVERITY_ORDER.filter(
                        (sev) => fw.open_findings_by_severity[sev] > 0
                      ).length === 0 ? (
                        <Badge variant="low">No findings</Badge>
                      ) : (
                        <div className="flex gap-1">
                          {SEVERITY_ORDER.filter(
                            (sev) => fw.open_findings_by_severity[sev] > 0
                          ).map((sev: Severity) => (
                            <Badge key={sev} variant={sev}>
                              {fw.open_findings_by_severity[sev]} {sev}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatLastSeen(fw.last_seen_at)}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/dashboard/firewalls/${fw.id}`}
                        className="text-primary hover:underline"
                      >
                        View details →
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent>
          {!createdToken ? (
            <>
              <DialogHeader>
                <DialogTitle>Add firewall</DialogTitle>
                <DialogDescription>
                  Give your firewall a name. You&apos;ll get an agent token to configure on your
                  pfSense agent next.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2">
                <Label htmlFor="firewall-name">Name</Label>
                <Input
                  id="firewall-name"
                  value={newFirewallName}
                  onChange={(e) => setNewFirewallName(e.target.value)}
                  placeholder="e.g. HQ-Main"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={closeDialog}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateFirewall}
                  disabled={isCreating || !newFirewallName.trim()}
                >
                  {isCreating ? "Creating..." : "Create"}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Firewall created</DialogTitle>
                <DialogDescription>
                  Copy this agent token now — it will not be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-center gap-2">
                <Input readOnly value={createdToken} className="font-mono text-xs" />
                <Button variant="outline" onClick={copyToken}>
                  Copy
                </Button>
              </div>
              <DialogFooter>
                <Button onClick={closeDialog}>Done</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </main>
  );
}
