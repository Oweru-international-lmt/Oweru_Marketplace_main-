interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_SUPPORT_WHATSAPP?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
