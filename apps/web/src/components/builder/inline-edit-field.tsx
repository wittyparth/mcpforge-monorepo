"use client";

import * as React from "react";
import { Pencil, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface InlineEditFieldProps {
  /** The current text value. */
  value: string;
  /** Called when the user saves a new value. */
  onChange: (value: string) => void;
  /** Label shown above the textarea when editing. */
  label: string;
  /** Optional placeholder text for the textarea. */
  placeholder?: string;
  /** Whether the field is disabled. */
  disabled?: boolean;
  /** Rows for the textarea. Defaults to 3. */
  rows?: number;
}

/**
 * Inline-editable text field with a compact edit/save/cancel pattern.
 *
 * Displays the current value as static text by default. When the user
 * clicks the edit icon, a textarea replaces the text. The user can
 * save (checkmark) or cancel (X) the edit.
 */
const InlineEditField = React.forwardRef<HTMLDivElement, InlineEditFieldProps>(
  ({ value, onChange, label, placeholder, disabled = false, rows = 3 }, ref) => {
    const [editing, setEditing] = React.useState(false);
    const [draft, setDraft] = React.useState(value);
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    // Sync draft when external value changes
    React.useEffect(() => {
      if (!editing) {
        setDraft(value);
      }
    }, [value, editing]);

    // Focus textarea when entering edit mode
    React.useEffect(() => {
      if (editing && textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.select();
      }
    }, [editing]);

    const handleSave = () => {
      const trimmed = draft.trim();
      if (trimmed !== value) {
        onChange(trimmed);
      } else {
        setDraft(value);
      }
      setEditing(false);
    };

    const handleCancel = () => {
      setDraft(value);
      setEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Escape") {
        handleCancel();
      }
      // Cmd/Ctrl + Enter to save
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSave();
      }
    };

    return (
      <div ref={ref} className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-muted-foreground">
            {label}
          </label>
          {!editing && !disabled && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className={cn(
                "rounded p-0.5 text-muted-foreground transition-colors",
                "hover:text-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
              )}
              aria-label={`Edit ${label}`}
            >
              <Pencil className="h-3 w-3" />
            </button>
          )}
        </div>

        {editing ? (
          <div className="space-y-2">
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={rows}
              className={cn(
                "w-full rounded-md border bg-background px-3 py-2 text-sm",
                "placeholder:text-muted-foreground/50",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "resize-none",
              )}
            />
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleSave}
                className="h-7 gap-1 px-2 text-xs"
              >
                <Check className="h-3 w-3" />
                Save
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={handleCancel}
                className="h-7 gap-1 px-2 text-xs"
              >
                <X className="h-3 w-3" />
                Cancel
              </Button>
              <span className="ml-1 text-[10px] text-muted-foreground/50">
                ⌘ + Enter to save
              </span>
            </div>
          </div>
        ) : (
          <div
            className={cn(
              "min-h-[2.5rem] rounded-md border border-transparent bg-muted/30 px-3 py-2 text-sm",
              "whitespace-pre-wrap break-words",
              disabled
                ? "cursor-not-allowed opacity-50"
                : "cursor-pointer hover:bg-muted/50",
            )}
            onClick={() => !disabled && setEditing(true)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (!disabled && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                setEditing(true);
              }
            }}
          >
            {value || (
              <span className="italic text-muted-foreground/50">
                No description
              </span>
            )}
          </div>
        )}
      </div>
    );
  },
);
InlineEditField.displayName = "InlineEditField";

export { InlineEditField };
