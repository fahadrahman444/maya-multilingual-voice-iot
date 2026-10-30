---
name: modern-web-guidance
description: Universal best practices for modern web development in React 18/19, Next.js, Framer Motion, Tailwind CSS, and TanStack React Query.
---

# Universal Modern Web Development Skill

Use this skill when developing, refactoring, or optimizing frontend components across modern React, Next.js, and web applications.

## 1. UI Architecture & Animations
- **Framer Motion Standards**: Use `motion.div` and `AnimatePresence` for all dynamic UI interactions (modals, drawers, expandable accordions, toast notifications).
- **Smooth Easing**: Use standard cubic-bezier timing functions (`easeOut` or `[0.22, 1, 0.36, 1]`) for clean, professional movement.
- **Performance & Backdrop Blur**:
  - Never animate `opacity` directly on elements with `backdrop-filter: blur`. Browsers re-render blur layers on every frame, causing frame drops.
  - Separate static background blurs from dynamic opacity overlays or use solid translucent backgrounds (`bg-slate-900/80`, `bg-white/95`).
- **Modal Portals**: Always render full-screen overlays, slide-out drawers, and modals using `createPortal(..., document.body)` with an SSR/hydration safety check.

## 2. Aesthetics & Design System
- **Color Palette & Clean Surfaces**: Crisp, high-contrast palette (Slate/Zinc neutrals, distinct primary accents, Emerald success badges, Amber warnings, Rose danger states).
- **Typography & Layout**: Clear visual hierarchy, readable typography, responsive layouts from mobile devices up to desktop monitors.
- **Avoid Heavy Glassmorphism**: Do not use heavy glassmorphism effects or excessive blur filters. Focus on crisp borders, clean solid surfaces, and subtle elevation shadows.

## 3. Data Fetching, Mutations & Concurrency
- **React Query (`useQuery` / `useMutation`)**:
  - Always configure queries with `staleTime: 1000 * 60 * 5` (5 min default) and `refetchOnWindowFocus: false`.
  - Invalidate relevant query keys (`queryClient.invalidateQueries({ queryKey: [...] })`) upon successful mutation.
- **Double-Click & Race Condition Prevention**:
  - State-mutating buttons (e.g., submit forms, checkout, bookings, payments) must disable themselves and check local loading states (`if (loading) return`).
