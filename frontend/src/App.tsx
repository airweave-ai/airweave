import { Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import Dashboard from "@/pages/Dashboard";
import DashboardLayout from "@/components/DashboardLayout";
import Settings from "@/pages/Settings";
import WhiteLabel from "@/pages/WhiteLabel";
import CreateWhiteLabel from "@/pages/CreateWhiteLabel";
import { NotFound } from "@/pages/NotFound";
import SyncCreate from "@/pages/SyncCreate";
import SyncTableView from "@/pages/SyncTableView";
import ViewEditSync from "@/pages/ViewEditSync";
import Destinations from "@/pages/Destinations";
import Profile from "@/pages/Profile";
import Chat from "@/pages/Chat";
import Sources from "@/pages/Sources";
import { AuthCallback } from "./pages/AuthCallback";
import ViewEditWhiteLabel from "./pages/ViewEditWhiteLabel";
import { LoginPage } from "./pages/LoginPage";
import { CallbackPage } from "./pages/CallbackPage";
import { AuthGuard } from "./components/AuthGuard";

function App() {
  return (
    <>
      <Routes>
        <Route
          element={
            <AuthGuard>
              <DashboardLayout />
            </AuthGuard>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />

          <Route path="/sync">
            <Route index element={<SyncTableView />} />
            <Route path="create" element={<SyncCreate />} />
            <Route path=":id" element={<ViewEditSync />} />
            <Route path=":id/job/:jobId" element={<ViewEditSync />} />
          </Route>

          <Route path="/sources" element={<Sources />} />
          <Route path="/destinations" element={<Destinations />} />

          <Route path="/white-label">
            <Route index element={<WhiteLabel />} />
            <Route path="create" element={<CreateWhiteLabel />} />
            <Route path=":id" element={<ViewEditWhiteLabel />} />
          </Route>

          <Route path="/settings" element={<Settings />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:id" element={<Chat />} />
        </Route>

        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<CallbackPage />} />
        <Route path="/auth/callback/:short_name" element={<AuthCallback />} />

        {/* 404 route */}
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
