"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PlansDialog } from "@/components/plans-dialog";

interface UpgradeTeaserProps {
  totalOpenFindings: number;
  criticalCount: number;
  highCount: number;
}

export function UpgradeTeaser({
  totalOpenFindings,
  criticalCount,
  highCount,
}: UpgradeTeaserProps) {
  const [open, setOpen] = useState(false);

  const message =
    totalOpenFindings > 0
      ? `${totalOpenFindings} finding${totalOpenFindings === 1 ? "" : "s"} detected` +
        (criticalCount > 0
          ? ` (${criticalCount} critical)`
          : highCount > 0
            ? ` (${highCount} high-severity)`
            : "") +
        " — available on the Pro plan."
      : "Unlock the compliance engine, firewall rules and VPN visibility on the Pro plan.";

  return (
    <>
      <Alert className="mb-6 border-primary/50 bg-primary/5">
        <Sparkles className="h-4 w-4" />
        <AlertTitle>Upgrade to Pro</AlertTitle>
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{message}</span>
          <Button size="sm" onClick={() => setOpen(true)}>
            See plans
          </Button>
        </AlertDescription>
      </Alert>
      <PlansDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
