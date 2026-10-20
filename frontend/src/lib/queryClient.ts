import { QueryClient } from "@tanstack/react-query";

// Estado de servidor con TanStack Query; sin estado global adicional (constitución II).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 60_000 },
    mutations: { retry: false },
  },
});
