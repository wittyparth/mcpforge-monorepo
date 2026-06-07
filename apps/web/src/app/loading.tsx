import { Cable } from "lucide-react";

export default function RootLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Cable className="h-5 w-5 animate-pulse text-primary" />
        <span className="text-sm">Loading...</span>
      </div>
    </div>
  );
}
