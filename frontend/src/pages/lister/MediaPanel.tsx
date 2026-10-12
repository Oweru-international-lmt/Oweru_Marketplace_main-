import { AnimatePresence, motion } from 'motion/react'
import { useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CloseIcon, ImageIcon } from '../../components/icons'
import { errorMessage } from '../../lib/errors'
import { firstFileProblem, PHOTO_TYPES } from '../../lib/files'
import { listerApi, MAXIMUM_PHOTOS, MINIMUM_PHOTOS } from '../../lib/listerApi'
import { withUrls, type Photo } from './rows'

// After L4's media card: a dashed drop zone with an icon tile, a line of
// rules and a soft "Add image" button, then the gallery as square tiles with
// "Main image" on the first. Each photo is uploaded as soon as it is chosen.
export function MediaPanel({ listingId, photos, onChange }: { listingId: string; photos: Photo[]; onChange: (photos: Photo[]) => void }) {
  const { t } = useTranslation()
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const full = photos.length + pending >= MAXIMUM_PHOTOS

  async function upload(files: File[]) {
    setError(null)
    const room = MAXIMUM_PHOTOS - photos.length - pending
    const chosen = files.slice(0, Math.max(0, room))
    if (chosen.length === 0) return
    const problem = firstFileProblem(chosen, PHOTO_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setPending((count) => count + chosen.length)
    let current = photos
    for (const file of chosen) {
      try {
        const added = await listerApi.addPhoto(listingId, file)
        const [withUrl] = await withUrls([added])
        current = [...current, withUrl]
        onChange(current)
      } catch (caught) {
        setError(errorMessage(t, caught))
      } finally {
        setPending((count) => count - 1)
      }
    }
  }

  async function remove(photo: Photo) {
    setError(null)
    try {
      await listerApi.removePhoto(listingId, photo.id)
      onChange(photos.filter((item) => item.id !== photo.id))
    } catch (caught) {
      setError(errorMessage(t, caught))
    }
  }

  async function makeMain(photo: Photo) {
    setError(null)
    const order = [photo, ...photos.filter((item) => item.id !== photo.id)]
    onChange(order)
    try {
      const saved = await listerApi.reorderPhotos(listingId, order.map((item) => item.id))
      const urls = new Map(order.map((item) => [item.id, item.url]))
      onChange([...saved].sort((a, b) => a.position - b.position).map((item) => ({ ...item, url: urls.get(item.id) ?? null })))
    } catch (caught) {
      onChange(photos)
      setError(errorMessage(t, caught))
    }
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          if (!full) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (!full) void upload(Array.from(event.dataTransfer.files))
        }}
        className={`flex flex-col items-center rounded-md border-[1.5px] border-dashed px-5 py-6 text-center transition-colors ${
          dragging ? 'border-gold bg-gold/[0.06]' : 'border-[#c9cfd9]'
        }`}
      >
        <span className="grid size-10 place-items-center rounded-md bg-gold text-white">
          <ImageIcon className="size-5" />
        </span>
        <p className="mt-4 text-[15px] text-navy">{t('lister.media.drop')}</p>
        <p className="mt-1 text-[13px] text-muted">{t('lister.media.rules', { max: MAXIMUM_PHOTOS })}</p>
        <input
          ref={input}
          id={id}
          type="file"
          accept={PHOTO_TYPES.join(',')}
          multiple
          className="sr-only"
          disabled={full}
          onChange={(event) => {
            void upload(Array.from(event.target.files ?? []))
            event.target.value = ''
          }}
        />
        <label
          htmlFor={id}
          className={`mt-5 inline-flex h-10 min-w-[160px] items-center justify-center rounded-md px-6 text-[14px] transition-colors ${
            full ? 'cursor-not-allowed bg-mist/50 text-muted' : 'cursor-pointer bg-gold/12 text-[#9a6c12] hover:bg-gold/20'
          }`}
        >
          {full ? t('lister.media.full') : t('lister.media.add')}
        </label>
      </div>

      {(photos.length > 0 || pending > 0) && (
        <ul className="mt-4 flex gap-2.5 overflow-x-auto pb-1">
          <AnimatePresence initial={false}>
            {photos.map((photo, index) => (
              <motion.li
                key={photo.id}
                layout
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.94 }}
                transition={{ duration: 0.2 }}
                className="relative size-[140px] shrink-0 overflow-hidden rounded-md bg-mist"
              >
                {photo.url ? (
                  <img src={photo.url} alt={t('lister.media.photoAlt', { number: index + 1 })} className="size-full object-cover" />
                ) : (
                  <span className="grid size-full place-items-center text-muted">
                    <ImageIcon className="size-6" />
                  </span>
                )}
                {index === 0 && (
                  <span className="absolute inset-x-1 top-1 rounded-[3px] bg-white py-1 text-center text-[12px] text-navy">{t('lister.media.main')}</span>
                )}
                <span className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-1 bg-gradient-to-t from-navy/85 to-navy/0 px-2 pt-5 pb-1.5">
                  {index > 0 ? (
                    <button type="button" onClick={() => void makeMain(photo)} className="rounded px-1 text-[12px] text-white underline-offset-2 hover:underline">
                      {t('lister.media.makeMain')}
                    </button>
                  ) : (
                    <span className="px-1 text-[12px] text-white">{t('lister.media.number', { number: 1 })}</span>
                  )}
                  <button
                    type="button"
                    onClick={() => void remove(photo)}
                    aria-label={t('lister.media.remove', { number: index + 1 })}
                    className="grid size-7 place-items-center rounded-full text-white/85 hover:bg-white/15 hover:text-white"
                  >
                    <CloseIcon className="size-3.5" />
                  </button>
                </span>
              </motion.li>
            ))}
            {Array.from({ length: pending }, (_, index) => (
              <li key={`pending-${index}`} className="grid size-[140px] shrink-0 place-items-center rounded-md bg-paper ring-1 ring-mist">
                <span className="size-5 animate-spin rounded-full border-2 border-gold/25 border-t-gold" aria-hidden="true" />
                <span className="sr-only">{t('lister.media.uploading')}</span>
              </li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      <p className={`mt-3 text-[12.5px] ${photos.length >= MINIMUM_PHOTOS ? 'text-success' : 'text-muted'}`} aria-live="polite">
        {t('lister.media.count', { count: photos.length, min: MINIMUM_PHOTOS })}
      </p>
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
