"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, AlertTriangle } from "lucide-react";

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

import {
  getFirewall,
  renameFirewall,
  deleteFirewall,
  rotateToken,
} from "@/lib/api/firewalls";
import { listFindings, resolveFinding, type Finding } from "@/lib/api/findings";
import { getFirewallRules, getFirewallVpnTunnels } from "@/lib/api/rules";
import { SEVERITY_ORDER, type Severity } from "@/lib/severity";
import { statusDotColor, statusLabel, formatLastSeen } from "@/lib/firewall-status";

function FindingDetails({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details);
  if (entries.length === 0) return null;
  return (
    <dl className="mt-2 space-y-1 text-sm text-muted-foreground">
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-2">
          <dt className="font-medium">{key}:</dt>
          <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function OverviewTab({ firewallId }: { firewallId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["firewall", firewallId],
    queryFn: () => getFirewall(firewallId),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load firewall details</AlertTitle>
        <AlertDescription>Something went wrong while fetching this firewall.</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardContent className="grid grid-cols-2 gap-6 p-6">
        <div>
          <p className="text-xs text-muted-foreground">Name</p>
          <p className="font-medium">{data.name}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">pfSense version</p>
          <p className="font-medium">{data.pfsense_version ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Status</p>
          <p className="inline-flex items-center gap-1.5 font-medium">
            <span className={`h-2 w-2 rounded-full ${statusDotColor(data.status)}`} />
            {statusLabel(data.status)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Last check-in</p>
          <p className="font-medium">{formatLastSeen(data.last_seen_at)}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function FindingsTab({ firewallId }: { firewallId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["findings", firewallId],
    queryFn: () => listFindings(firewallId, { status: "open" }),
  });
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const findings = data?.findings ?? [];
    const map = new Map<Severity, Finding[]>();
    for (const sev of SEVERITY_ORDER) map.set(sev, []);
    for (const finding of findings) {
      const key = finding.severity as Severity;
      const list = map.get(key) ?? [];
      list.push(finding);
      map.set(key, list);
    }
    return map;
  }, [data]);

  async function handleResolve(findingId: string) {
    setResolvingId(findingId);
    try {
      await resolveFinding(firewallId, findingId);
      queryClient.invalidateQueries({ queryKey: ["findings", firewallId] });
      toast.success("Finding marked as resolved.");
    } catch {
      toast.error("Could not resolve finding. Please try again.");
    } finally {
      setResolvingId(null);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load findings</AlertTitle>
        <AlertDescription>Something went wrong while fetching findings.</AlertDescription>
      </Alert>
    );
  }

  const totalFindings = data?.findings.length ?? 0;

  if (totalFindings === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No open findings for this firewall.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {SEVERITY_ORDER.map((sev) => {
        const findings = grouped.get(sev) ?? [];
        if (findings.length === 0) return null;
        return (
          <div key={sev}>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold capitalize">
              <Badge variant={sev}>{sev}</Badge>
              {findings.length} finding{findings.length === 1 ? "" : "s"}
            </h3>
            <div className="space-y-2">
              {findings.map((finding) => (
                <Card key={finding.id}>
                  <CardContent className="flex items-start justify-between gap-4 p-4">
                    <div>
                      <p className="font-medium">{finding.check_type}</p>
                      <FindingDetails details={finding.details} />
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={resolvingId === finding.id}
                      onClick={() => handleResolve(finding.id)}
                    >
                      {resolvingId === finding.id ? "Resolving..." : "Mark as resolved"}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RulesVpnTab({ firewallId }: { firewallId: string }) {
  const rulesQuery = useQuery({
    queryKey: ["rules", firewallId],
    queryFn: () => getFirewallRules(firewallId),
  });
  const vpnQuery = useQuery({
    queryKey: ["vpn-tunnels", firewallId],
    queryFn: () => getFirewallVpnTunnels(firewallId),
  });

  const isLoading = rulesQuery.isLoading || vpnQuery.isLoading;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const rules = rulesQuery.data?.rules ?? [];
  const vpnTunnels = vpnQuery.data?.vpn_tunnels ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-semibold">Firewall rules</h3>
        {rules.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No data received yet.
            </CardContent>
          </Card>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  {Object.keys(rules[0]).map((key) => (
                    <TableHead key={key}>{key}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule, idx) => (
                  <TableRow key={idx}>
                    {Object.keys(rules[0]).map((key) => (
                      <TableCell key={key}>{String(rule[key] ?? "—")}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">VPN tunnels</h3>
        {vpnTunnels.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No data received yet.
            </CardContent>
          </Card>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  {Object.keys(vpnTunnels[0]).map((key) => (
                    <TableHead key={key}>{key}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {vpnTunnels.map((tunnel, idx) => (
                  <TableRow key={idx}>
                    {Object.keys(vpnTunnels[0]).map((key) => (
                      <TableCell key={key}>{String(tunnel[key] ?? "—")}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}

function SettingsTab({ firewallId }: { firewallId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { data, isLoading } = useQuery({
    queryKey: ["firewall", firewallId],
    queryFn: () => getFirewall(firewallId),
  });

  const [name, setName] = useState("");
  const [nameInitialised, setNameInitialised] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [isRotating, setIsRotating] = useState(false);
  const [rotatedToken, setRotatedToken] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (data && !nameInitialised) {
      setName(data.name);
      setNameInitialised(true);
    }
  }, [data, nameInitialised]);

  async function handleRename() {
    if (!name.trim()) return;
    setIsRenaming(true);
    try {
      await renameFirewall(firewallId, name.trim());
      queryClient.invalidateQueries({ queryKey: ["firewall", firewallId] });
      queryClient.invalidateQueries({ queryKey: ["firewalls"] });
      toast.success("Firewall renamed.");
    } catch {
      toast.error("Could not rename firewall. Please try again.");
    } finally {
      setIsRenaming(false);
    }
  }

  async function handleRotateToken() {
    setIsRotating(true);
    try {
      const result = await rotateToken(firewallId);
      setRotatedToken(result.agent_token);
    } catch {
      toast.error("Could not rotate token. Please try again.");
    } finally {
      setIsRotating(false);
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await deleteFirewall(firewallId);
      queryClient.invalidateQueries({ queryKey: ["firewalls"] });
      toast.success("Firewall removed.");
      router.push("/dashboard");
    } catch {
      toast.error("Could not remove firewall. Please try again.");
      setIsDeleting(false);
    }
  }

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <p className="font-semibold">Firewall name</p>
        </CardHeader>
        <CardContent className="flex items-end gap-2">
          <div className="flex-1 space-y-2">
            <Label htmlFor="firewall-rename">Name</Label>
            <Input id="firewall-rename" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button onClick={handleRename} disabled={isRenaming || !name.trim()}>
            {isRenaming ? "Saving..." : "Save"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="font-semibold">Agent token</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {rotatedToken ? (
            <>
              <p className="text-sm text-muted-foreground">
                Copy this agent token now — it will not be shown again.
              </p>
              <Input readOnly value={rotatedToken} className="font-mono text-xs" />
            </>
          ) : (
            <>
              <Input readOnly value="••••••••••••••••••••••••" className="font-mono text-xs" />
              <Button
                variant="outline"
                onClick={handleRotateToken}
                disabled={isRotating}
              >
                {isRotating ? "Rotating..." : "Revoke and generate new"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-red-200">
        <CardHeader>
          <p className="font-semibold text-red-600">Remove firewall</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            This permanently removes the firewall and its history from FireAudit.
          </p>
          <Button variant="destructive" onClick={() => setDeleteDialogOpen(true)}>
            Remove firewall
          </Button>
        </CardContent>
      </Card>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove firewall?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The firewall and its findings history will be
              permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? "Removing..." : "Remove firewall"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function FirewallDetailPage() {
  const params = useParams<{ id: string }>();
  const firewallId = params.id;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["firewall", firewallId],
    queryFn: () => getFirewall(firewallId),
  });

  const isOffline = data && data.status !== "active";

  return (
    <main className="min-h-screen bg-background p-6">
      <Button variant="ghost" size="sm" asChild className="mb-4 -ml-2">
        <a href="/dashboard" className="inline-flex items-center gap-1.5">
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </a>
      </Button>

      <div className="mb-6">
        <h1 className="text-xl font-bold">
          {isLoading ? <Skeleton className="h-7 w-48" /> : data?.name ?? "Firewall"}
        </h1>
      </div>

      {isError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Could not load firewall</AlertTitle>
          <AlertDescription>Something went wrong while fetching this firewall.</AlertDescription>
        </Alert>
      )}

      {isOffline && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Agent offline</AlertTitle>
          <AlertDescription>
            This firewall&apos;s agent has been offline since{" "}
            {formatLastSeen(data?.last_seen_at ?? null)}. Findings and metrics may be stale until
            it reconnects.
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="findings">Findings</TabsTrigger>
          <TabsTrigger value="rules-vpn">Rules &amp; VPN</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab firewallId={firewallId} />
        </TabsContent>
        <TabsContent value="findings">
          <FindingsTab firewallId={firewallId} />
        </TabsContent>
        <TabsContent value="rules-vpn">
          <RulesVpnTab firewallId={firewallId} />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab firewallId={firewallId} />
        </TabsContent>
      </Tabs>
    </main>
  );
}
