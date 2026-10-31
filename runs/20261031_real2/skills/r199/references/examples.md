## Examples

### Quick Migration Status

```typescript
const status = await validateVercelMigration();
console.log(`Migration ${status.passed ? 'PASSED' : 'FAILED'}`);
status.checks.forEach(c => console.log(`  ${c.name}: ${c.result.success}`));
```

---
*[Tons of Skills]([url-1]) by [Intent Solutions]([url-2]) | [[host-1]]([url-3])*
