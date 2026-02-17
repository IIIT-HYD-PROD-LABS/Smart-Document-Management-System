# Coding Conventions

**Analysis Date:** 2026-02-17

## Naming Patterns

**Files:**
- Page components: lowercase kebab-case with `.tsx` extension (e.g., `page.tsx`, `login/page.tsx`)
- Context files: PascalCase (e.g., `AuthContext.tsx`)
- API modules: lowercase (e.g., `api.ts`)
- All files follow Next.js App Router conventions

**Functions:**
- camelCase for all functions (e.g., `handleSubmit`, `loadDocuments`, `formatSize`)
- Handler functions prefixed with `handle` (e.g., `handleChange`, `handleDelete`, `handleUploadAll`)
- Async operations prefixed descriptively (e.g., `loadStats`, `loadDocuments`)
- Utility functions clearly named for purpose (e.g., `formatSize`, `removeItem`)

**Variables:**
- camelCase for all variables and state (e.g., `email`, `documents`, `isLoading`, `uploading`)
- Boolean flags prefixed with `is` or verb form (e.g., `isLoading`, `isActive`, `isDragActive`, `uploading`)
- Collections use plural nouns (e.g., `documents`, `uploads`, `results`, `navItems`)
- State setters follow React convention: `[state, setState]` pattern

**Types and Interfaces:**
- PascalCase for all types and interfaces (e.g., `User`, `Stats`, `UploadItem`, `AuthContextType`)
- Suffixed with `Type` for context/complex types (e.g., `AuthContextType`)
- Enum-like objects use PascalCase keys (e.g., `categoryColors`, `categoryEmoji`)
- Record types used for mapped objects (e.g., `Record<string, string>`, `Record<string, number>`)

## Code Style

**Formatting:**
- No explicit formatter config found (no .eslintrc or .prettierrc)
- TypeScript strict mode enabled in `tsconfig.json`
- Consistent 4-space indentation observed throughout
- Max line length appears unconstrained (lines up to 150+ characters)

**Linting:**
- Next.js lint configured: `npm run lint` command available
- TypeScript strict: `true` - enforces type safety
- JSX preserved in tsconfig for proper React/Next.js handling

## Import Organization

**Order:**
1. React and Next.js hooks/utilities (e.g., `import { useEffect, useState }`)
2. External third-party libraries (e.g., `import { motion } from "framer-motion"`)
3. UI/Icon libraries (e.g., `import { FiHome, FiUpload } from "react-icons/fi"`)
4. Application-specific imports using path aliases (e.g., `import { documentsApi } from "@/lib/api"`)
5. Next.js utilities (e.g., `import Link from "next/link"`)

**Path Aliases:**
- `@/*` maps to `./src/*` (defined in `tsconfig.json`)
- All internal imports use `@/` prefix (e.g., `@/lib/api`, `@/context/AuthContext`)
- No relative imports in cross-module imports - always use `@/`

**Example pattern from `src/app/login/page.tsx`:**
```typescript
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { FiMail, FiLock, FiArrowRight } from "react-icons/fi";
import Link from "next/link";
```

## Error Handling

**Patterns:**
- Try-catch blocks for async API calls with silent failure recovery
- Fallback states on error (e.g., empty arrays, null values)
- Toast notifications for user-facing errors (error messages extracted from API response)
- Graceful degradation with default values:
  ```typescript
  try {
    const res = await documentsApi.getStats();
    setStats(res.data);
  } catch {
    setStats({ total_documents: 0, category_distribution: {}, status_distribution: {}, recent_documents: [] });
  }
  ```
- HTTP interceptor in `api.ts` handles 401 redirects automatically
- Error details accessed via `err.response?.data?.detail` pattern

## Logging

**Framework:** No explicit logging library - uses browser console if needed

**Patterns:**
- No console.log statements found in examined code
- UI feedback via `react-hot-toast` for all user notifications:
  - Success: `toast.success(message)`
  - Error: `toast.error(message)`
- Toast configuration centralized in `src/app/layout.tsx` with custom styling

## Comments

**When to Comment:**
- Section dividers with comment blocks (e.g., `// ──── Auth API ────`, `{/* Header */}`)
- Minimal inline comments - code is self-documenting
- Comments used to separate logical sections in long files
- No JSDoc/TSDoc comments found - type annotations serve as documentation

**Example section divider pattern from `src/lib/api.ts`:**
```typescript
// ──── Auth API ────
export const authApi = {
  // ...
}

// ──── Documents API ────
export const documentsApi = {
  // ...
}
```

## Function Design

**Size:**
- Functions kept relatively small (10-50 lines typical)
- Page components can be larger due to JSX content (100-170 lines observed)
- Utility functions extracted when reusable (e.g., `formatSize` in upload page)

**Parameters:**
- Functions accept individual parameters or single object parameter
- API methods use arrow functions with destructured parameters:
  ```typescript
  register: (data: { email: string; username: string; password: string; full_name?: string }) =>
    api.post("/auth/register", data)
  ```
- Event handlers use React event types explicitly: `(e: React.FormEvent)`, `(e: React.ChangeEvent<HTMLInputElement>)`

**Return Values:**
- Async functions return Promises (Promise<void> for mutations, Promise<AxiosResponse> for API calls)
- Event handlers return void
- No explicit return statements for simple state updates
- Callbacks return void unless data extraction needed

## Module Design

**Exports:**
- Named exports for context hooks (e.g., `export function AuthProvider`, `export function useAuth`)
- Default exports for page components and contexts
- API modules use named exports for organized groups:
  ```typescript
  export const authApi = { /* ... */ }
  export const documentsApi = { /* ... */ }
  export default api;
  ```

**Barrel Files:**
- No barrel files (index.ts re-exports) found
- Each module imported directly by path

## CSS and Styling

**Framework:** Tailwind CSS for all styling

**Approach:**
- Utility-first Tailwind classes applied directly to JSX elements
- Custom utilities defined in `src/app/globals.css` using `@layer utilities`
- No CSS modules or component-scoped styles
- Responsive design with Tailwind breakpoints (sm, md, lg)

**Custom utilities in globals.css:**
- `.glass` - glassmorphism backdrop effect
- `.glass-card` - enhanced glass effect for cards with hover states
- `.gradient-text` - gradient text effect
- `.bg-mesh` - animated mesh background gradient
- `.btn-primary` - primary button styling
- `.btn-ghost` - ghost button styling
- `.input-field` - form input base styling

**Color system:**
- Indigo/purple primary color: `primary-500` (#6366f1)
- Tailwind color palette extended in `tailwind.config.ts` with custom `primary` and `surface` colors
- Semantic color usage: `emerald` (success), `amber` (warning), `red` (danger)
- All dark theme (bg-surface-900, text-white)

## State Management

**Patterns:**
- React Context API for global auth state (`AuthContext.tsx`)
- Local component state with `useState` for UI state (loading, form inputs, filters)
- useCallback for memoized handlers to prevent unnecessary re-renders
- useEffect with dependency arrays for data fetching
- No Redux or additional state management libraries

**Context usage:**
```typescript
// AuthContext provides: user, token, isLoading, login, register, logout
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
```

## Performance Considerations

**Observed patterns:**
- Lazy rendering with AnimatePresence for list items
- Framer Motion for smooth animations
- useCallback for expensive handlers
- Conditional rendering to avoid unnecessary re-renders
- No pagination mechanism found - getAll() retrieves with skip/limit but all-at-once display

## Next.js Specific

**App Router conventions:**
- `"use client"` directive on interactive components
- Layout files structure page hierarchy
- Nested routing via directory structure
- Dynamic segments for filtered/detail views
- No API routes defined in frontend codebase
