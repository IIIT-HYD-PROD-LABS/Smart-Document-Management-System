# Testing Patterns

**Analysis Date:** 2026-02-17

## Test Framework

**Status:** No testing framework currently configured

**What was found:**
- No test files (*.test.ts, *.test.tsx, *.spec.ts, *.spec.tsx) in the codebase
- No test configuration files (jest.config.js, vitest.config.ts)
- No testing dependencies in package.json
- No test scripts in package.json

**Current state:**
- No automated tests present
- Only manual testing available via `npm run dev` (development server)

## Recommended Testing Setup

If tests were to be added, the following stack would be appropriate for Next.js 14 with React 18:

**Suggested Framework:**
- **Jest** (Next.js recommended) or **Vitest** (faster alternative)
- **React Testing Library** for component testing
- **Axios mock adapter** or **MSW** (Mock Service Worker) for API mocking

**Installation example:**
```bash
npm install --save-dev jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom
```

**Config file location:** `jest.config.js` at project root

**Run commands (if configured):**
```bash
npm run test              # Run all tests
npm run test:watch       # Watch mode
npm run test:coverage    # Coverage report
```

## Existing Code Structure for Testing

**API layer (`src/lib/api.ts`):**
- Uses axios with interceptors
- Would benefit from mocking with `axios-mock-adapter` or MSW
- Export pattern allows for easy stub injection:
  ```typescript
  // Current structure
  export const authApi = { /* methods */ }
  export const documentsApi = { /* methods */ }
  export default api;
  ```

**Context layer (`src/context/AuthContext.tsx`):**
- React Context setup makes unit testing viable
- Can be wrapped in test with custom render function:
  ```typescript
  // Pattern for testing components using AuthContext
  const renderWithAuth = (component: React.ReactNode, initialUser?: User) => {
    // Provide mock AuthContext
  }
  ```

**Page components:**
- All page components use "use client" directive - suitable for React Testing Library
- Heavy use of hooks (useRouter, useAuth, useState, useEffect)
- Require mocking of:
  - `useRouter` from `next/navigation`
  - `useAuth` context
  - API calls from `@/lib/api`

## Testable Code Patterns

**Components with clear responsibilities:**

1. **Auth pages** (`login/page.tsx`, `register/page.tsx`):
   ```typescript
   // Testable units:
   // - Form validation (password length check)
   // - Login/register handler
   // - Error toast display
   // - Navigation on success
   ```

2. **Upload page** (`dashboard/upload/page.tsx`):
   ```typescript
   // Testable units:
   // - File drop handling (onDrop)
   // - Upload queue management
   // - File size formatting
   // - Upload state progression
   // - Error handling
   ```

3. **Documents page** (`dashboard/documents/page.tsx`):
   ```typescript
   // Testable units:
   // - Category filtering
   // - Delete confirmation
   // - Document loading
   // - Empty state display
   ```

4. **API layer** (`lib/api.ts`):
   ```typescript
   // Testable functions:
   // - authApi.register()
   // - authApi.login()
   // - documentsApi.upload()
   // - documentsApi.getAll()
   // - documentsApi.search()
   // - documentsApi.delete()
   // - 401 response handling
   ```

## Testing Strategy Recommendations

### Unit Tests (for lib/ modules)

**What to test:**
- API methods with mocked axios responses
- Utility functions like `formatSize()`
- Context providers and hooks in isolation

**Example test structure:**
```typescript
// src/lib/api.test.ts
import { documentsApi } from '@/lib/api';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';

describe('documentsApi', () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
  });

  afterEach(() => {
    mock.reset();
  });

  it('should fetch all documents', async () => {
    const mockData = { documents: [{ id: 1, name: 'test.pdf' }] };
    mock.onGet('/documents/all').reply(200, mockData);

    const result = await documentsApi.getAll();
    expect(result.data).toEqual(mockData);
  });
});
```

### Component Tests

**What to test:**
- User interactions (clicks, form inputs)
- Conditional rendering (loading states, empty states)
- API error handling
- Navigation on success/failure

**Mocking strategy:**
```typescript
// src/app/login/page.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LoginPage from './page';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

// Mock API
jest.mock('@/lib/api', () => ({
  authApi: {
    login: jest.fn(),
  },
}));

// Mock context
jest.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    login: jest.fn(),
    user: null,
    isLoading: false,
  }),
}));

describe('LoginPage', () => {
  it('should display login form', () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText(/you@example.com/)).toBeInTheDocument();
  });
});
```

### Integration Tests

**What to test:**
- Full auth flow (register → login → dashboard)
- Document upload → processing → display
- Search filtering

**Approach:**
- Use MSW (Mock Service Worker) for API mocking
- Test multiple components together
- Verify state changes propagate correctly

## Code Areas Lacking Tests

**High priority:**
- API request/response handling
- Auth flow (login, register, token management)
- Error states and recovery
- Form validation

**Medium priority:**
- Document filtering and search
- Upload queue management
- Analytics calculations

**Lower priority:**
- UI animations (Framer Motion)
- Toast notifications
- CSS styling (Tailwind)

## Testing Best Practices (for when tests are added)

**File organization:**
```
src/
├── app/
│   ├── login/
│   │   ├── page.tsx
│   │   └── page.test.tsx          # Co-located test
├── lib/
│   ├── api.ts
│   └── api.test.ts                # Co-located test
├── context/
│   ├── AuthContext.tsx
│   └── AuthContext.test.tsx       # Co-located test
└── __tests__/                     # Shared test utilities
    ├── setup.ts                   # Test setup
    ├── mocks.ts                   # Shared mocks
    └── render.tsx                 # Custom render with providers
```

**Naming convention:**
- Test files: `[module].test.ts` or `[module].spec.ts`
- Test functions: `it('should [behavior]')` format
- Suites: `describe('[Component/Module]', () => {})`

**Setup file (jest.config.js):**
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)',
  ],
};
```

## Coverage Targets

**No coverage currently enforced**

**Recommended coverage targets (if implemented):**
- Statements: 70%+
- Branches: 65%+
- Functions: 70%+
- Lines: 70%+

**Critical paths to 100%:**
- API layer (src/lib/api.ts)
- Auth context (src/context/AuthContext.tsx)
- Error handling paths

## Manual Testing Checklist (Current Approach)

Without automated tests, manual testing is critical:

**Authentication:**
- [ ] Register new user
- [ ] Login with valid credentials
- [ ] Login with invalid credentials (error message)
- [ ] Logout functionality
- [ ] Token persistence in cookies
- [ ] Redirect on unauthorized (401)

**Document Management:**
- [ ] Upload single file
- [ ] Upload multiple files
- [ ] File size validation (16MB limit)
- [ ] File type validation
- [ ] Upload progress display
- [ ] Delete document with confirmation

**Search & Filter:**
- [ ] Search by keyword
- [ ] Filter by category
- [ ] Filter by multiple categories
- [ ] Search in empty library

**Dashboard:**
- [ ] Load stats on page open
- [ ] Category distribution display
- [ ] Status distribution display
- [ ] Recent documents list
- [ ] Navigation between sections

---

**Next steps for testing infrastructure:**
1. Install Jest and React Testing Library
2. Create jest.config.js and jest.setup.ts
3. Set up test utilities and mocks in `__tests__/`
4. Write tests for API layer first (easiest to test)
5. Add context tests for auth flow
6. Add component tests for critical user flows
7. Configure CI/CD to run tests on commits
