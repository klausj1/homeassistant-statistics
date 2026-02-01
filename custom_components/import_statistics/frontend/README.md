# Import Statistics Frontend Panel

This directory contains the frontend web component for the Import Statistics custom integration.

## Technology Stack

- **Lit 3.x** - Web Components framework
- **TypeScript** - Type-safe JavaScript
- **Rollup** - Module bundler

## Prerequisites

- Node.js 18+ and npm

## Installation

```bash
cd custom_components/import_statistics/frontend
npm install
```

## Development

Build the frontend in watch mode (auto-rebuild on changes):

```bash
npm run dev
```

## Production Build

Build the frontend for production:

```bash
npm run build
```

This creates `dist/index.js` which is loaded by Home Assistant.

## Project Structure

```
frontend/
├── src/
│   ├── index.ts                    # Entry point
│   ├── import-statistics-panel.ts  # Main panel component
│   └── types.ts                    # TypeScript type definitions
├── dist/                           # Build output
│   ├── index.html                  # HTML wrapper
│   └── index.js                    # Bundled JavaScript (generated)
├── package.json                    # Dependencies
├── tsconfig.json                   # TypeScript config
└── rollup.config.js                # Build config
```

## Accessing the Panel

After building and restarting Home Assistant, access the panel at:

```
http://your-home-assistant:8123/api/import_statistics/panel/index.html
```

## Development Notes

- The panel uses Lit decorators (`@customElement`, `@property`, `@state`)
- TypeScript strict mode is enabled
- The component integrates with Home Assistant's service API
- Fixed import parameters are used in this minimal version

## Future Enhancements

- Sidebar panel registration (requires Home Assistant panel API integration)
- Configurable import parameters
- File preview
- Drag-and-drop upload
- Progress indicators
- Upload history
