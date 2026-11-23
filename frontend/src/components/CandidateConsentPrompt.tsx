import { useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { ConsentTerm } from "./ConsentTerm";
import { ErrorBox } from "./ui";

export function CandidateConsentPrompt({ children }: { children?: ReactNode }) {
  const session = useSession();
  const client = useQueryClient();
  const [accepted, setAccepted] = useState(false);
  const user = session.data?.user;
  const consent = useQuery({
    queryKey: ["consent-receipts", "entry", user?.id],
    enabled: Boolean(user && user.kind !== "INTERNAL"),
    queryFn: async () => {
      let page = 1;
      let result: Collection;
      do {
        result = await api<Collection>("/privacy/my-consent-receipts?page_number=" + page);
        const receipt = result.items.find(item => item.context === "CADASTRO");
        if (receipt) return receipt;
        page++;
      } while (result.items.length > 0 && (page - 1) * result.page_size < result.total);
      return null;
    },
    refetchOnMount: "always",
  });
  if (!user || user.kind === "INTERNAL") return <>{children}</>;
  if (accepted || consent.data) return <>{children}</>;
  if (consent.isPending) return <section className="surface padded"><p role="status">Conferindo o aceite do termo de consentimento…</p></section>;
  if (consent.isError) return <section className="surface padded"><h1>Termo de consentimento</h1><ErrorBox error={consent.error} /><p>Precisamos conferir seu aceite antes de continuar.</p><button className="button" onClick={() => void consent.refetch()}>Tentar novamente</button></section>;
  return <section className="candidate-first-consent surface padded" aria-label="Aceite obrigatório do termo de consentimento">
    <header><p className="privacy-eyebrow">BOAS-VINDAS AO PORTO AURORA TALENTOS</p><h1>Leia o termo e confirme seu aceite</h1><p>Olá, {user.name.split(" ")[0]}! Antes de preencher seu perfil, conheça como seus dados serão utilizados no processo seletivo.</p><ol className="consent-intro-steps" aria-label="Como continuar o cadastro"><li><span>1</span>Leia o documento até o final</li><li><span>2</span>Confirme a leitura e o aceite</li><li><span>3</span>Continue seu cadastro</li></ol></header>
    <ConsentTerm expanded context="CADASTRO" identity={{ name: user.name, email: user.email }} onAccept={receipt => {
      client.setQueryData(["consent-receipts", "entry", user.id], receipt);
      setAccepted(true);
      void client.invalidateQueries({ queryKey: ["consent-receipts"] });
      void client.invalidateQueries({ queryKey: ["candidate-journey"] });
    }} />
  </section>;
}
