import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Layout } from "./components/Layout";
import { ReplayProvider } from "./state/replay";
import { Overview } from "./pages/Overview";
import { Detail } from "./pages/Detail";
import { Alerts } from "./pages/Alerts";
import { Learn } from "./pages/Learn";
import { About } from "./pages/About";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ReplayProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Overview />} />
              <Route path="crew/:id" element={<Detail />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="learn" element={<Learn />} />
              <Route path="about" element={<About />} />
              <Route path="*" element={<p>That page does not exist. Go back to the crew.</p>} />
            </Route>
          </Routes>
        </ReplayProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
