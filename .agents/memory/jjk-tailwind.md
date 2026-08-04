---
name: JJK Tailwind Layer Rule
description: Tailwind v4 restriction — @apply inside @layer utilities is forbidden.
---

## Rule

In **Tailwind v4**, `@apply` inside `@layer utilities` blocks is **not allowed** and throws:
`"Cannot apply unknown utility class"`

## Fix

Move any custom class that uses `@apply` to `@layer components` instead:

```css
/* WRONG in Tailwind v4 */
@layer utilities {
  .glass {
    @apply bg-card/60 backdrop-blur-md;  /* Error! */
  }
}

/* CORRECT */
@layer components {
  .glass {
    @apply bg-card/60 backdrop-blur-md;  /* OK */
  }
}

/* Also fine: raw CSS values in @layer utilities */
@layer utilities {
  .text-glow {
    text-shadow: 0 0 10px hsl(var(--primary) / 0.5);  /* OK */
  }
}
```

## Applied in This Project

`artifacts/jjk-dashboard/src/index.css`:
- `.glass`, `.glass-card`, `.glass-card::before` → moved to `@layer components`
- `.text-glow`, `.box-glow`, `.bg-grid-pattern` → stay in `@layer utilities` (raw CSS, no @apply)
