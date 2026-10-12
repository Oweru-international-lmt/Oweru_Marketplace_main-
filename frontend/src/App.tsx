import { MotionConfig } from 'motion/react'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, RequireAuth, RequirePermission } from './auth/guards'
import { AppLayout } from './layouts/AppLayout'
import { AuthLayout } from './layouts/AuthLayout'
import { PublicLayout } from './layouts/PublicLayout'
import { AccountPage } from './pages/AccountPage'
import { EmailConfirmPage } from './pages/EmailConfirmPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { FullPageLoader } from './components/FullPageLoader'
import { LoginPage } from './pages/LoginPage'
import { ManagementRolesPage } from './pages/ManagementRolesPage'
import { ManagementStaffPage } from './pages/ManagementStaffPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ComplaintPage } from './pages/public/ComplaintPage'
import { ComplaintStatusPage } from './pages/public/ComplaintStatusPage'
import { FreeCheckResultPage } from './pages/public/FreeCheckResultPage'
import { FullCheckOrderPage } from './pages/public/FullCheckOrderPage'
import { FullCheckPage } from './pages/public/FullCheckPage'
import { FullChecksPage } from './pages/public/FullChecksPage'
import { HomePage } from './pages/public/HomePage'
import { ListingPage } from './pages/public/ListingPage'
import { SearchPage } from './pages/public/SearchPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { ComplaintDetailPage } from './pages/staff/ops/ComplaintDetailPage'
import { ComplaintsDeskPage } from './pages/staff/ops/ComplaintsDeskPage'
import { FullCheckDeskPage } from './pages/staff/ops/FullCheckDeskPage'
import { FullChecksDeskPage } from './pages/staff/ops/FullChecksDeskPage'
import { OverviewPage } from './pages/staff/ops/OverviewPage'
import { ResultFormPage } from './pages/staff/ops/ResultFormPage'

// The map library is only needed on this page; keep it out of the first load.
const FreeCheckPage = lazy(() => import('./pages/public/FreeCheckPage').then((module) => ({ default: module.FreeCheckPage })))

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* SRD 24 public screens: no account needed. */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/listings" element={<SearchPage />} />
              <Route path="/listings/:listingId" element={<ListingPage />} />
              {/* SRD 21 to 23 public services. Free checks and complaints need no account. */}
              <Route
                path="/free-check"
                element={
                  <Suspense fallback={<FullPageLoader inline />}>
                    <FreeCheckPage />
                  </Suspense>
                }
              />
              <Route path="/free-check/:checkId" element={<FreeCheckResultPage />} />
              <Route path="/complaints/new" element={<ComplaintPage />} />
              <Route path="/complaints/:complaintId" element={<ComplaintStatusPage />} />
              <Route path="/listings/:listingId/full-check" element={<RequireAuth><FullCheckOrderPage /></RequireAuth>} />
              <Route path="/full-checks" element={<RequireAuth><FullChecksPage /></RequireAuth>} />
              <Route path="/full-checks/:jobId" element={<RequireAuth><FullCheckPage /></RequireAuth>} />
            </Route>
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
              <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
              <Route path="/forgot-password" element={<GuestOnly><ForgotPasswordPage /></GuestOnly>} />
              {/* Paths fixed by the backend's PASSWORD_RESET_URL and EMAIL_VERIFICATION_URL. */}
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/verify-email" element={<EmailConfirmPage />} />
            </Route>
            <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
              <Route path="/account" element={<AccountPage />} />
              {/* Staff work (CMP-02 to CMP-08, PAY-13, FUL-07): Verifiers and Management. */}
              <Route path="/staff" element={<RequirePermission permission="complaint.handle"><OverviewPage /></RequirePermission>} />
              <Route path="/staff/complaints" element={<RequirePermission permission="complaint.handle"><ComplaintsDeskPage /></RequirePermission>} />
              <Route path="/staff/complaints/:complaintId" element={<RequirePermission permission="complaint.handle"><ComplaintDetailPage /></RequirePermission>} />
              <Route path="/staff/full-checks" element={<RequirePermission permission="complaint.handle"><FullChecksDeskPage /></RequirePermission>} />
              <Route path="/staff/full-checks/:jobId" element={<RequirePermission permission="complaint.handle"><FullCheckDeskPage /></RequirePermission>} />
              <Route path="/staff/full-checks/:jobId/result" element={<RequirePermission permission="complaint.handle"><ResultFormPage /></RequirePermission>} />
              <Route
                path="/management/roles"
                element={<RequirePermission permission="authorization.view"><ManagementRolesPage /></RequirePermission>}
              />
              <Route
                path="/management/staff"
                element={<RequirePermission permission="authorization.view"><ManagementStaffPage /></RequirePermission>}
              />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </MotionConfig>
  )
}
