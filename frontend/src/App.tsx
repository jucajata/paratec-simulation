import { QueryClientProvider } from "@tanstack/react-query";

import { Workspace } from "./features/workspace/Workspace";
import { queryClient } from "./lib/queryClient";
import "./styles.css";

export function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <Workspace />
    </QueryClientProvider>
  );
}
