// The API refuses files over MEDIA_MAX_UPLOAD_BYTES (5 MB by default) and
// checks the real content type; this only catches the obvious cases early.
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024

export const PHOTO_TYPES = ['image/jpeg', 'image/png']
export const EVIDENCE_TYPES = ['image/jpeg', 'image/png', 'application/pdf']

export type FileProblem = { kind: 'size' | 'type'; name: string }

export function firstFileProblem(files: File[], types: string[]): FileProblem | null {
  for (const file of files) {
    if (!types.includes(file.type)) return { kind: 'type', name: file.name }
    if (file.size > MAX_UPLOAD_BYTES) return { kind: 'size', name: file.name }
  }
  return null
}

// The free check and complaints take WhatsApp numbers from anywhere; the API
// accepts +<country><number> and turns 07xx / 06xx into +255.
export function looksLikeWhatsApp(value: string): boolean {
  const number = value.replace(/[\s()-]/g, '').replace(/^00/, '+')
  return /^0[67]\d{8}$/.test(number) || /^\+[1-9]\d{7,14}$/.test(number)
}
