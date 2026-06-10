"use client";

import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface CheckoutButtonProps {
  isLoading: boolean;
  onClick: () => void;
  disabled?: boolean;
  label?: string;
}

export function CheckoutButton({
  isLoading,
  onClick,
  disabled = false,
  label = "Upgrade",
}: CheckoutButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled || isLoading}
      className="w-full"
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Redirecting to checkout...
        </>
      ) : (
        label
      )}
    </Button>
  );
}
