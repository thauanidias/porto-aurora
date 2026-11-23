import { useQuery } from "@tanstack/react-query";
import { api, type Collection } from "./api";

export type ActivityKind = "INTERVIEW" | "TEST";
export function useActivityLinks(kind?: ActivityKind, candidateId?: string, applicationId?: string) {
  const params = new URLSearchParams();
  if (kind) params.set("kind", kind);
  if (candidateId) params.set("candidate_id", candidateId);
  if (applicationId) params.set("application_id", applicationId);
  return useQuery({ queryKey: ["candidate-activity-links", candidateId ?? "me", kind ?? "", applicationId ?? ""],
    queryFn: () => api<Collection>("/candidate-activity-links?" + params), refetchInterval: 15000 });
}
