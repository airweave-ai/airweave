import { useEffect } from 'react';
import { ThemeProvider } from '@/lib/theme-provider';
import { Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';

import DashboardLayout from '@/components/DashboardLayout';
import Dashboard from '@/pages/Dashboard';
import CollectionDetailView from "@/pages/CollectionDetailView";
import CollectionsView from "@/pages/CollectionsView";

import AuthProviders from '@/pages/AuthProviders';
import SemanticMcp from '@/pages/SemanticMcp';
import { useCollectionsStore } from '@/lib/stores';
import { NotFound } from '@/pages/NotFound';
import { AuthGuard } from '@/components/AuthGuard';
import Login from '@/pages/Login';
import Callback from '@/pages/Callback';
import { protectedPaths, publicPaths } from '@/constants/paths';
import { AuthCallback } from '@/pages/AuthCallback';
import { OrganizationSettingsUnified } from '@/pages/organization/OrganizationSettingsUnified';
import Onboarding from '@/pages/Onboarding';
import BillingSuccess from '@/pages/BillingSuccess';
import BillingCancel from '@/pages/BillingCancel';
import BillingSetup from '@/pages/BillingSetup';
import BillingPortal from '@/pages/BillingPortal';

function App() {
  // Initialize collections event listeners when the app loads
  useEffect(() => {
    const unsubscribe = useCollectionsStore.getState().subscribeToEvents();
    return unsubscribe;
  }, []);

  return (
    <ThemeProvider defaultTheme="dark" storageKey="airweave-ui-theme">
      <Routes>
        {/* Public routes */}
        <Route path={publicPaths.login} element={<Login />} />
        <Route path={publicPaths.callback} element={<Callback />} />
        <Route path={publicPaths.semanticMcp} element={<SemanticMcp />} />
        <Route path={publicPaths.onboarding} element={<Onboarding />} />
        <Route path={publicPaths.billingSuccess} element={<BillingSuccess />} />
        <Route path={publicPaths.billingCancel} element={<BillingCancel />} />

        {/* Auth callback routes - OUTSIDE of DashboardLayout */}
        {/* <Route path="/auth/callback/:short_name" element={<AuthCallback />} /> */}
        <Route path="/auth/callback" element={<AuthCallback />} />

        {/* Protected routes */}
        <Route element={<AuthGuard><DashboardLayout /></AuthGuard>}>
          <Route path={protectedPaths.dashboard} element={<Dashboard />} />
          <Route path={protectedPaths.collections} element={<CollectionsView />} />
          <Route path={protectedPaths.collectionDetail} element={<CollectionDetailView />} />
          <Route path={protectedPaths.apiKeys} />
          <Route path={protectedPaths.authProviders} element={<AuthProviders />} />

          {/* Organization routes */}
          <Route path="/organization/settings" element={<OrganizationSettingsUnified />} />

          {/* Billing routes */}
          <Route path="/billing/setup" element={<BillingSetup />} />
          <Route path="/billing/portal" element={<BillingPortal />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster
        richColors
        position="top-right"
        expand={false}
        closeButton
      />
    </ThemeProvider>
  );
}

export default App;
