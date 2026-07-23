import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ArtifactDetailPage } from "./pages/ArtifactDetailPage";
import { ArtifactsPage } from "./pages/ArtifactsPage";
import { CapabilitiesPage } from "./pages/CapabilitiesPage";
import { HomePage } from "./pages/HomePage";
import { MotifsPage } from "./pages/MotifsPage";
import { PolicyStudioPage } from "./pages/PolicyStudioPage";
import { RunDetailPage } from "./pages/RunDetailPage";
import { RunsPage } from "./pages/RunsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="runs/:runId" element={<RunDetailPage />} />
          <Route path="motifs" element={<MotifsPage />} />
          <Route path="policies" element={<PolicyStudioPage />} />
          <Route path="artifacts" element={<ArtifactsPage />} />
          <Route path="artifacts/:artifactId" element={<ArtifactDetailPage />} />
          <Route path="capabilities" element={<CapabilitiesPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
