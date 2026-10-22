interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_SUPPORT_WHATSAPP?: string
  readonly VITE_ESRI_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
