import { motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../components/Alert'
import { AuthHeading } from '../components/AuthHeading'
import { Button } from '../components/Button'
import { ArrowLeftIcon, MailIcon } from '../components/icons'
import { StaggerGroup, StaggerItem } from '../components/Stagger'
import { TextField } from '../components/TextField'
import { WhatsAppHelp } from '../components/WhatsAppHelp'
import { authApi } from '../lib/authApi'
import { errorMessage } from '../lib/errors'
import { emailError } from '../lib/validation'

function BackToSignIn() {
  const { t } = useTranslation()
  return (
    <Link to="/login" className="text-link inline-flex items-center gap-2 text-sm">
      <ArrowLeftIcon className="size-4" />
      {t('common.backToSignIn')}
    </Link>
  )
}

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [sentTo, setSentTo] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const error = emailError(t, email)
    setFieldError(error)
    setFormError(null)
    if (error) return

    setSubmitting(true)
    try {
      // The response never says whether an account exists for the address.
      await authApi.requestPasswordReset(email.trim())
      setSentTo(email.trim())
    } catch (error) {
      setFormError(errorMessage(t, error))
    } finally {
      setSubmitting(false)
    }
  }

  if (sentTo) {
    return (
      <StaggerGroup className="space-y-6">
        <StaggerItem>
          <motion.span
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 18 }}
            className="grid size-14 place-items-center rounded-2xl bg-gold/15 text-navy"
          >
            <MailIcon className="size-7" />
          </motion.span>
        </StaggerItem>
        <StaggerItem>
          <AuthHeading title={t('forgot.sentTitle')} subtitle={t('forgot.sentBody')} />
        </StaggerItem>
        <StaggerItem>
          <WhatsAppHelp email={sentTo} />
        </StaggerItem>
        <StaggerItem>
          <BackToSignIn />
        </StaggerItem>
      </StaggerGroup>
    )
  }

  return (
    <>
      <AuthHeading title={t('forgot.title')} subtitle={t('forgot.subtitle')} />

      <form noValidate onSubmit={handleSubmit}>
        <StaggerGroup className="space-y-5">
          {formError && (
            <StaggerItem>
              <Alert tone="error">{formError}</Alert>
            </StaggerItem>
          )}
          <StaggerItem>
            <TextField
              label={t('fields.email')}
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              placeholder={t('fields.emailPlaceholder')}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={fieldError}
            />
          </StaggerItem>
          <StaggerItem>
            <Button type="submit" loading={submitting} loadingLabel={t('forgot.submitting')}>
              {t('forgot.submit')}
            </Button>
          </StaggerItem>
          <StaggerItem className="pt-2">
            <WhatsAppHelp />
          </StaggerItem>
          <StaggerItem>
            <BackToSignIn />
          </StaggerItem>
        </StaggerGroup>
      </form>
    </>
  )
}
