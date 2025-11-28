'use client';

export default function Disclaimer() {
  return (
    <div className="mt-8 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700/30 rounded-lg p-4 flex items-start gap-4">
      <span className="material-symbols-outlined text-yellow-500 dark:text-yellow-400 mt-0.5">warning</span>
      <div>
        <h2 className="font-semibold text-yellow-800 dark:text-yellow-300">Important Legal Disclaimer</h2>
        <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">
          This tool is not a substitute for legal advice. It is an AI-assisted reviewer intended for preliminary analysis only. All outputs should be reviewed by qualified legal professionals before making any decisions. The system may produce errors, omissions, or inaccurate assessments.
        </p>
      </div>
    </div>
  );
}
