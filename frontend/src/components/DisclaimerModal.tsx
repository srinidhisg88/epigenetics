import React, { useEffect, useState } from 'react';

const SESSION_KEY = 'disclaimer_acknowledged';

const DisclaimerModal: React.FC = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show every session — medical tools should re-confirm each visit
    if (!sessionStorage.getItem(SESSION_KEY)) {
      setVisible(true);
    }
  }, []);

  const acknowledge = () => {
    sessionStorage.setItem(SESSION_KEY, '1');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-amber-500 px-6 py-4 flex items-center gap-3">
          <svg className="w-7 h-7 text-white shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <div>
            <h2 className="text-lg font-bold text-white">Research Use Only</h2>
            <p className="text-amber-100 text-xs">Not clinically validated — read before proceeding</p>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4 text-sm text-gray-700">
          <p>
            <strong>This tool is a research prototype</strong> and has <strong>not been clinically validated</strong>
            for diagnostic use. It is intended solely for academic research and educational purposes.
          </p>

          <ul className="space-y-2 list-none">
            {[
              'Do not use predictions or ACMG classifications to make clinical decisions.',
              'All outputs — including ML predictions, ACMG criteria, and LLM interpretations — must be independently verified by a qualified clinical geneticist.',
              'The ACMG/AMP classifications generated here are automated and may not reflect the full evidence available to expert reviewers.',
              'AI-generated clinical summaries may contain errors or omissions.',
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-0.5 shrink-0 w-5 h-5 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold">!</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 text-xs text-gray-500">
            By clicking <strong>"I Understand"</strong> you confirm that you are using this tool for
            research or educational purposes only and will not rely on its outputs for clinical diagnosis or treatment decisions.
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 flex justify-end">
          <button
            onClick={acknowledge}
            className="px-6 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-lg transition-colors text-sm"
          >
            I Understand — Continue to Research Tool
          </button>
        </div>
      </div>
    </div>
  );
};

export default DisclaimerModal;
