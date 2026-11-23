import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { ConversationView } from "./ConversationView";

export function ApplicationConversation({ applicationId }: { applicationId: string }) {
  const [body, setBody] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  const session = useSession();
  const canSend = session.data?.user.kind === "CANDIDATO" || Boolean(session.data?.permissions.includes("message.send"));
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["messages", applicationId, "conversation", page], queryFn: () => api<Collection>(`/applications/${applicationId}/messages?conversation_only=true&page_number=${page}`),
    refetchInterval: page === 1 ? 2000 : 10000, refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always", refetchOnReconnect: "always" });
  const readMessage = useRef("");
  const latestId = query.data?.items[0]?.id;
  useEffect(() => {
    if (!latestId || page !== 1 || readMessage.current === latestId || document.visibilityState === "hidden") return;
    readMessage.current = latestId;
    void post(`/applications/${applicationId}/messages/read`, { message_id: latestId })
      .then(() => client.invalidateQueries({ queryKey: ["message-unread"] }))
      .catch(() => { readMessage.current = ""; });
  }, [latestId, page, applicationId, client, query.dataUpdatedAt]);
  return <ConversationView title="Conversa entre candidato e RH" description="Dúvidas e orientações sobre esta candidatura." recipient={session.data?.user.kind === "CANDIDATO" ? "o RH" : "o candidato"} userId={session.data?.user.id}
    messages={query.data} loading={query.isPending} failed={query.isError} error={error ?? query.error}
    body={body} busy={busy} sent={sent} canSend={canSend} page={page}
    onBody={value => { setBody(value); setSent(false); }} onPage={setPage} onRetry={() => void query.refetch()}
    onSend={async () => {
      if (busy || !canSend || !body.trim()) return;
      setBusy(true); setError(undefined); setSent(false);
      try {
        await post(`/applications/${applicationId}/messages`, { subject: "Conversa com o RH", body: body.trim(), visibility: "CANDIDATE" });
        setBody(""); setPage(1); setSent(true);
        await client.invalidateQueries({ queryKey: ["messages", applicationId] });
        await client.invalidateQueries({ queryKey: ["message-unread"] });
      } catch (err) { setError(err); } finally { setBusy(false); }
    }} />;
}
