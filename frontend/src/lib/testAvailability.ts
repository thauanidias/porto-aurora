import { obj, rows, type Row } from "./api";

export function testAvailability(row: Row, now = Date.now()) {
  if (row.stage_unlocked === false) return "Teste bloqueado. Aguarde o RH avançar esta candidatura para a etapa de testes.";
  if (now < new Date(String(row.opens_at)).getTime()) return "Aguarde a data de abertura do teste.";
  if (now > new Date(String(row.due_at)).getTime()) return "Prazo de realização encerrado.";
  const attempts = rows(row.attempts);
  const active = attempts.some((attempt) => attempt.status === "STARTED");
  if (!active && attempts.length >= Number(obj(row.snapshot).attempts_allowed)) {
    return "Todas as tentativas deste teste foram concluídas.";
  }
  return "";
}
