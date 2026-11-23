import { api, post, type Collection, type Row } from "./api";
import { safeReturnPath } from "./returnPath";

export async function enrollSelectedVacancy(returnTo: string) {
  const path = safeReturnPath(returnTo);
  if (!path) throw new Error("Selecione uma vaga no portal para se inscrever.");
  const url = new URL(path, "https://portal.invalid");
  const invitation = url.pathname === "/convite";
  const invitationToken = new URLSearchParams(url.hash.slice(1)).get("token");
  const match = url.pathname.match(/^\/(carreiras\/vagas|oportunidades-internas)\/([^/]+)\/?$/);
  if (!match && !(invitation && invitationToken)) throw new Error("Selecione novamente a vaga no portal.");
  const job = invitation
    ? await post<Row>("/public/invitations/lookup", { token: invitationToken })
    : await api<Row>((match![1] === "carreiras/vagas" ? "/public/vacancies/" : "/internal/vacancies/") + match![2]);
  const existing = await api<Collection>("/applications?vacancy_id=" + encodeURIComponent(job.id));
  if (existing.items[0]) return existing.items[0];
  const readiness = await api<{ ready: boolean; missing: string[]; cv_id: string | null }>("/candidates/me/application-readiness");
  if (!readiness.ready) throw new Error("Perfil salvo. Para concluir sua inscrição, preencha: " + readiness.missing.join(", ") + ". Depois, clique novamente em Salvar e inscrever-se na vaga.");
  return post<Row>("/applications", {
    vacancy_id: job.id, enrollment: true, cv_id: readiness.cv_id,
    ...(invitation ? { invitation_token: invitationToken } : {}),
    utm: Object.fromEntries([...url.searchParams].filter(([key]) => ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].includes(key))),
  });
}
