---
name: jest-test
description: >
  Write, review, and improve Jest tests following best practices for TypeScript
  and JavaScript projects. Covers test structure, matchers, async testing,
  mocking strategies, data-driven tests, and anti-pattern detection. Use when
  user says "write tests for this", "create Jest tests", "review my tests",
  "mock this dependency", "test this function", "Jest best practices", or any
  Jest testing task.
license: MIT
---

# Jest Test

Write, review, and improve Jest tests following production-quality patterns and best practices for TypeScript and JavaScript projects.

Before starting, consult [references/jest-guide.xml](references/jest-guide.xml) -- a comprehensive playbook covering core principles, the full matcher catalog, async testing patterns, mocking strategies, data-driven tests, error handling, anti-patterns, and CI/CD integration. Reference it throughout the workflow.

## Workflow Overview

```
Analyze --> Plan --> Write Tests --> Review
    ^                    |             |
    +---- Revise --------+             |
                         +-- Fix ------+
```

Follow steps 1-4 in order. If the user provides existing tests for review, skip to Step 4.

## Step 1: Analyze

Read the source code to understand what needs testing. Identify:

- **Functions and methods** -- Public API surface that needs coverage
- **Dependencies** -- External modules, services, or APIs that need mocking (see `<mocking>` in jest-guide.xml)
- **Async operations** -- Promises, async/await, callbacks that need special handling (see `<async_testing>`)
- **Edge cases** -- Error paths, boundary values, null/undefined inputs
- **State management** -- Setup/teardown needs for consistent test state

If the user provides a file path, read it. If they describe functionality without providing code, ask them to share the relevant source files.

## Step 2: Plan

Determine the test strategy before writing code. Decide:

**What to test:**
- Test behavior, not implementation details (see `<anti_patterns>` in jest-guide.xml)
- Cover the happy path, error paths, and edge cases
- Prioritize public API surface over internal helpers

**Test organization** (see `<core_principles>` for structure templates):
- One `describe` block per function, class, or logical grouping
- Descriptive test names that read as specifications: `'should return empty array when no items match filter'`
- Group related tests with nested `describe` blocks

**Mocking strategy** (see `<mocking>` for the full pattern catalog):
- Mock external dependencies (APIs, databases, file system)
- Mock expensive operations (network calls, heavy computation)
- Do NOT mock the unit under test
- Use `jest.spyOn` when you need to verify calls while keeping the original behavior

**Coverage goals** (see `<coverage_requirements>` in `<core_principles>`):
- Services: 98% across all metrics
- Repositories/data access: 95%
- Utilities: 90%
- Global minimum: 95% statements, branches, functions, lines

## Step 3: Write Tests

Generate tests following the patterns in jest-guide.xml. Apply these rules consistently:

### Test structure

Every test file follows this skeleton:

```typescript
import { ServiceUnderTest } from '../service-under-test';

// Mock dependencies at the top
jest.mock('../dependency-module');

describe('ServiceUnderTest', () => {
  let service: ServiceUnderTest;
  let mockDependency: jest.Mocked<DependencyType>;

  beforeEach(() => {
    // Arrange: fresh instance and mocks for each test
    mockDependency = new DependencyModule() as jest.Mocked<DependencyType>;
    service = new ServiceUnderTest(mockDependency);
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  describe('methodName', () => {
    test('should return expected result for valid input', async () => {
      // Arrange
      mockDependency.fetch.mockResolvedValue(testData);
      // Act
      const result = await service.methodName(input);
      // Assert
      expect(result).toEqual(expected);
    });

    test('should throw when dependency fails', async () => {
      // Arrange
      mockDependency.fetch.mockRejectedValue(new Error('Network error'));
      // Act & Assert
      await expect(service.methodName(input)).rejects.toThrow('Network error');
    });
  });
});
```

### Choosing matchers

Select the right matcher from `<matchers>` in jest-guide.xml:

| Scenario | Matcher | Why |
|----------|---------|-----|
| Primitive comparison | `toBe()` | Strict === equality |
| Object/array comparison | `toEqual()` | Deep equality, ignores undefined |
| Strict object comparison | `toStrictEqual()` | Includes undefined properties |
| Partial object match | `toMatchObject()` | Only checks specified keys |
| Array contains item | `toContain()` (primitives) / `toContainEqual()` (objects) | Subset checking |
| Floating point | `toBeCloseTo()` | Avoids precision errors |
| Error thrown | `toThrow()` | Wrap in `expect(() => ...)` for sync |

### Async tests

All async tests must include assertion counting (see `<async_testing>`):

```typescript
test('async operation', async () => {
  expect.assertions(1); // Prevents false positives
  const result = await service.fetchData();
  expect(result).toBeDefined();
});
```

For error cases, use `.rejects`:

```typescript
test('rejects on failure', async () => {
  expect.assertions(1);
  await expect(service.fetchData()).rejects.toThrow('Network error');
});
```

### Mock cleanup

Always clean up mocks (see `<cleanup>` in `<mocking>`):

```typescript
afterEach(() => {
  jest.clearAllMocks();   // Reset call history
  jest.restoreAllMocks(); // Restore original implementations
});
```

### Data-driven tests

Use `test.each` for parameterized tests (see `<data_driven_testing>`):

```typescript
test.each([
  ['[email-1]', true],
  ['invalid', false],
  ['', false],
])('validates email "%s" as %s', (email, expected) => {
  expect(isValidEmail(email)).toBe(expected);
});
```

### Forbidden patterns

Never include any of the patterns listed in `<forbidden_patterns>` in jest-guide.xml:
- No `.only` or `.skip` -- these break CI
- No empty test bodies -- every test must have assertions
- No real timers -- use `jest.useFakeTimers()` (see `<timer_mocking>`)
- No unhandled async -- always `await` and use `expect.assertions()`

## Step 4: Review

Audit tests (generated or user-provided) against the reference. Check each area and report findings.

### Anti-pattern scan

Check against every item in `<anti_patterns>` in jest-guide.xml:

- [ ] Tests verify behavior, not implementation details
- [ ] Mocks are cleaned up in `afterEach`
- [ ] No real `setTimeout`/`setInterval` -- fake timers used instead
- [ ] All async operations are properly awaited
- [ ] No `.only`, `.skip`, or `.todo` in committed code

### Async safety

- [ ] Every async test has `expect.assertions(n)` or `expect.hasAssertions()`
- [ ] Promise rejections are tested with `.rejects.toThrow()`
- [ ] No floating promises (async calls without `await`)

### Mock hygiene

- [ ] `afterEach` includes `jest.clearAllMocks()` and/or `jest.restoreAllMocks()`
- [ ] Mocks are scoped to the narrowest level needed
- [ ] `jest.spyOn` used when original behavior should be preserved
- [ ] Module mocks use `jest.mock()` at the top of the file (hoisting)

### Coverage and completeness

- [ ] Happy path covered for all public methods
- [ ] Error paths tested (rejected promises, thrown exceptions)
- [ ] Edge cases covered (empty inputs, null/undefined, boundary values)
- [ ] Coverage meets thresholds from `<coverage_requirements>`

### CI readiness

Check against `<ci_cd>` quality gates:

- [ ] No `.only` / `.skip` / `.todo`
- [ ] No `console.log` statements in test files
- [ ] Coverage thresholds configured and met
- [ ] All async tests have assertion counts

Present review results as a checklist with pass/fail and specific fix recommendations.

## Examples

### Example 1: Writing tests for a service

User says: "Write tests for this UserService"

Actions:
1. Read the UserService source to identify methods, dependencies, and async operations
2. Plan: mock the UserRepository dependency, test CRUD methods, cover error paths
3. Generate a complete test file with describe/test blocks, proper mocking, async handling, and assertion counting
4. Verify no anti-patterns, all async tests have `expect.assertions()`, mocks cleaned up in `afterEach`

Result: A complete `user-service.test.ts` file with tests for each public method, mocked dependencies, error path coverage, and proper cleanup.

### Example 2: Reviewing existing tests

User says: "Review my test file for issues"

Actions:
1. Skip to Step 4 (Review)
2. Scan for anti-patterns: implementation testing, missing mock cleanup, real timers, unhandled async
3. Check async safety: assertion counts, proper await, rejects handling
4. Check mock hygiene: cleanup in afterEach, proper scoping
5. Present findings with specific line references and fixes

Result: A review report like:
- FAIL: Line 15 -- missing `expect.assertions()` in async test
- FAIL: Line 42 -- `setTimeout` used instead of fake timers
- WARN: No `afterEach` cleanup -- mock state may leak between tests
- PASS: All tests verify behavior, not implementation
- RECOMMENDATION: Add `test.each` for the repetitive validation tests on lines 60-90

### Example 3: Mocking guidance

User says: "How do I mock this external API client?"

Actions:
1. Read the source to understand the API client's interface
2. Show the relevant mocking pattern from `<mocking>` in jest-guide.xml
3. Provide a concrete example using `jest.mock()` for the module and `mockResolvedValue` / `mockRejectedValue` for async methods
4. Include cleanup pattern

Result: A focused code snippet showing module mock setup, typed mocks, return value configuration, and cleanup -- ready to paste into the test file.

## Troubleshooting

### Issue: Tests pass locally but fail in CI

Cause: Test order dependency -- a mock or state from one test leaks into another. Tests run in a different order in CI.
Solution: Add `afterEach(() => { jest.clearAllMocks(); jest.restoreAllMocks(); })` to every describe block. Run locally with `--runInBand` to reproduce order-dependent failures. Check for shared mutable state outside of `beforeEach`.

### Issue: Mock is not being used (original function still runs)

Cause: `jest.mock()` calls are hoisted to the top of the file, but the mock path may not match the import path exactly. Or `jest.doMock()` was used without a subsequent dynamic `require()`.
Solution: Ensure the path in `jest.mock('path')` exactly matches the import statement. For aliased paths (`@/services/...`), verify `moduleNameMapper` in Jest config. Check that the mock is defined before the module-under-test is imported.

### Issue: Async test times out

Cause: A promise is never resolved or rejected, or `done()` is never called in a callback-style test.
Solution: Check that all async operations are properly awaited. For callback tests, ensure `done()` is called in both success and error paths (wrap in try/catch). Add `expect.assertions(n)` to catch silent non-execution. Increase timeout if the operation is legitimately slow: `test('slow op', async () => {...}, 10000)`.

### Issue: Coverage threshold not met

Cause: Uncovered branches (often error paths, default switch cases, or early returns).
Solution: Run `jest --coverage` and inspect the HTML report at `coverage/lcov-report/index.html`. Look for red-highlighted lines -- these are uncovered. Common gaps: catch blocks, null checks, default cases in switch statements. Add targeted tests for each uncovered branch.
