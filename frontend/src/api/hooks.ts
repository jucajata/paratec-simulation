import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { CaseRequest, FlowType, ScrapeJob } from "./types";

export function useSnapshots() {
  return useQuery({ queryKey: ["snapshots"], queryFn: api.snapshots });
}

/** Inicia la descarga de una fecha (FR-038). */
export function useStartScrape() {
  return useMutation({ mutationFn: (date: string) => api.startScrape(date) });
}

const SCRAPE_POLL_MS = 1000;

function isRunning(job: ScrapeJob | undefined): boolean {
  return job !== undefined && job.status !== "listo" && job.status !== "error";
}

/** Estado de una descarga; sondea cada segundo mientras corre (FR-038). */
export function useScrapeJob(jobId: string | null) {
  return useQuery({
    queryKey: ["scrape", jobId],
    queryFn: () => api.scrapeJob(jobId as string),
    enabled: jobId !== null,
    staleTime: 0,
    refetchInterval: (query) => (isRunning(query.state.data) || query.state.data === undefined ? SCRAPE_POLL_MS : false),
  });
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
