import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { obj, post, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { InterviewLinkForm } from "./InterviewLinkForm";
import { Modal } from "./ui";

export function InterviewAttachmentButton({ application }: { application: Row }) {
  const session = useSession();
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const client = useQueryClient();
  const available = session.data?.permissions.includes("candidate.move") &&
    ["INTERVIEW", "TEST"].includes(str(obj(application.candidate_access).phase)) &&
    ["ACTIVE", "RESERVE"].includes(str(application.status));
  if (!available) return null;
  return <>
    <button className="button secondary small" onClick={() => { setOpen(true); setSaved(false); }}><Link2 size={16} aria-hidden="true" />Anexar link da entrevista</button>
    {saved && <span className="muted" role="status">Link da entrevista salvo.</span>}
    <Modal open={open} onOpenChange={setOpen} title="Anexar link da entrevista">
      {open && <><p><strong>{str(application.vacancy_title)}</strong></p><InterviewLinkForm onSubmit={async content => {
        await post("/candidate-activity-links", { ...content, application_id: application.id, kind: "INTERVIEW" });
        setOpen(false); setSaved(true);
        await client.invalidateQueries();
      }} /></>}
    </Modal>
  </>;
}
