import aerialLarge from '../assets/photos/dar-aerial-1200.webp'
import aerialSmall from '../assets/photos/dar-aerial-720.webp'
import coastLarge from '../assets/photos/dar-coast-1200.webp'
import coastSmall from '../assets/photos/dar-coast-720.webp'
import sunsetLarge from '../assets/photos/dar-sunset-1200.webp'
import sunsetSmall from '../assets/photos/dar-sunset-720.webp'

// Unsplash photos of Dar es Salaam (free Unsplash licence). Credits shown in the panel.
export type Scene = {
  id: 'login' | 'register' | 'recovery'
  small: string
  large: string
  credit: string
  headlineKey: string
}

const SCENES: Record<Scene['id'], Scene> = {
  login: { id: 'login', small: sunsetSmall, large: sunsetLarge, credit: 'Ali Mkumbwa', headlineKey: 'panel.login' },
  register: { id: 'register', small: coastSmall, large: coastLarge, credit: 'Yoel Winkler', headlineKey: 'panel.register' },
  recovery: { id: 'recovery', small: aerialSmall, large: aerialLarge, credit: 'Ali Mkumbwa', headlineKey: 'panel.recovery' },
}

export function sceneFor(pathname: string): Scene {
  if (pathname.startsWith('/register')) return SCENES.register
  if (pathname.startsWith('/forgot-password') || pathname.startsWith('/reset-password')) return SCENES.recovery
  return SCENES.login
}
