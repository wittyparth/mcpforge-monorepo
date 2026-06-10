"use client";

import { useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Copy, Check } from "lucide-react";
import type { ApiKeyCreateResponse } from "@/types/api";

const DISMISSED_KEY = "mcpforge_api_key_dismissed";

interface KeyDisplayOnceProps {
  response: ApiKeyCreateResponse | null;
  onDismiss: () => void;
}

export function KeyDisplayOnce({ response, onDismiss }: KeyDisplayOnceProps) {
  const [copied, setCopied] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!response) return;
    await navigator.clipboard.writeText(response.plaintext_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [response]);

  const handleDismiss = () => {
    if (!acknowledged) return;
    try {
      window.localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // localStorage unavailable
    }
    onDismiss();
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && acknowledged) {
      handleDismiss();
    }
  };

  if (!response) return null;

  return (
    <Dialog open={!!response} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-600">
            <AlertTriangle className="h-5 w-5" />
            Save your API key
          </DialogTitle>
          <DialogDescription>
            This is the only time you&apos;ll see this key. Copy it now and
            store it securely. You won&apos;t be able to see it again.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="relative rounded-md border bg-muted p-4">
            <code className="break-all font-mono text-sm">
              {response.plaintext_key}
            </code>
            <Button
              variant="outline"
              size="icon"
              className="absolute right-2 top-2 h-8 w-8"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-600" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              <span className="sr-only">Copy key</span>
            </Button>
          </div>

          {copied && (
            <p className="text-sm text-green-600">Copied to clipboard!</p>
          )}

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="acknowledge-key"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <label htmlFor="acknowledge-key" className="text-sm">
              I&apos;ve saved my key
            </label>
          </div>

          <Button
            className="w-full"
            disabled={!acknowledged}
            onClick={handleDismiss}
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
