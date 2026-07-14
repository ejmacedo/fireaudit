import { Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="flex flex-col items-center gap-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary">
          <Shield className="h-8 w-8 text-primary-foreground" />
        </div>

        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">FireAudit</h1>
          <p className="text-xl text-muted-foreground">
            Continuous compliance and audit for pfSense firewalls
          </p>
        </div>

        <p className="max-w-md text-muted-foreground">
          Automated security analysis, drift detection, and remote configuration
          management for pfSense administrators.
        </p>

        <div className="flex gap-3">
          <Button size="lg" disabled>
            Get early access
          </Button>
          <Button size="lg" variant="outline" disabled>
            Learn more
          </Button>
        </div>

        <p className="text-sm text-muted-foreground">
          Coming soon &mdash; currently in development
        </p>
      </div>
    </main>
  );
}
