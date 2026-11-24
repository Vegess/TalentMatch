import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { I18nProvider } from "./lib/i18n";
import { ToastProvider } from "./components/Toast";
import { CheckoutProvider } from "./components/Checkout";
import { AppShell, PublicLayout, RequireRole } from "./components/Layout";
import { Loading } from "./components/ui";
import Home from "./pages/public/Home";
import Pricing from "./pages/public/Pricing";
import { ForgotPassword, Login, Register, ResetPassword } from "./pages/public/Auth";
import { Freelancers, Jobs, Services } from "./pages/public/Browse";
import { FreelancerDetail, JobDetail, NotFound, ServiceDetail } from "./pages/public/Details";

// Signed-in areas are split into their own chunks so the public site loads fast.
const C = lazy(() => import("./pages/client/Client").then((m) => ({ default: m.ClientDashboard })));
const CJobs = lazy(() => import("./pages/client/Client").then((m) => ({ default: m.MyJobs })));
const CNew = lazy(() => import("./pages/client/Client").then((m) => ({ default: m.NewJob })));
const CManage = lazy(() => import("./pages/client/Client").then((m) => ({ default: m.ManageJob })));
const CBilling = lazy(() => import("./pages/client/Client").then((m) => ({ default: m.Billing })));
const F = lazy(() => import("./pages/freelancer/Freelancer").then((m) => ({ default: m.FreelancerDashboard })));
const FProfile = lazy(() => import("./pages/freelancer/Freelancer").then((m) => ({ default: m.Profile })));
const FServices = lazy(() => import("./pages/freelancer/Freelancer").then((m) => ({ default: m.MyServices })));
const FWork = lazy(() => import("./pages/freelancer/Freelancer").then((m) => ({ default: m.FindWork })));
const FProposals = lazy(() => import("./pages/freelancer/Freelancer").then((m) => ({ default: m.MyProposals })));
const Messages = lazy(() => import("./pages/shared/Messages"));
const PaymentReturn = lazy(() => import("./pages/shared/PaymentReturn"));
const FPayouts = lazy(() => import("./pages/freelancer/Payouts"));
const Orders = lazy(() => import("./pages/shared/Shared").then((m) => ({ default: m.Orders })));
const OrderDetail = lazy(() => import("./pages/shared/Shared").then((m) => ({ default: m.OrderDetail })));
const Settings = lazy(() => import("./pages/shared/Shared").then((m) => ({ default: m.Settings })));
const AOverview = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.Overview })));
const AUsers = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.Users })));
const APayments = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.Payments })));
const AOrders = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.AdminOrders })));
const AJobs = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.AdminJobs })));
const AServices = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.AdminServices })));
const AAudit = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.Audit })));

const guard = (roles: ("admin" | "client" | "freelancer")[]) => <RequireRole roles={roles}><AppShell /></RequireRole>;

export default function App() {
  return <BrowserRouter>
    <I18nProvider><AuthProvider><ToastProvider><CheckoutProvider>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<Home />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="freelancers" element={<Freelancers />} />
            <Route path="freelancers/:id" element={<FreelancerDetail />} />
            <Route path="services" element={<Services />} />
            <Route path="services/:id" element={<ServiceDetail />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="jobs/:id" element={<JobDetail />} />
          </Route>
          <Route path="login" element={<Login />} />
          <Route path="register" element={<Register />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="client" element={guard(["client"])}>
            <Route index element={<C />} />
            <Route path="jobs" element={<CJobs />} />
            <Route path="jobs/new" element={<CNew />} />
            <Route path="jobs/:id" element={<CManage />} />
            <Route path="billing" element={<CBilling />} />
          </Route>
          <Route path="freelancer" element={guard(["freelancer"])}>
            <Route index element={<F />} />
            <Route path="profile" element={<FProfile />} />
            <Route path="services" element={<FServices />} />
            <Route path="jobs" element={<FWork />} />
            <Route path="proposals" element={<FProposals />} />
            <Route path="payouts" element={<FPayouts />} />
          </Route>
          <Route element={guard(["client", "freelancer", "admin"])}>
            <Route path="orders" element={<Orders />} />
            <Route path="orders/:id" element={<OrderDetail />} />
            <Route path="settings" element={<Settings />} />
            <Route path="messages" element={<Messages />} />
            <Route path="messages/:id" element={<Messages />} />
            <Route path="payments/return" element={<PaymentReturn />} />
          </Route>
          <Route path="control-room" element={guard(["admin"])}>
            <Route index element={<AOverview />} />
            <Route path="users" element={<AUsers />} />
            <Route path="payments" element={<APayments />} />
            <Route path="orders" element={<AOrders />} />
            <Route path="jobs" element={<AJobs />} />
            <Route path="services" element={<AServices />} />
            <Route path="audit" element={<AAudit />} />
          </Route>
          <Route element={<PublicLayout />}><Route path="*" element={<NotFound />} /></Route>
        </Routes>
      </Suspense>
    </CheckoutProvider></ToastProvider></AuthProvider></I18nProvider>
  </BrowserRouter>;
}
