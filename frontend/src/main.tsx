import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Layout } from "./components/Layout";
import { ReplayProvider } from "./state/replay";
import { Overview } from "./pages/Overview";
import { Skeleton } from "./components/ui";

// The crew overview loads first; the other pages (and the charting library they use) load when opened.
const Detail = lazy(() => import("./pages/Detail").then((m) => ({ default: m.Detail })));
const Alerts = lazy(() => import("./pages/Alerts").then((m) => ({ default: m.Alerts })));
const Learn = lazy(() => import("./pages/Learn").then((m) => ({ default: m.Learn })));
const About = lazy(() => import("./pages/About").then((m) => ({ default: m.About })));
const page = (el: React.ReactNode) => <Suspense fallback={<Skeleton lines={6} height={28} />}>{el}</Suspense>;

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ReplayProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Overview />} />
              <Route path="crew/:id" element={page(<Detail />)} />
              <Route path="alerts" element={page(<Alerts />)} />
              <Route path="learn" element={page(<Learn />)} />
              <Route path="about" element={page(<About />)} />
              <Route path="*" element={<p>That page does not exist. Go back to the crew.</p>} />
            </Route>
          </Routes>
        </ReplayProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
