import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { ListingCard } from '../../components/market/ListingCard'
import { ChevronRightIcon, HomeIcon, MapPinIcon, TickIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatDate } from '../../lib/format'
import { peopleApi, type ListerProfile } from '../../lib/peopleApi'

// IDV-06. After R22: a small label, the name and role centred, a large
// portrait panel beside a column of their property photos, then "About"
// with what Oweru has checked, the areas and property types, and the
// lister's public listings. No contact details: buyers enquire per listing.

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('')
}

export function ListerProfilePage() {
  const { listerId = '' } = useParams()
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [profile, setProfile] = useState<ListerProfile | null>(null)
  const [error, setError] = useState('')
  useDocumentTitle(profile?.name ?? t('listerProfile.title'))

  useEffect(() => {
    peopleApi.profile(listerId).then(setProfile, (failure) => setError(errorMessage(t, failure)))
  }, [listerId, t])

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <p className="font-serif text-2xl font-semibold text-navy">{t('listerProfile.missingTitle')}</p>
        <p className="mt-2 text-sm text-muted">{t('listerProfile.missingBody')}</p>
        <Link to="/listings" className="mt-6 inline-flex rounded-md bg-gold px-5 py-2.5 text-sm font-semibold text-navy">{t('listerProfile.browse')}</Link>
      </div>
    )
  }
  if (!profile) return <div className="mx-auto h-[60vh] max-w-5xl animate-pulse px-4 py-16"><div className="h-full rounded-2xl bg-paper" /></div>

  const agent = profile.lister_roles.includes('agent')
  const photos = profile.listings.flatMap((listing) => listing.photos.slice(0, 1).map((photo) => ({ url: photo.url, id: listing.listing_id }))).slice(0, 3)

  return (
    <div className="mx-auto max-w-5xl px-4 pt-6 pb-20 sm:px-6">
      <nav aria-label={t('listerProfile.breadcrumb')} className="flex items-center gap-1.5 text-xs text-muted">
        <Link to="/listings" className="hover:text-navy">{t('listerProfile.listings')}</Link>
        <ChevronRightIcon className="size-3.5" />
        <span className="text-navy">{t('listerProfile.title')}</span>
      </nav>

      <header className="mt-6 text-center">
        <p className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.2em] text-gold uppercase">
          <span className="size-1.5 rounded-full bg-gold" />
          {t('listerProfile.eyebrow')}
        </p>
        <motion.h1 initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-2 font-serif text-3xl font-semibold text-navy sm:text-4xl">{profile.name}</motion.h1>
        <p className="mt-1 text-sm text-muted">{agent ? t('listerProfile.agent') : t('listerProfile.owner')}</p>
      </header>

      <div className="mt-8 grid gap-4 md:grid-cols-[minmax(0,1fr)_200px]">
        <motion.div initial={reduce ? false : { opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }} className="relative grid aspect-[4/3] place-items-center overflow-hidden rounded-2xl bg-navy md:aspect-auto md:min-h-[360px]">
          <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(200,145,40,0.28),transparent_55%)]" />
          <span className="relative grid size-36 place-items-center rounded-full border-2 border-gold/60 font-serif text-5xl font-semibold text-gold-light sm:size-44">{initials(profile.name)}</span>
          {profile.is_verified && (
            <span className="absolute bottom-4 left-4 inline-flex items-center gap-1.5 rounded-full bg-white/95 px-3 py-1.5 text-xs font-medium text-navy">
              <TickIcon className="size-4 text-gold" />
              {t('levels.short.1')}
            </span>
          )}
        </motion.div>
        <div className="grid grid-cols-3 gap-3 md:grid-cols-1">
          {[0, 1, 2].map((index) => {
            const photo = photos[index]
            return photo ? (
              <motion.div key={photo.id} initial={reduce ? false : { opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + index * 0.1 }}>
                <Link to={`/listings/${photo.id}`} className="block aspect-[4/3] overflow-hidden rounded-2xl md:aspect-auto md:h-[112px]">
                  <img src={photo.url} alt="" className="size-full object-cover transition-transform duration-500 hover:scale-105" />
                </Link>
              </motion.div>
            ) : (
              <div key={index} className="grid aspect-[4/3] place-items-center rounded-2xl bg-paper text-mist md:aspect-auto md:h-[112px]"><HomeIcon className="size-6" /></div>
            )
          })}
        </div>
      </div>

      <section className="mt-10 grid gap-8 md:grid-cols-[minmax(0,1fr)_280px]">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-navy">{t('listerProfile.about', { name: profile.name.split(' ')[0] })}</h2>
          <ul className="mt-4 space-y-2.5 text-sm text-navy">
            <li className="flex gap-2.5"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-gold" />{profile.is_verified ? t('listerProfile.verified') : t('listerProfile.notVerified')}</li>
            <li className="flex gap-2.5"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-gold" />{t('listerProfile.since', { date: formatDate(profile.member_since, i18n.language) })}</li>
            <li className="flex gap-2.5"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-gold" />{t('listerProfile.active', { count: profile.listings.length })}</li>
          </ul>
          {agent && <p className="mt-5 rounded-md bg-paper px-4 py-3 text-sm leading-relaxed text-navy">{t('levels.agentNote')}</p>}
          <p className="mt-4 text-xs text-muted">{t('listerProfile.contactNote')}</p>
        </div>
        <aside className="space-y-5">
          <div>
            <h3 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('listerProfile.areas')}</h3>
            {profile.areas.length === 0 ? (
              <p className="mt-2 text-sm text-muted">{t('listerProfile.noneYet')}</p>
            ) : (
              <ul className="mt-2 flex flex-wrap gap-2">
                {profile.areas.map((area) => (
                  <li key={`${area.district}-${area.region}`} className="inline-flex items-center gap-1 rounded-full border border-mist px-3 py-1 text-xs text-navy"><MapPinIcon className="size-3.5 text-muted" />{`${area.district}, ${area.region}`}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('listerProfile.types')}</h3>
            {profile.property_types.length === 0 ? (
              <p className="mt-2 text-sm text-muted">{t('listerProfile.noneYet')}</p>
            ) : (
              <ul className="mt-2 flex flex-wrap gap-2">
                {profile.property_types.map((type) => <li key={type} className="rounded-full bg-gold/12 px-3 py-1 text-xs text-[#7a5410]">{t(`market.category.${type}`)}</li>)}
              </ul>
            )}
          </div>
        </aside>
      </section>

      {profile.listings.length > 0 && (
        <section className="mt-12">
          <h2 className="font-serif text-2xl font-semibold text-navy">{t('listerProfile.listingsTitle')}</h2>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {profile.listings.map((listing, index) => (
              <motion.div key={listing.listing_id} initial={reduce ? false : { opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ delay: Math.min(index, 5) * 0.06 }}>
                <ListingCard listing={listing} priority={index < 3} />
              </motion.div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
