import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { ConversationView } from "./ConversationView";

export function VacancyConversation({ vacancyId }: { vacancyId: string }) {
  const [body, setBody] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  const client = useQueryClient();
  const session = useSession();
  const query = useQuery({ queryKey: ["vacancy-messages", vacancyId, page], queryFn: () => api<Collection>(`/vacancies/${vacancyId}/messages?page_number=${page}`), refetchInterval: page === 1 ? 2000 : 10000, refetchIntervalInBackground: true, refetchOnWindowFocus: "always", refetchOnReconnect: "always" });
  return <ConversationView title="Conversa entre gestor e RH" description="Conversa interna sobre a vaga, visível à equipe responsável." recipient="a equipe responsável" userId={session.data?.user.id}
    messages={query.data} loading={query.isPending} failed={query.isError} error={error ?? query.error}
    body={body} busy={busy} sent={sent} canSend={true} page={page}
    onBody={value => { setBody(value); setSent(false); }} onPage={setPage} onRetry={() => void query.refetch()}
    onSend={async () => {
      if (busy || !body.trim()) return;
      setBusy(true); setError(undefined); setSent(false);
      try { await post(`/vacancies/${vacancyId}/messages`, { body: body.trim() }); setBody(""); setPage(1); setSent(true); await client.invalidateQueries({ queryKey: ["vacancy-messages", vacancyId] }); }
      catch (err) { setError(err); } finally { setBusy(false); }
    }} />;
}
