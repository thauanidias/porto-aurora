import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function TestMailbox() {
  const features = useQuery({
    queryKey: ["public-features"],
    queryFn: () => api<{ test_email: boolean }>("/public/features"),
  });
  if (!features.data?.test_email) return null;
  const inbox = new URL(window.location.origin);
  inbox.port = "8025";
  return (
    <aside className="alert" role="note">
      <strong>E-mails de teste</strong>
      <p>Os códigos e links de confirmação chegam à caixa local. Procure pelo e-mail usado no cadastro. Neste ambiente, as mensagens não são enviadas para sua caixa corporativa.</p>
      <a className="button secondary" href={inbox.href} target="_blank" rel="noopener noreferrer">
        Abrir caixa de e-mails de teste
      </a>
    </aside>
  );
}
