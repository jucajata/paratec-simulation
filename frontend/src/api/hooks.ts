import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { CaseRequest, FlowType } from "./types";

export function useSnapshots() {
  return useQuery({ queryKey: ["snapshots"], queryFn: api.snapshots });
}

export function useCreateCase() {
  return useMutation({ mutationFn: (body: CaseRequest) => api.createCase(body) });
}

export function useCase(caseId: string | null) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.getCase(caseId as string),
    enabled: caseId !== null,
  });
}

export function useRunCase() {
  return useMutation({
    mutationFn: ({ caseId, flowType }: { caseId: string; flowType: FlowType }) =>
      api.runCase(caseId, flowType),
  });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId as string),
    enabled: runId !== null,
  });
}

export function useTopology(runId: string | null) {
  return useQuery({
    queryKey: ["topology", runId],
    queryFn: () => api.topology(runId as string),
    enabled: runId !== null,
  });
}

/** Mapa base para la disposición geográfica (FR-035); no cambia, así que no se refresca. */
export function useBasemap(enabled: boolean) {
  return useQuery({ queryKey: ["basemap"], queryFn: () => api.basemap(), enabled, staleTime: Infinity });
}
