import React, { useState } from 'react';
import type { ACMGClassification, ACMGCriterion } from '../types';

interface ACMGPanelProps {
  acmg: ACMGClassification;
  gene: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const CLASSIFICATION_STYLES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  'Pathogenic':        { bg: 'bg-red-50',    border: 'border-red-400',    text: 'text-red-800',    badge: 'bg-red-600 text-white' },
  'Likely Pathogenic': { bg: 'bg-orange-50', border: 'border-orange-400', text: 'text-orange-800', badge: 'bg-orange-500 text-white' },
  'VUS':               { bg: 'bg-yellow-50', border: 'border-yellow-400', text: 'text-yellow-800', badge: 'bg-yellow-500 text-white' },
  'Likely Benign':     { bg: 'bg-blue-50',   border: 'border-blue-400',   text: 'text-blue-800',   badge: 'bg-blue-500 text-white' },
  'Benign':            { bg: 'bg-green-50',  border: 'border-green-400',  text: 'text-green-800',  badge: 'bg-green-600 text-white' },
};

const POINTS_COLOR: Record<number, string> = {};

function pointsBadgeStyle(points: number): string {
  if (points >= 8) return 'bg-red-700 text-white';
  if (points >= 4) return 'bg-red-500 text-white';
  if (points >= 2) return 'bg-orange-500 text-white';
  if (points >= 1) return 'bg-orange-300 text-orange-900';
  if (points <= -4) return 'bg-green-700 text-white';
  if (points <= -2) return 'bg-green-500 text-white';
  return 'bg-green-300 text-green-900';
}

function weightLabel(points: number): string {
  const abs = Math.abs(points);
  if (abs >= 8) return 'Very Strong';
  if (abs >= 4) return 'Strong';
  if (abs >= 2) return 'Moderate';
  return 'Supporting';
}

function scoreBarWidth(score: number): number {
  // Map score to 0–100% bar. Range ~[-16, +16]
  const clamped = Math.max(-16, Math.min(16, score));
  return Math.round(((clamped + 16) / 32) * 100);
}

// ── Sub-components ────────────────────────────────────────────────────────────

const CriterionCard: React.FC<{ criterion: ACMGCriterion; met: boolean }> = ({ criterion, met }) => (
  <div className={`rounded-lg border p-3 ${met ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100 opacity-70'}`}>
    <div className="flex items-start gap-2">
      {/* Code + points badge */}
      <div className="flex flex-col items-center gap-1 min-w-[52px]">
        <span className={`inline-block px-2 py-0.5 rounded font-mono font-bold text-sm ${met ? pointsBadgeStyle(criterion.points) : 'bg-gray-200 text-gray-500'}`}>
          {criterion.code}
        </span>
        {met && (
          <span className={`text-[10px] font-semibold px-1 rounded ${criterion.points > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {criterion.points > 0 ? `+${criterion.points}` : criterion.points}
          </span>
        )}
      </div>
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-gray-700 truncate">{criterion.description}</span>
          {met && (
            <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${criterion.points > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {weightLabel(criterion.points)}
            </span>
          )}
        </div>
        <p className={`text-xs leading-relaxed ${met ? 'text-gray-600' : 'text-gray-400'}`}>
          {criterion.reason}
        </p>
      </div>
      {/* Met/Not-met icon */}
      <span className={`shrink-0 text-base ${met ? (criterion.points > 0 ? 'text-red-500' : 'text-green-500') : 'text-gray-300'}`}>
        {met ? '●' : '○'}
      </span>
    </div>
  </div>
);

// ── LLM Clinical Summary ──────────────────────────────────────────────────────

const ClinicalSummaryBox: React.FC<{ summary: string }> = ({ summary }) => {
  const [expanded, setExpanded] = useState(false);

  // Parse the structured summary text into sections
  const lines = summary.split('\n').filter(l => l.trim());
  const headerLine = lines[0] || '';
  const scoreLine = lines[1] || '';
  const body = lines.slice(2);

  return (
    <div className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-indigo-100 border-b border-indigo-200">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span className="text-sm font-semibold text-indigo-800">LLM Clinical Interpretation</span>
          <span className="text-[10px] bg-indigo-200 text-indigo-700 px-1.5 py-0.5 rounded-full font-medium">AI-generated</span>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          {expanded ? 'Show less ▲' : 'Show full ▼'}
        </button>
      </div>

      <div className="px-4 py-3">
        {/* Validation disclaimer */}
        <div className="mb-3 flex items-start gap-1.5 rounded bg-amber-50 border border-amber-200 px-2.5 py-2 text-xs text-amber-800">
          <svg className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span>
            This classification is <strong>automated and not clinically validated</strong>.
            Independent review by a certified clinical geneticist is required before any diagnostic use.
          </span>
        </div>

        {/* Always show first two lines */}
        <p className="text-sm font-semibold text-indigo-900">{headerLine}</p>
        <p className="text-xs text-indigo-700 mb-2">{scoreLine}</p>

        {/* Expandable body */}
        {(expanded || body.length <= 6) && (
          <div className="space-y-1 mt-2">
            {body.map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return <div key={i} className="h-1" />;
              if (trimmed.endsWith(':')) {
                return <p key={i} className="text-xs font-semibold text-indigo-800 mt-2">{trimmed}</p>;
              }
              const isCheck = trimmed.startsWith('✓');
              return (
                <p key={i} className={`text-xs leading-relaxed ${isCheck ? 'text-indigo-700 pl-2' : 'text-indigo-600 pl-2'}`}>
                  {trimmed}
                </p>
              );
            })}
          </div>
        )}

        {!expanded && body.length > 6 && (
          <p className="text-xs text-indigo-500 mt-1 italic">
            {body.length - 6} more lines — click "Show full" to expand
          </p>
        )}
      </div>
    </div>
  );
};

// ── Main Panel ────────────────────────────────────────────────────────────────

const ACMGPanel: React.FC<ACMGPanelProps> = ({ acmg, gene }) => {
  const [showNotMet, setShowNotMet] = useState(false);

  const style = CLASSIFICATION_STYLES[acmg.classification] ?? CLASSIFICATION_STYLES['VUS'];
  const barWidth = scoreBarWidth(acmg.total_score);
  const midPoint = scoreBarWidth(0); // where 0 score falls (50%)

  const pathogenicCriteria = acmg.criteria_met.filter(c => c.points > 0);
  const benignCriteria = acmg.criteria_met.filter(c => c.points < 0);

  return (
    <div className={`rounded-lg border-2 ${style.border} ${style.bg} overflow-hidden`}>
      {/* ── Panel Header ── */}
      <div className={`px-4 py-3 border-b ${style.border} flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          <div>
            <h4 className={`text-sm font-bold ${style.text}`}>ACMG/AMP Classification</h4>
            <p className="text-xs text-gray-500">
              Tavtigian 2018 points-based scoring · Gene mechanism: <span className="font-semibold">{acmg.gene_mechanism}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-sm font-bold ${style.badge}`}>
            {acmg.classification}
          </span>
        </div>
      </div>

      {/* ── Score Bar ── */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
          <span>Benign ←</span>
          <span className="font-bold text-sm text-gray-900">
            Evidence Score: <span className={acmg.total_score > 0 ? 'text-red-600' : acmg.total_score < 0 ? 'text-green-600' : 'text-gray-600'}>
              {acmg.total_score > 0 ? `+${acmg.total_score}` : acmg.total_score}
            </span>
          </span>
          <span>→ Pathogenic</span>
        </div>
        <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden">
          {/* Neutral midpoint line */}
          <div className="absolute top-0 bottom-0 w-0.5 bg-gray-400 z-10" style={{ left: `${midPoint}%` }} />
          {/* Score fill */}
          <div
            className={`absolute top-0 bottom-0 rounded-full transition-all ${acmg.total_score >= 0 ? 'bg-red-400' : 'bg-green-400'}`}
            style={acmg.total_score >= 0
              ? { left: `${midPoint}%`, width: `${barWidth - midPoint}%` }
              : { left: `${barWidth}%`, width: `${midPoint - barWidth}%` }
            }
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
          <span>−16 (Benign)</span>
          <span>0 (VUS)</span>
          <span>+10 (Pathogenic)</span>
        </div>
      </div>

      {/* ── Score Breakdown Pills ── */}
      <div className="px-4 pb-3 flex flex-wrap gap-2">
        {acmg.score_breakdown.pathogenic_criteria.map(code => (
          <span key={code} className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-mono font-bold border border-red-200">
            {code}
          </span>
        ))}
        {acmg.score_breakdown.benign_criteria.map(code => (
          <span key={code} className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-mono font-bold border border-green-200">
            {code}
          </span>
        ))}
        {acmg.criteria_met.length === 0 && (
          <span className="text-xs text-gray-400 italic">No criteria met</span>
        )}
      </div>

      {/* ── Criteria Met ── */}
      <div className="px-4 pb-3 space-y-3">
        {pathogenicCriteria.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-red-700 mb-2 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
              Pathogenic Evidence ({acmg.score_breakdown.pathogenic_points > 0 ? `+${acmg.score_breakdown.pathogenic_points}` : 0} pts)
            </p>
            <div className="space-y-2">
              {pathogenicCriteria.map(c => (
                <CriterionCard key={c.code} criterion={c} met={true} />
              ))}
            </div>
          </div>
        )}

        {benignCriteria.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-green-700 mb-2 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
              Benign Evidence ({acmg.score_breakdown.benign_points} pts)
            </p>
            <div className="space-y-2">
              {benignCriteria.map(c => (
                <CriterionCard key={c.code} criterion={c} met={true} />
              ))}
            </div>
          </div>
        )}

        {/* Not-met toggle */}
        {acmg.criteria_not_met.length > 0 && (
          <div>
            <button
              onClick={() => setShowNotMet(v => !v)}
              className="text-xs text-gray-500 hover:text-gray-700 font-medium flex items-center gap-1"
            >
              {showNotMet ? '▼' : '▶'} {showNotMet ? 'Hide' : 'Show'} criteria not met ({acmg.criteria_not_met.length})
            </button>
            {showNotMet && (
              <div className="mt-2 space-y-2">
                {acmg.criteria_not_met.map(c => (
                  <CriterionCard key={c.code} criterion={c} met={false} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── LLM Clinical Summary ── */}
      <div className="px-4 pb-4">
        <ClinicalSummaryBox summary={acmg.clinical_summary} />
      </div>
    </div>
  );
};

export default ACMGPanel;
