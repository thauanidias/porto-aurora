import { useDataTable } from "./table";
import { useMemo, useRef, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { flexRender, type ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown, ChevronLeft, ChevronRight, Inbox, X, BriefcaseBusiness, Users, FileText, CalendarDays, MessageSquare, Settings, ShieldCheck, ChartNoAxesCombined, ClipboardCheck, GraduationCap } from "lucide-react";
import { ApiError, type Row, str } from "../lib/api";
import { label, date } from "../lib/labels";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="alert error" role="alert">
      <strong>
        {error instanceof Error
          ? error.message
          : "Não foi possível concluir a operação."}
      </strong>
      {error instanceof ApiError &&
        error.details.map((d, i) => (
          <div key={i}>
            {label(d.field.split(".").at(-1) ?? "")}: {d.message}
          </div>
        ))}
      {error instanceof ApiError && error.requestId && (
        <small>Atendimento: {error.requestId}</small>
      )}
    </div>
  );
}
export function Empty({
  title = "Nenhum registro encontrado",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={32} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Badge({ value }: { value: unknown }) {
  const s = str(value);
  return (
    <span className={"badge status-" + s.toLowerCase()}>
      <span className="status-dot" aria-hidden />
      {label(s)}
    </span>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  const content = useRef<HTMLDivElement>(null);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (
          !value &&
          content.current?.querySelector('form[data-dirty="true"]') &&
          !window.confirm("Há alterações não salvas. Deseja descartar?")
        )
          return;
        onOpenChange(value);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          ref={content}
          className="modal"
          aria-describedby={undefined}
        >
          <div className="modal-header">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Fechar">
              <X size={20} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function PageTitle({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  const text = title.toLocaleLowerCase("pt-BR");
  const Icon = /vaga|oportunidade/.test(text) ? BriefcaseBusiness
    : /candidat|talento|gestor|usuário|colaborador/.test(text) ? Users
    : /entrevista|agenda/.test(text) ? CalendarDays
    : /mensage|conversa/.test(text) ? MessageSquare
    : /configura|administra/.test(text) ? Settings
    : /privacidade|auditoria|permiss/.test(text) ? ShieldCheck
    : /relatório|indicador|resultado/.test(text) ? ChartNoAxesCombined
    : /teste|prova/.test(text) ? GraduationCap
    : /tarefa|avalia|checklist/.test(text) ? ClipboardCheck : FileText;
  return (
    <div className="page-title">
      <div className="page-title-copy">
        <span className="page-title-icon" aria-hidden="true"><Icon size={25} /></span>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="actions">{actions}</div>
    </div>
  );
}
export function DataTable({
  data,
  columns: keys,
  onOpen,
  total,
  page = 1,
  pageSize = 25,
  onPage,
  actions,
  cells,
  columnLabels,
  showDensity = true,
}: {
  data: Row[];
  columns: string[];
  onOpen?: (row: Row) => void;
  total?: number;
  page?: number;
  pageSize?: number;
  onPage?: (n: number) => void;
  actions?: (row: Row) => ReactNode;
  cells?: Record<string, (row: Row) => ReactNode>;
  columnLabels?: Record<string, string>;
  showDensity?: boolean;
}) {
  const [dense, setDense] = useState(
    localStorage.getItem("density") === "compact",
  );
  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      keys.map((key) => ({
        accessorKey: key,
          header: () => columnLabels?.[key] ?? label(key),
        cell: ({ getValue, row }) =>
          cells?.[key] ? cells[key](row.original) : key === "status" ? (
            <Badge value={getValue()} />
          ) : key.endsWith("_at") || ["deadline", "due_at"].includes(key) ? (
            date(getValue())
          ) : (
            <span>
              {Array.isArray(getValue())
                ? (getValue() as unknown[]).map((v) => str(v)).join(", ")
                : typeof getValue() === "boolean"
                  ? getValue()
                    ? "Sim"
                    : "Não"
                  : typeof getValue() === "object"
                    ? "—"
                    : str(getValue()) || "—"}
            </span>
          ),
      })),
      [keys, cells, columnLabels],
  );
  const table = useDataTable(data, columns);
  if (!data.length) return <Empty />;
  return (
    <>
      <div className="table-tools">
          <span>{total ?? data.length} {(total ?? data.length) === 1 ? "registro" : "registros"}</span>
        {showDensity && <label>
          <input
            type="checkbox"
            checked={dense}
            onChange={(e) => {
              setDense(e.target.checked);
              localStorage.setItem(
                "density",
                e.target.checked ? "compact" : "comfortable",
              );
            }}
          />{" "}
          Densidade compacta
        </label>}
      </div>
      <div className="table-scroll">
        <table className={showDensity && dense ? "compact" : ""}>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th key={header.id}>
                    <button onClick={header.column.getToggleSortingHandler()}>
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      <ArrowUpDown size={13} />
                    </button>
                  </th>
                ))}
                {(onOpen || actions) && <th>Ações</th>}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} data-label={columnLabels?.[cell.column.id] ?? label(cell.column.id)}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
                {(onOpen || actions) && (
                  <td className="row-actions">
                    {onOpen && (
                      <button
                        className="text-button"
                        onClick={() => onOpen(row.original)}
                      >
                        Abrir
                      </button>
                    )}
                    {actions?.(row.original)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {onPage && (
        <div className="pagination">
          <button
            className="icon-button"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            aria-label="Página anterior"
          >
            <ChevronLeft size={18} />
          </button>
          <span>Página {page}</span>
          <button
            className="icon-button"
            disabled={page * pageSize >= (total ?? 0)}
            onClick={() => onPage(page + 1)}
            aria-label="Próxima página"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </>
  );
}
