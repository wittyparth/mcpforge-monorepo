import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TeamRole } from "@/types/api";

const ROLE_LABELS: Record<TeamRole, string> = {
  admin: "Admin",
  editor: "Editor",
  viewer: "Viewer",
};

interface RoleSelectorProps {
  value: TeamRole;
  onChange: (role: TeamRole) => void;
  disabled?: boolean;
}

export function RoleSelector({ value, onChange, disabled }: RoleSelectorProps) {
  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v as TeamRole)}
      disabled={disabled}
    >
      <SelectTrigger className="w-[140px]" aria-label="Select role">
        <SelectValue placeholder="Select role" />
      </SelectTrigger>
      <SelectContent>
        {(Object.keys(ROLE_LABELS) as TeamRole[]).map((role) => (
          <SelectItem key={role} value={role}>
            {ROLE_LABELS[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
