import type { Transition, Variants } from "motion/react";

/**
 * Curvas e variantes compartilhadas para manter todo o movimento do app
 * coerente. Tudo aqui respeita `prefers-reduced-motion` nos componentes que
 * usam `useReducedMotion` do motion.
 */

export const easeOut: Transition["ease"] = [0.16, 1, 0.3, 1];
export const easeSpring: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 26,
  mass: 0.9,
};

/** Container que escalona a entrada dos filhos. */
export const staggerContainer = (stagger = 0.06, delay = 0): Variants => ({
  hidden: {},
  show: {
    transition: { staggerChildren: stagger, delayChildren: delay },
  },
});

/** Item que sobe e aparece — par natural do staggerContainer. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: easeOut },
  },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.4, ease: easeOut } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.35, ease: easeOut },
  },
};

/** Transição de página (usada com AnimatePresence, mode="wait"). */
export const pageTransition: Variants = {
  hidden: { opacity: 0, y: 10, filter: "blur(4px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.45, ease: easeOut },
  },
  exit: {
    opacity: 0,
    y: -8,
    filter: "blur(4px)",
    transition: { duration: 0.25, ease: easeOut },
  },
};
