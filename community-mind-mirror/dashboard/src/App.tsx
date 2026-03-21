import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Topics from "./pages/Topics";
import TopicDetail from "./pages/TopicDetail";
import People from "./pages/People";
import PersonaDetail from "./pages/PersonaDetail";
import News from "./pages/News";
import Geo from "./pages/Geo";
import Intelligence from "./pages/Intelligence";
import SearchPage from "./pages/SearchPage";
import Signals from "./pages/Signals";
import System from "./pages/System";
import GigBoard from "./pages/GigBoard";
import Research from "./pages/Research";
import ResearchDetail from "./pages/ResearchDetail";
import { useWebSocket } from "./hooks/useWebSocket";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

function AppInner() {
  useWebSocket();

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="topics" element={<Topics />} />
          <Route path="topics/:id" element={<TopicDetail />} />
          <Route path="people" element={<People />} />
          <Route path="people/:id" element={<PersonaDetail />} />
          <Route path="intelligence" element={<Intelligence />} />
          <Route path="gig-board" element={<GigBoard />} />
          <Route path="research" element={<Research />} />
          <Route path="research/:id" element={<ResearchDetail />} />
          <Route path="signals" element={<Signals />} />
          <Route path="news" element={<News />} />
          <Route path="system" element={<System />} />
          <Route path="geo" element={<Geo />} />
          <Route path="search" element={<SearchPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  );
}
