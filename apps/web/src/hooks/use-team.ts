"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TeamRole } from "@/types/api";

const TEAM_KEY = ["team"] as const;
const TEAM_MEMBERS_KEY = ["team-members"] as const;
const TEAM_AUDIT_KEY = ["team-audit-log"] as const;

export function useTeam() {
  return useQuery({
    queryKey: TEAM_KEY,
    queryFn: () => api.team.get(),
    retry: false,
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string }) => api.team.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAM_KEY });
    },
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string }) => api.team.update(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAM_KEY });
    },
  });
}

export function useInviteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; role: TeamRole }) =>
      api.team.invite(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["team-invitations"] });
    },
  });
}

export function useAcceptInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { token: string }) => api.team.accept(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAM_KEY });
      void queryClient.invalidateQueries({ queryKey: TEAM_MEMBERS_KEY });
    },
  });
}

export function useTeamMembers() {
  return useQuery({
    queryKey: TEAM_MEMBERS_KEY,
    queryFn: () => api.team.listMembers(),
  });
}

export function useUpdateMemberRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      role,
    }: {
      userId: string;
      role: TeamRole;
    }) => api.team.updateMember(userId, { role }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAM_MEMBERS_KEY });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.team.removeMember(userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAM_MEMBERS_KEY });
      void queryClient.invalidateQueries({ queryKey: TEAM_KEY });
    },
  });
}

export function useAuditLog(params?: {
  skip?: number;
  limit?: number;
  action?: string;
}) {
  return useQuery({
    queryKey: [...TEAM_AUDIT_KEY, params],
    queryFn: () => api.team.auditLog(params),
  });
}
