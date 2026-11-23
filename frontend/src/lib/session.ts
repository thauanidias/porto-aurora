import { useQuery } from "@tanstack/react-query";
import { api, type Session } from "./api";
export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/auth/me"),
    retry: false,
    staleTime: 300000,
  });
}

export function isManager(session?: { permissions: string[] }) {
  return Boolean(session?.permissions.includes("request.create")) &&
    !session?.permissions.includes("vacancy.create") &&
    !session?.permissions.includes("request.approve");
}
