import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { VacancyRequestDetail } from "./VacancyRequestDetail";

afterEach(cleanup);

it("mostra nomes, valores traduzidos e o retorno do RH sem identificadores internos", () => {
  const { container } = render(<VacancyRequestDetail request={{ id: "internal-request-id", version: 1,
    title: "Vaga de estágio", status: "PENDING_APPROVAL", org_unit_id: "internal-org-id",
    org_unit_name: "Tecnologia da Informação", requested_by: "internal-user-id", requested_by_name: "Maria Silva",
    quantity: 1, current_step: 0, rh_feedback: "Confirme a jornada do estágio.",
    details: { position: "Estagiário", request_type: "REPLACEMENT", urgency: "NORMAL", desired_date: "2026-05-10",
      cost_center: "12551", reason: "Conclusão do estágio atual", justification: "Manter o atendimento da equipe.", replaced_employee: "João" },
    workflow_snapshot: [{ name: "Análise do RH", approver_id: "internal-approver-id", sla_hours: 48 }],
  }} />);
  expect(screen.getByText("Tecnologia da Informação")).toBeVisible();
  expect(screen.getByText("Maria Silva")).toBeVisible();
  expect(screen.getByText("Substituição")).toBeVisible();
  expect(screen.getByText("Normal")).toBeVisible();
  expect(screen.getByText("10/05/2026")).toBeVisible();
  expect(screen.getByText("Confirme a jornada do estágio.")).toBeVisible();
  expect(screen.getByText("Análise do RH").closest("li")).toHaveAttribute("aria-current", "step");
  expect(container.textContent).not.toMatch(/internal-|workflow_snapshot|REPLACEMENT|NORMAL|requested_by/);
});
