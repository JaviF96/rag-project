import type { Transition, Variants } from 'motion/react'
import { useReducedMotion } from 'motion/react'

/* ---------------------------------------------------------------------------
   A single motion vocabulary.

   Everything on the page animates with one of these springs, so entrances,
   layout shifts and chart marks all feel like the same object moving. Durations
   are never hand-tuned per component.
--------------------------------------------------------------------------- */

/** Default for entrances: settles quickly, barely overshoots. */
export const spring: Transition = {
  type: 'spring',
  stiffness: 260,
  damping: 30,
  mass: 0.9,
}

/** Softer and slower, for large surfaces (cards, panels, scene blocks). */
export const springSoft: Transition = {
  type: 'spring',
  stiffness: 170,
  damping: 26,
  mass: 1,
}

/** Snappy, for press states and small affordances. */
export const springTight: Transition = {
  type: 'spring',
  stiffness: 420,
  damping: 32,
}

/** Chart marks grow rather than spring, so values never overshoot their scale. */
export const draw: Transition = { duration: 0.62, ease: [0.22, 1, 0.36, 1] }

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: spring },
}

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.4 } },
}

/** Parent variant: children run in sequence via their own `fadeUp`. */
export function stagger(gap = 0.06, delay = 0): Variants {
  return {
    hidden: {},
    show: { transition: { staggerChildren: gap, delayChildren: delay } },
  }
}

/**
 * Collapses every transform-based animation to a plain fade when the visitor
 * asks for reduced motion. Returns props to spread onto a `motion` element.
 */
export function useMotionSafe() {
  const reduced = useReducedMotion()
  return {
    reduced: !!reduced,
    variants: reduced ? fadeIn : fadeUp,
    /** Chart marks: skip the grow entirely rather than animate a scale. */
    markTransition: reduced ? { duration: 0 } : draw,
    stagger: (gap = 0.06, delay = 0) => (reduced ? stagger(0, 0) : stagger(gap, delay)),
  }
}
