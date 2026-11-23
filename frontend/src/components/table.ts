import { useMemo, useState } from "react";
import {
  createTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import type { Row } from "../lib/api";

/** A fresh, controlled TanStack table per data/state snapshot; safe for React memoization. */
export function useDataTable(data: Row[], columns: ColumnDef<Row>[]) {
  const [sorting, setSorting] = useState<SortingState>([]);
  return useMemo(() => {
    const table = createTable<Row>({
      data,
      columns,
      state: { sorting },
      onSortingChange: setSorting,
      onStateChange: (updater) => {
        const state =
          typeof updater === "function" ? updater(table.getState()) : updater;
        setSorting(state.sorting);
      },
      renderFallbackValue: null,
      getCoreRowModel: getCoreRowModel(),
      getSortedRowModel: getSortedRowModel(),
    });
    table.setOptions((options) => ({
      ...options,
      state: { ...table.initialState, sorting },
    }));
    return table;
  }, [data, columns, sorting]);
}
