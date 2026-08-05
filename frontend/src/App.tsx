import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { SearchJobProvider } from "./contexts/SearchJobContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppLayout } from "./components/AppLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import AccesoDenegadoPage from "./pages/AccesoDenegadoPage";
import ImportarPage from "./pages/ImportarPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ConsultarPage from "./pages/ConsultarPage";
import BulkSearchPage from "./pages/BulkSearchPage";
import CasosPage from "./pages/CasosPage";
import CasoDetailPage from "./pages/CasoDetailPage";
import ConfiguracionPage from "./pages/ConfiguracionPage";
import NoEncontradosPage from "./pages/NoEncontradosPage";
import ProjectDashboardPage from "./pages/ProjectDashboardPage";
import AgendaView from "./pages/AgendaView";
import HelpPage from "./pages/HelpPage";
import NotFound from "./pages/NotFound";
import AdminDashboard from "./pages/AdminDashboard";
import LandingPage from "./pages/LandingPage";
import TableroIAPage from "./pages/TableroIAPage";

import { MyTasksView } from "./components/MyTasksView";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider>
        <Sonner />
        <Toaster />
        <AuthProvider>
          <SearchJobProvider>
            <BrowserRouter>
              <Routes>
              {/* Rutas públicas */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage initialView="login" />} />
              <Route path="/register-company" element={<LoginPage initialView="register" />} />
              <Route path="/register" element={<Navigate to="/register-company" replace />} />
              <Route path="/forgot-password" element={<LoginPage initialView="forgot_password" />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/acceso-denegado" element={<AccesoDenegadoPage />} />
              
              {/* Rutas protegidas */}
              <Route element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }>
                <Route path="/importar" element={<ImportarPage />} />
                
                {/* Nuevas rutas de Experiencia de Usuario */}
                <Route path="/mis-tareas" element={<MyTasksView />} />
                <Route path="/tablero-ia" element={<TableroIAPage />} />
                
                <Route path="/consultar" element={<ConsultarPage />} />
                <Route path="/consultar-nombre" element={<BulkSearchPage />} />
                <Route path="/casos" element={<CasosPage />} />
                <Route path="/casos/:radicado" element={<CasoDetailPage />} />
                <Route path="/casos/id/:id" element={<CasoDetailPage />} />
                <Route path="/proyectos" element={<ProjectDashboardPage />} />
                <Route path="/agenda" element={<AgendaView />} />
                <Route path="/ayuda" element={<HelpPage />} />
                <Route path="/no-encontrados" element={<NoEncontradosPage />} />
                <Route path="/configuracion" element={
                  <ProtectedRoute requiredPermission="importar">
                    <ConfiguracionPage />
                  </ProtectedRoute>
                } />
                <Route path="/admin" element={
                  <ProtectedRoute>
                    <AdminDashboard />
                  </ProtectedRoute>
                } />
              </Route>
              
              <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </SearchJobProvider>
        </AuthProvider>
      </ThemeProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
