# Contract Copilot UI

Next.js demo interface for the AI Contract Reviewer & Negotiation Copilot.

## Features

- **File Upload**: Drag-and-drop interface for contract documents (PDF, TXT)
- **Progress Indicator**: Real-time visualization of agent pipeline execution
- **Results Display**: Tabbed interface showing:
  - Extracted clauses with classifications
  - Risk assessments with severity levels
  - Redline suggestions with diff viewer
  - Negotiation summary and draft email
  - Complete audit trail
- **Download**: Export audit bundle as JSON
- **Disclaimer**: Prominent legal disclaimer on all pages

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

### Installation

```bash
cd ui
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
npm run build
npm start
```

## Configuration

The UI connects to the FastAPI backend at `http://localhost:8000` by default. To change this, update the API endpoint in `app/page.tsx`.

## Components

- `FileUpload`: Drag-and-drop file upload with validation
- `ProgressIndicator`: Animated pipeline progress tracker
- `ResultsDisplay`: Tabbed results viewer
- `Disclaimer`: Legal disclaimer component
- `DiffViewer`: Side-by-side and unified diff viewer for redlines
- `tabs/ClausesTab`: Display extracted clauses
- `tabs/RisksTab`: Display risk assessments
- `tabs/RedlinesTab`: Display redline suggestions
- `tabs/SummaryTab`: Display negotiation summary
- `tabs/AuditTab`: Display audit trail

## Technology Stack

- Next.js 16 with App Router
- TypeScript
- Tailwind CSS
- React Hooks

## Requirements Addressed

- **1.1**: File upload interface for contract documents
- **5.4**: Negotiation-ready summary display
- **8.2**: Prominent disclaimer on all outputs
