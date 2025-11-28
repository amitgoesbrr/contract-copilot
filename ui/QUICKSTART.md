# Quick Start Guide

## Step 1: Install Dependencies

```bash
cd ui
npm install
```

## Step 2: Start the Backend API

In a separate terminal, start the FastAPI backend:

```bash
cd ..
python run_api.py
```

The API should be running on `http://localhost:8000`.

## Step 3: Start the UI Development Server

```bash
npm run dev
```

The UI will be available at `http://localhost:3000`.

## Step 4: Upload a Contract

1. Open your browser to `http://localhost:3000`
2. Drag and drop a contract file (PDF, TXT, or MD) or click to browse
3. Wait for the analysis to complete (progress indicator will show each stage)
4. Review the results in the tabbed interface:
   - **Clauses**: View extracted clauses with classifications
   - **Risks**: See risk assessments with severity levels
   - **Redlines**: Review suggested changes with diff viewer
   - **Summary**: Read negotiation summary and draft email
   - **Audit Trail**: Examine complete audit trail
5. Download the audit bundle as JSON if needed

## Testing with Sample Contracts

Use the sample contracts in the `sample_contracts/` directory:

- `sample_nda.md`: Standard NDA
- `sample_msa.md`: Master Services Agreement
- `sample_sla.md`: Service Level Agreement

## Troubleshooting

### API Connection Error

If you see "Upload failed" or connection errors:

1. Verify the backend API is running on port 8000
2. Check the console for CORS errors
3. Ensure `.env.local` has the correct API URL (if using custom configuration)

### File Upload Issues

- Ensure file is PDF, TXT, or MD format
- File size must be under 10MB
- Check browser console for validation errors

### Processing Timeout

If processing takes too long:

- Check backend logs for errors
- Verify Gemini API key is configured in backend `.env`
- Try with a smaller contract document
