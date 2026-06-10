"use client";

import * as React from "react";
import { Share2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export interface ShareTestButtonProps {
  /** Server slug for URL construction */
  serverSlug: string;
  /** Tool name to share */
  toolName: string | null;
  /** Tool parameters to encode in URL */
  parameters: Record<string, unknown>;
  /** Whether sharing is available (requires a successful call) */
  enabled: boolean;
}

/**
 * Share Test Button: generates a shareable URL for a tool call configuration.
 *
 * Encodes the tool name and parameters into a URL query string and copies
 * it to the clipboard. Shows a toast on success or failure.
 */
function ShareTestButton({
  serverSlug,
  toolName,
  parameters,
  enabled,
}: ShareTestButtonProps) {
  const [isSharing, setIsSharing] = React.useState(false);

  const handleShare = React.useCallback(async () => {
    if (!toolName) return;

    setIsSharing(true);

    try {
      const url = new URL(
        `/dashboard/servers/${serverSlug}/playground`,
        window.location.origin,
      );
      url.searchParams.set("tool", toolName);

      const paramsStr = JSON.stringify(parameters);
      if (Object.keys(parameters).length > 0) {
        url.searchParams.set("params", paramsStr);
      }

      const shareUrl = url.toString();

      await navigator.clipboard.writeText(shareUrl);
      toast.success("Share URL copied to clipboard", {
        description: "Paste it in a browser to replay this tool call.",
      });
    } catch {
      toast.error("Failed to copy share URL");
    } finally {
      setIsSharing(false);
    }
  }, [serverSlug, toolName, parameters]);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={!enabled || isSharing}
            onClick={handleShare}
            aria-label="Share tool test configuration"
          >
            {isSharing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Share2 className="h-3.5 w-3.5" />
            )}
            Share
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {enabled
            ? "Copy a shareable URL to clipboard"
            : "Complete a tool call first to share"}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export { ShareTestButton };
