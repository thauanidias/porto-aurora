import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, obj, put, str } from "../lib/api";
import { SchemaForm, type Schema } from "./SchemaForm";
import { ErrorBox } from "./ui";
import { FilePenLine, ShieldCheck } from "lucide-react";
import { RegistrationSnapshot } from "./CandidateRegistrationDocuments";
import { withFormChoices } from "../lib/formChoices";

const endpoint = "/candidates/me/selection-registration";
export function externalTemplateSchema(source: Schema): Schema {
  return { ...source, $defs: Object.fromEntries(Object.entries(source.$defs ?? {}).map(([name, definition]) => [name, {
    ...definition,
    ...(name === "BankDetails" ? { description: "Banco Bradesco. Informe agência e conta corrente; não informe conta poupança." } : {}),
    properties: definition.properties && Object.fromEntries(Object.entries(definition.properties).map(([field, config]) => [field,
      (name === "BankDetails" && field === "bank_name") || (name === "ExternalDeclaration" && field === "signature_name") ? { ...config, readOnly: true }
      : name === "EducationDetails" && field === "high_school" ? { ...config, enum: ["Não informado", "Completo"] }
      : config,
    ])),
  }])) };
}
type Registration = {
  data: Record<string, unknown> | null;
  version: number;
  saved_at: string | null;
  confirmed_at: string | null;
  signature_record?: { protocol: string } | null;
};

export function SelectionRegistration({ identity }: { identity: Record<string, unknown> }) {
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(true);
  const [saved, setSaved] = useState<Registration>();
  const [editing, setEditing] = useState(false);
  const schema = useQuery({
    queryKey: ["selection-registration-schema"],
    queryFn: () => api<Schema>(endpoint + "/schema"),
    enabled: expanded,
  });
  const registration = useQuery({
    queryKey: ["selection-registration"],
    queryFn: () => api<Registration>(endpoint),
    enabled: expanded,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  });
  const current = saved ?? registration.data;
  const signed = Boolean(current?.confirmed_at && current.signature_record && !editing);
  const initial = current?.data ? { ...current.data, ...(editing ? { declaration: { ...obj(current.data.declaration), accepted: false, signature_image: "", date: null } } : {}) } : { personal: { name: str(identity.name), email: str(identity.email) } };
  return (
    <section className="surface padded selection-registration" aria-labelledby="selection-registration-title">
      <div className="registration-heading"><div><p className="privacy-eyebrow">FORM-PPO-RH-002.02 · CONFIDENCIAL</p><h2 id="selection-registration-title"><FilePenLine size={22} aria-hidden="true" /> Ficha de inscrição para seleção externa</h2></div><span className={"registration-status" + (signed ? " signed" : "")}>{signed ? "Ficha assinada" : "Em preenchimento"}</span></div>
      <p>Preencha a ficha com seus dados pessoais, documentação, dependentes, histórico profissional e informações complementares. Nas listas, digite para filtrar as opções. Nos campos com sugestões, você também pode escrever outra resposta. Você pode salvar e continuar depois.</p>
      <p className="muted"><ShieldCheck size={16} aria-hidden="true" /> Seus dados ficam protegidos, com acesso restrito ao RH, e não participam do cálculo de aderência.</p>
      <ol className="registration-steps"><li><strong>1</strong> Preencha os dados aplicáveis</li><li><strong>2</strong> Revise a ficha completa</li><li><strong>3</strong> Assine e confirme as declarações</li></ol>
      {!signed && <p className="registration-help">Você pode salvar um rascunho sem confirmar as declarações. Para concluir, informe os dados de identificação e contato, registre sua assinatura, marque a confirmação e salve. O RH receberá a ficha completa assinada.</p>}
      <button type="button" className="button secondary" aria-expanded={expanded} aria-controls="selection-registration-content" onClick={() => setExpanded(!expanded)}>
        {expanded ? "Recolher ficha" : "Abrir ficha de inscrição"}
      </button>
      <div id="selection-registration-content" hidden={!expanded}>
        <>
          <ErrorBox error={schema.error ?? registration.error} />
          {(schema.isPending || registration.isPending) && <p role="status">Carregando ficha…</p>}
          {(schema.isError || registration.isError) && <button className="button secondary" onClick={() => { void schema.refetch(); void registration.refetch(); }}>Tentar novamente</button>}
          {saved && <p className="alert success" role="status">{signed ? "Ficha concluída e assinada. O documento original já está disponível para o RH." : "Rascunho salvo. Você pode continuar o preenchimento depois."}</p>}
          {signed && schema.data && current?.data ? <><p className="muted">Protocolo: {current.signature_record?.protocol}. Se precisar corrigir informações, edite e assine novamente.</p><button className="button secondary" onClick={() => setEditing(true)}>Editar ficha e assinar novamente</button><details className="registration-completed"><summary>Conferir ficha enviada ao RH</summary><RegistrationSnapshot data={current.data} schema={schema.data} root={schema.data} /></details></> : schema.data && registration.isSuccess && <SchemaForm
            key={`${current?.version ?? 0}-${editing}`}
            schema={withFormChoices(externalTemplateSchema(schema.data))}
            searchableSelects
            initial={initial}
            submitLabel="Salvar ficha e assinatura"
            onSubmit={async (data) => {
              setSaved(undefined);
              const payload = { ...data, bank: { ...obj(data.bank), bank_name: "Bradesco" }, declaration: { ...obj(data.declaration), signature_name: str(obj(data.personal).name) } };
              const result = await put<Registration>(endpoint, { data: payload, version: current?.version ?? 0 });
              setSaved(result);
              setEditing(false);
              client.setQueryData(["selection-registration"], result);
            }}
          />}
        </>
      </div>
    </section>
  );
}
