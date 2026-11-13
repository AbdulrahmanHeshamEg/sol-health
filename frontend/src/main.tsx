import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Layout } from "./components/Layout";
import { ReplayProvider } from "./state/replay";
import { Skeleton } from "./components/ui";

// Pages (and the charting library most of them use) load when opened.
const Me = lazy(() => import("./pages/Me").then((m) => ({ default: m.Me })));
const Cabin = lazy(() => import("./pages/Cabin").then((m) => ({ default: m.Cabin })));
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));
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
              <Route index element={page(<Me />)} />
              <Route path="cabin" element={page(<Cabin />)} />
              <Route path="reports" element={page(<Reports />)} />
              <Route path="learn" element={page(<Learn />)} />
              <Route path="about" element={page(<About />)} />
              <Route path="*" element={<p>That page does not exist. Go back to your health page.</p>} />
            </Route>
          </Routes>
        </ReplayProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
