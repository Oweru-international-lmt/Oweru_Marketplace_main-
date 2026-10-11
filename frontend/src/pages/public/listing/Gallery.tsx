import { AnimatePresence, motion } from 'motion/react'
import { useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ArrowLeftIcon, ChevronLeftIcon, ChevronRightIcon, ImageIcon } from '../../../components/icons'

type Photo = { position: number; url: string }

// Phones (M8 reference): edge to edge, a round back button, swipe and dots.
function BackButton({ to }: { to: string }) {
  const { t } = useTranslation()
  return (
    <Link
      to={to}
      aria-label={t('listing.back')}
      className="absolute top-4 left-4 z-10 grid size-11 place-items-center rounded-full bg-white/95 text-navy shadow-lg backdrop-blur sm:hidden"
    >
      <ArrowLeftIcon className="size-5" />
    </Link>
  )
}

// Swipe or use the arrows; the thumbnail strip jumps to any photo.
export function Gallery({ photos, backTo }: { photos: Photo[]; backTo?: string }) {
  const { t } = useTranslation()
  const [[index, direction], setState] = useState<[number, number]>([0, 0])
  const total = photos.length

  function go(step: number) {
    if (total < 2) return
    setState(([current]) => [(current + step + total) % total, step])
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowRight') go(1)
    if (event.key === 'ArrowLeft') go(-1)
  }

  if (total === 0) {
    return (
      <div className="relative grid aspect-[5/4] place-items-center bg-mist text-muted sm:aspect-[16/10] sm:rounded-xl">
        {backTo && <BackButton to={backTo} />}
        <span className="flex flex-col items-center gap-2 text-sm">
          <ImageIcon className="size-9" />
          {t('market.noPhotos')}
        </span>
      </div>
    )
  }

  return (
    <div>
      <div
        role="region"
        aria-roledescription="carousel"
        aria-label={t('listing.photo', { index: index + 1, total })}
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="relative aspect-[5/4] overflow-hidden bg-navy sm:aspect-[16/10] sm:rounded-xl"
      >
        {backTo && <BackButton to={backTo} />}
        <AnimatePresence initial={false} custom={direction}>
          <motion.img
            key={photos[index].url}
            src={photos[index].url}
            alt={t('listing.photo', { index: index + 1, total })}
            custom={direction}
            variants={{
              enter: (dir: number) => ({ x: dir >= 0 ? '12%' : '-12%', opacity: 0 }),
              center: { x: 0, opacity: 1 },
              exit: (dir: number) => ({ x: dir >= 0 ? '-12%' : '12%', opacity: 0 }),
            }}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ x: { type: 'spring', stiffness: 300, damping: 34 }, opacity: { duration: 0.25 } }}
            drag={total > 1 ? 'x' : false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.5}
            onDragEnd={(_, info) => {
              if (info.offset.x < -60 || info.velocity.x < -400) go(1)
              else if (info.offset.x > 60 || info.velocity.x > 400) go(-1)
            }}
            draggable={false}
            className="absolute inset-0 size-full cursor-grab object-cover active:cursor-grabbing"
          />
        </AnimatePresence>

        {total > 1 && (
          <>
            <ArrowButton side="left" label={t('listing.previousPhoto')} onClick={() => go(-1)} />
            <ArrowButton side="right" label={t('listing.nextPhoto')} onClick={() => go(1)} />
            <span className="absolute bottom-4 left-4 hidden rounded-full bg-navy/75 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm sm:block" aria-hidden="true">
              {index + 1} / {total}
            </span>
            {/* Phones: M8's dots, above the sheet edge that overlaps the photo. */}
            <div className="absolute inset-x-0 bottom-10 flex justify-center gap-1.5 sm:hidden" aria-hidden="true">
              {photos.map((photo, dot) => (
                <span key={photo.url} className={`h-1.5 rounded-full bg-white transition-all ${dot === index ? 'w-5' : 'w-1.5 opacity-60'}`} />
              ))}
            </div>
          </>
        )}
      </div>

      {total > 1 && (
        <div className="mt-3 hidden gap-2 overflow-x-auto pb-1 sm:flex">
          {photos.map((photo, thumb) => (
            <button
              key={photo.url}
              type="button"
              aria-label={t('listing.showPhoto', { index: thumb + 1 })}
              aria-current={thumb === index}
              onClick={() => setState(([current]) => [thumb, thumb > current ? 1 : -1])}
              className={`relative h-16 w-24 shrink-0 overflow-hidden rounded-md transition-opacity sm:h-20 sm:w-28 ${
                thumb === index ? 'opacity-100 ring-2 ring-gold ring-offset-2 ring-offset-paper' : 'opacity-60 hover:opacity-100'
              }`}
            >
              <img src={photo.url} alt="" loading="lazy" decoding="async" className="size-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function ArrowButton({ side, label, onClick }: { side: 'left' | 'right'; label: string; onClick: () => void }) {
  const Icon = side === 'left' ? ChevronLeftIcon : ChevronRightIcon
  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={label}
      whileTap={{ scale: 0.92 }}
      className={`absolute top-1/2 hidden size-11 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-navy shadow-lg backdrop-blur hover:bg-white sm:grid ${
        side === 'left' ? 'left-3' : 'right-3'
      }`}
    >
      <Icon className="size-5" />
    </motion.button>
  )
}
