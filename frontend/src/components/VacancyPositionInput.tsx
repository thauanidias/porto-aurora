import { useQuery } from "@tanstack/react-query";
import { api, str, type Collection } from "../lib/api";
import { SearchSelect } from "./SearchSelect";

export function VacancyPositionInput({ title, value, onChange }: { title: string; value: string; onChange: (value: string) => void }) {
  const vacancies = useQuery({ queryKey: ["available-position-titles"], staleTime: 60000,
    queryFn: async () => {
      const names = new Set<string>();
      let page = 1;
      while (true) {
        const result = await api<Collection>(`/public/vacancies?page_size=100&page_number=${page}`);
        for (const vacancy of result.items) if (str(vacancy.title)) names.add(str(vacancy.title));
        if (!result.items.length || page * 100 >= (result.total ?? 0)) break;
        page++;
      }
      return [...names].sort((a, b) => a.localeCompare(b, "pt-BR"));
    } });
  return <div className="field"><span>{title}</span><SearchSelect title={title} value={value} onChange={onChange} options={(vacancies.data ?? []).map(name => ({ value: name, label: name }))} loading={vacancies.isPending} error={Boolean(vacancies.error)} allowCustom placeholder="Selecione uma vaga ou digite o cargo" /></div>;
}
