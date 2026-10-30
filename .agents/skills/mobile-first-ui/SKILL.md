---
name: mobile-first-ui
description: Universal mobile-first responsive design principles, touch target safety, typography collision prevention, and smooth viewport/gesture standards for web applications.
---

# Universal Mobile-First UI & Responsive Engineering Skill

Use this skill whenever designing, reviewing, or implementing user interfaces, responsive layouts, navigation bars, cards, modal drawers, and typography for mobile and desktop screens.

---

## 1. Typography & Text Collision Prevention

- **Heading Line Heights on Mobile:**
  - Never use ultra-tight line heights (`leading-[0.9]`, `leading-none`) on multi-line text.
  - On screens $\le$ 640px (mobile), titles frequently wrap across multiple lines. Always use `leading-[1.1]` to `leading-[1.2]` on mobile, scaling up to `sm:leading-[0.95]` on desktop.
- **Text Balance:** Use CSS `text-wrap: balance` (Tailwind `text-balance`) for section headlines and titles to eliminate awkward single-word lines.
- **Fluid & Responsive Scaling:**
  - Display / Hero: `text-3xl sm:text-5xl md:text-6xl lg:text-7xl`
  - Section Titles: `text-xl sm:text-3xl md:text-4xl`
  - Subheadings: `text-sm sm:text-base`
  - Caption / Metadata: `text-xs sm:text-sm`

---

## 2. Touch Target & Navigation Safety

- **Minimum 44×44px Touch Targets:**
  - Every interactive button, menu toggle, icon trigger, and form input must have at least a 44×44px touch footprint to prevent mis-taps on mobile devices.
- **Header Action Bar Safety:**
  - When placing centered brand logos with absolute positioning (`absolute left-1/2 -translate-x-1/2`), enforce max-widths or icon-only compact views on the left/right action bars to prevent element collision on narrow devices ($< 390px$).
- **Sticky Actions (Bottom CTA):**
  - For critical conversion flows (e.g. checkout, add to cart, book now, submit form), provide a fixed bottom action bar on mobile (`fixed bottom-0 left-0 right-0 p-4 bg-background border-t pb-[env(safe-area-inset-bottom)]`) for effortless one-thumb tapping.

---

## 3. Viewport & Scroll Safety

- **Dynamic Viewport Heights:**
  - Use `min-h-[100dvh]` or `min-h-[100svh]` rather than `100vh` to account for mobile browser URL navigation bars dynamically expanding/collapsing.
- **Safe Area Insets:**
  - Always support iOS / Android safe area margins for bottom navigation and floating modals: `pb-[calc(1rem+env(safe-area-inset-bottom,0px))]`.
- **Horizontal Scroll Prevention:**
  - Apply `overflow-x-clip` or `overflow-x-hidden` on main layout containers to eliminate unintended horizontal page shifting/jitter on swipe gestures.

---

## 4. Mobile Layout & Grid Progression

- **Grid Scaling:**
  - Default: 1 column on mobile (`grid-cols-1` or `grid-cols-2` with compact `gap-3`).
  - Tablet: `sm:grid-cols-2 md:grid-cols-3`.
  - Desktop: `lg:grid-cols-4 xl:grid-cols-5`.
- **Modal vs. Bottom Sheet Drawer:**
  - On desktop: Centered dialog modal (`max-w-lg mx-auto`).
  - On mobile: Slide-up bottom sheet drawer with swipe-to-dismiss gesture for superior ergonomics.
