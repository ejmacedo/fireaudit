"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createCheckoutSession } from "@/lib/api/subscription";

interface PlansDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const FREE_FEATURES: { text: string; included: boolean }[] = [
  { text: "Basic infrastructure metrics (CPU, RAM, disk)", included: true },
  { text: "Agent health check (last seen)", included: true },
  { text: "Email alert for agent offline", included: true },
  { text: "Firewall rules and VPN visibility", included: false },
  { text: "6 automated compliance checks", included: false },
  { text: "PDF reports", included: false },
];

const PRO_FEATURES: { text: string; included: boolean }[] = [
  { text: "Everything in Free", included: true },
  { text: "Full visibility of firewall rules and VPN tunnels", included: true },
  { text: "6 automated compliance checks (risky rules, expiring certs, CVEs, etc.)", included: true },
  { text: "PDF reports", included: true },
  { text: "Email + webhook alerts", included: true },
  { text: "90-day history retention", included: true },
];

export function PlansDialog({ open, onOpenChange }: PlansDialogProps) {
  const [isRedirecting, setIsRedirecting] = useState(false);

  async function handleUpgrade() {
    setIsRedirecting(true);
    try {
      const { url } = await createCheckoutSession();
      window.location.href = url;
    } catch {
      toast.error("Could not start checkout. Please try again.");
      setIsRedirecting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Compare plans</DialogTitle>
          <DialogDescription>
            Upgrade to Pro to unlock full firewall visibility and the compliance engine.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border p-4">
            <h3 className="font-semibold">Free</h3>
            <p className="mb-3 text-2xl font-bold">$0<span className="text-sm font-normal text-muted-foreground">/month</span></p>
            <ul className="space-y-2 text-sm">
              {FREE_FEATURES.map((f) => (
                <li key={f.text} className="flex items-start gap-2">
                  {f.included ? (
                    <Check className="mt-0.5 h-4 w-4 text-green-600" />
                  ) : (
                    <X className="mt-0.5 h-4 w-4 text-muted-foreground" />
                  )}
                  <span className={f.included ? "" : "text-muted-foreground"}>{f.text}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border-2 border-primary p-4">
            <h3 className="font-semibold">Pro</h3>
            <p className="mb-3 text-2xl font-bold">$19<span className="text-sm font-normal text-muted-foreground">/month</span></p>
            <ul className="mb-4 space-y-2 text-sm">
              {PRO_FEATURES.map((f) => (
                <li key={f.text} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 text-green-600" />
                  <span>{f.text}</span>
                </li>
              ))}
            </ul>
            <Button onClick={handleUpgrade} disabled={isRedirecting} className="w-full">
              {isRedirecting ? "Redirecting..." : "Sign up for Pro"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
