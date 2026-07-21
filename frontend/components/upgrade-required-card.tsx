"use client";

import { useState } from "react";
import { Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PlansDialog } from "@/components/plans-dialog";

interface UpgradeRequiredCardProps {
  featureLabel: string;
}

export function UpgradeRequiredCard({ featureLabel }: UpgradeRequiredCardProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10">
            <Lock className="h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="font-semibold">Upgrade to Pro to see {featureLabel}</p>
            <p className="text-sm text-muted-foreground">
              The Pro plan unlocks the full compliance engine, firewall rules and VPN visibility.
            </p>
          </div>
          <Button onClick={() => setOpen(true)}>See plans</Button>
        </CardContent>
      </Card>
      <PlansDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
