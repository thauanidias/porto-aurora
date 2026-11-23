import { useQuery } from "@tanstack/react-query";
import { api, type Collection } from "./api";

export function useTestQuestionnaires() {
  return useQuery({ queryKey: ["my-test-questionnaires"], queryFn: () => api<Collection>("/test-questionnaires/me"), refetchInterval: 15000 });
}
