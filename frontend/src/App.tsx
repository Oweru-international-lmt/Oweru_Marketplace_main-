import { MotionConfig } from 'motion/react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, HomeRedirect, RequireAuth, RequirePasswordChange, RequirePermission } from './auth/guards'
import { AppLayout } from './layouts/AppLayout'
import { AuthLayout } from './layouts/AuthLayout'
import { AccountPage } from './pages/AccountPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ConfirmLinkPage } from './pages/ConfirmLinkPage'
import { EmailConfirmPage } from './pages/EmailConfirmPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
import { ManagementDeletionsPage } from './pages/ManagementDeletionsPage'
import { ManagementRolesPage } from './pages/ManagementRolesPage'
import { ManagementStaffPage } from './pages/ManagementStaffPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
              <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
              <Route path="/forgot-password" element={<GuestOnly><ForgotPasswordPage /></GuestOnly>} />
              {/* Paths fixed by the backend's PASSWORD_RESET_URL, EMAIL_CONFIRMATION_URL and CONFIRMATION_URL. */}
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/confirm-email" element={<EmailConfirmPage />} />
              <Route path="/confirm" element={<ConfirmLinkPage />} />
              <Route path="/change-password" element={<RequirePasswordChange><ChangePasswordPage /></RequirePasswordChange>} />
            </Route>
            <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
              <Route path="/account" element={<AccountPage />} />
              <Route
                path="/management/roles"
                element={<RequirePermission permission="authorization.view"><ManagementRolesPage /></RequirePermission>}
              />
              <Route
                path="/management/staff"
                element={<RequirePermission permission="authorization.view"><ManagementStaffPage /></RequirePermission>}
              />
              <Route
                path="/management/deletion-requests"
                element={<RequirePermission permission="account.manage"><ManagementDeletionsPage /></RequirePermission>}
              />
            </Route>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </MotionConfig>
  )
}
