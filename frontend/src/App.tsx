import { MotionConfig } from 'motion/react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, HomeRedirect, RequireAuth } from './auth/guards'
import { AuthLayout } from './layouts/AuthLayout'
import { AccountPage } from './pages/AccountPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
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
              {/* Path fixed by the backend's PASSWORD_RESET_URL. */}
              <Route path="/reset-password" element={<ResetPasswordPage />} />
            </Route>
            <Route path="/account" element={<RequireAuth><AccountPage /></RequireAuth>} />
            <Route path="/" element={<HomeRedirect />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </MotionConfig>
  )
}
