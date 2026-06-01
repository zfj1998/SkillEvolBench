# @acme/ui-components — Changelog

## 4.0.0 (2024-01-15)

### BREAKING CHANGES
- **Minimum React version is now 18.0.0** (dropped React 16/17 support)
- Migrated all internal rendering from `ReactDOM.render` to `createRoot` API
- **`Button`: renamed `label` prop to `text`** for consistency with design system tokens
- Removed `legacyMode` prop (no longer needed with React 18)

### Migration Guide
- Upgrade React to 18.x first
- Replace `<Button label="...">` with `<Button text="...">`
- No other prop changes for Modal, Card, or other components

## 3.2.0 (2023-06-01)
- Added Card component
- Bug fixes for Button hover states
- Requires React ^17.0.0
