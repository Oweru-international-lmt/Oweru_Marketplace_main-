import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

// Register once; components import gsap and ScrollTrigger from here.
gsap.registerPlugin(useGSAP, ScrollTrigger)

// Animations run only for people who haven't asked for reduced motion.
export const MOTION_OK = '(prefers-reduced-motion: no-preference)'

export { gsap, ScrollTrigger, useGSAP }
