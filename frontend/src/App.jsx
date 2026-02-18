import { BrowserRouter, Routes, Route } from "react-router";
import { AuthProvider } from "./auth/AuthProvider";
import ProtectedRoute from "./auth/ProtectedRoute";
import Landing from "./pages/Landing";
import Callback from "./pages/Callback";
import Dashboard from "./pages/Dashboard";
import PitcherDetail from "./pages/PitcherDetail";
import PitcherCompare from "./pages/PitcherCompare";
import Layout from "./components/Layout";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/callback" element={<Callback />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/pitchers/:id" element={<PitcherDetail />} />
              <Route path="/pitchers/:idA/compare" element={<PitcherCompare />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
