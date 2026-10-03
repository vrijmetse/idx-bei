import React from 'react';
import { Printer, X, ShieldCheck, TrendingUp, Coins, Building, Award, CheckCircle, AlertTriangle } from 'lucide-react';
import type { Company } from '../types';
import { formatNum, formatCurrency } from '../utils/formatters';

interface InvestorMemoModalProps {
  company: Company;
  onClose: () => void;
}

export const InvestorMemoModal: React.FC<InvestorMemoModalProps> = ({ company, onClose }) => {
  const currentPrice = company.price ?? company.previous_price ?? 0;
  const score = company.compounder_score ?? company.score?.total ?? null;
  const latestFsDate = company.latest_fs_date ? new Date(company.latest_fs_date).toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: '2-digit' }) : 'N/A';
  const isExtremeLeverage = (company.de_ratio != null && company.de_ratio > 4.0 && !company.is_blue_chip) || (company.roe != null && company.roe > 100.0);
  const isTrapOrLoss = company.is_value_trap || (company.roe != null && company.roe < 0) || (company.npm != null && company.npm < 0) || isExtremeLeverage;
  const isHighQuality = (company.roe != null && company.roe >= 15) && !isTrapOrLoss;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem',
    }}>
      <div className="memo-container" style={{
        background: '#0a0e1a',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '820px',
        maxHeight: '90vh',
        overflowY: 'auto',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      }}>
        {/* Screen Toolbar (Hidden when printing) */}
        <div className="no-print" style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '1rem 1.5rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          background: 'rgba(15, 23, 42, 0.8)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Award size={20} style={{ color: '#38bdf8' }} />
            <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Institutional Investment Memo</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={handlePrint}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                background: '#38bdf8',
                color: '#000',
                fontWeight: 700,
                fontSize: '0.85rem',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <Printer size={16} />
              <span>Print / Save PDF</span>
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#fff',
                padding: '0.5rem',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Printable Memo Sheet */}
        <div id="printableMemo" style={{ padding: '2rem', color: '#f8fafc' }}>
          {/* Header Banner */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            borderBottom: '2px solid rgba(56, 189, 248, 0.4)',
            paddingBottom: '1.25rem',
            marginBottom: '1.5rem',
          }}>
            <div>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#38bdf8', fontWeight: 700 }}>
                IDX Quantitative Research &bull; Institutional Dossier
              </div>
              <h1 style={{ margin: '0.35rem 0 0.2rem', fontSize: '2rem', fontWeight: 800 }}>
                {company.code} &mdash; {company.name}
              </h1>
              <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                Sector: <strong>{company.sector}</strong> {company.conglomerate ? `| Group: ${company.conglomerate}` : ''}
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: currentPrice > 0 ? '#10b981' : '#64748b', fontFamily: 'monospace' }}>
                {currentPrice > 0 ? `Rp ${currentPrice.toLocaleString()}` : '—'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                As of {latestFsDate}
              </div>
              <div style={{
                display: 'inline-block',
                marginTop: '0.5rem',
                padding: '0.25rem 0.75rem',
                borderRadius: '20px',
                background: score != null && score >= 80 ? 'rgba(16, 185, 129, 0.2)' : score != null && score < 30 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                color: score != null && score >= 80 ? '#34d399' : score != null && score < 30 ? '#ef4444' : '#38bdf8',
                fontWeight: 700,
                fontSize: '0.8rem',
                border: `1px solid ${score != null && score >= 80 ? 'rgba(16, 185, 129, 0.4)' : score != null && score < 30 ? 'rgba(239, 68, 68, 0.4)' : 'rgba(56, 189, 248, 0.4)'}`,
              }}>
                SMSS Score: {score != null ? `${score} / 100` : '—'}
              </div>
            </div>
          </div>

          {/* 4 Pillars Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
            {/* Fundamentals */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#38bdf8' }}>
                <TrendingUp size={18} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>1. Valuation & Profitability</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', fontSize: '0.85rem' }}>
                <div>Price-to-Earnings (PER): <strong>{formatNum(company.per, 2, '—')}x</strong></div>
                <div>Price-to-Book (PBV): <strong>{formatNum(company.pbv ?? company.price_bv, 2, '—')}x</strong></div>
                <div>Return on Equity (ROE): <strong style={{ color: company.roe && company.roe >= 15 ? '#10b981' : company.roe && company.roe < 0 ? '#ef4444' : '#eab308' }}>{formatNum(company.roe, 2, '—')}%</strong></div>
                <div>Debt-to-Equity (DER): <strong>{formatNum(company.de_ratio, 2, '—')}x</strong></div>
              </div>
            </div>

            {/* Dividend Health */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#eab308' }}>
                <Coins size={18} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>2. Dividend Quality & Cashflow</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', fontSize: '0.85rem' }}>
                <div>Dividend Yield: <strong style={{ color: company.dividend_yield_pct && company.dividend_yield_pct >= 5 ? '#10b981' : '#eab308' }}>{formatNum(company.dividend_yield_pct, 2, '—')}%</strong></div>
                <div>Latest DPS: <strong>{formatCurrency(company.annualized_dps, 'Rp', 0, '—')}</strong></div>
                <div>Trap Risk Score: <strong style={{ color: company.dividend_trap_tier === 'LOW' ? '#10b981' : company.dividend_trap_tier === 'CRITICAL' ? '#ef4444' : '#eab308' }}>{formatNum(company.dividend_trap_score, 0, '—')}/100</strong></div>
                <div>Status: <strong style={{ color: company.dca_verdict === 'BUY / ACCUMULATE' ? '#34d399' : company.dca_verdict === 'SELL BEFORE CUM DATE' ? '#ef4444' : '#eab308' }}>{company.dca_verdict || company.dividend_trap_tier || 'Not Available'}</strong></div>
              </div>
            </div>

            {/* Smart Money Flow */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#10b981' }}>
                <ShieldCheck size={18} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>3. Smart Money Footprint</h3>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <div>Institutional Regime: <strong style={{ color: company.smart_money?.institutional_regime === 'Net Accumulation' ? '#10b981' : '#ef4444' }}>{company.smart_money?.institutional_regime || 'Not Available'}</strong></div>
                <div>Smart Money Delta: <strong>{formatNum(company.smart_money?.smart_money_delta, 2, '—')}x ({company.smart_money?.broker_dominance || 'Not Available'})</strong></div>
                <div>Audit Risk: <strong style={{ color: company.fundamentals?.audit_opinion === 'WTP' ? '#34d399' : '#ef4444' }}>{company.fundamentals?.audit_opinion || 'Not Available'}</strong></div>
              </div>
            </div>

            {/* Ownership & Control */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: '#c084fc' }}>
                <Building size={18} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>4. Corporate Governance & Group</h3>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <div>Controlling Group: <strong>{company.conglomerate || 'Independent'}</strong></div>
                <div>Blue Chip Status: <strong>{company.is_blue_chip ? 'LQ45 Tier-1' : 'Mid-Cap'}</strong></div>
                <div>Board Centrality: <strong>{formatNum(company.board_centrality, 2, 'Not Available')}</strong></div>
              </div>
            </div>
          </div>

          {/* Bottom Executive Verdict */}
          <div style={{
            background: isTrapOrLoss ? 'rgba(239, 68, 68, 0.08)' : isHighQuality ? 'rgba(16, 185, 129, 0.08)' : 'rgba(56, 189, 248, 0.08)',
            border: `1px solid ${isTrapOrLoss ? 'rgba(239, 68, 68, 0.4)' : isHighQuality ? 'rgba(16, 185, 129, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`,
            borderRadius: '12px',
            padding: '1.25rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: isTrapOrLoss ? '#ef4444' : isHighQuality ? '#10b981' : '#38bdf8', fontWeight: 700, marginBottom: '0.35rem' }}>
              {isTrapOrLoss ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
              <span>{isTrapOrLoss ? 'Forensic & Risk Warning' : 'Executive Investment Verdict'}</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.5, color: '#e2e8f0' }}>
              {company.ai_thesis ? (
                company.ai_thesis
              ) : isTrapOrLoss ? (
                <span>
                  <strong>{company.code}</strong> exhibits heightened financial or valuation risk.
                  {company.roe != null && company.roe < 0 ? ` The company recorded an unprofitable ROE of ${company.roe.toFixed(2)}%.` : ''}
                  {company.forensic_reasons && company.forensic_reasons.length > 0 ? ` Flagged concerns: ${company.forensic_reasons.join('; ')}.` : ''}
                  {' '}Not recommended for long-term compounder portfolios until sustained profitability and balance sheet solvency are demonstrated.
                </span>
              ) : isHighQuality ? (
                <span>
                  <strong>{company.code}</strong> demonstrates strong capital compounding capability with an ROE of {company.roe != null ? `${company.roe.toFixed(2)}%` : 'elevated'} and stable financial health. Suitable for disciplined dollar-cost averaging (DCA) and core long-term portfolio allocation.
                </span>
              ) : (
                <span>
                  <strong>{company.code}</strong> exhibits moderate fundamentals with an ROE of {company.roe != null ? `${company.roe.toFixed(2)}%` : '—'} and PBV of {company.pbv ?? company.price_bv != null ? `${(company.pbv ?? company.price_bv)!.toFixed(2)}x` : '—'}. Position sizing should be managed conservatively pending further margin expansion or institutional accumulation.
                </span>
              )}
            </p>
          </div>

          <div style={{ marginTop: '1.5rem', fontSize: '0.7rem', color: 'var(--text-secondary)', textAlign: 'center', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.75rem' }}>
            Disclaimer: Generated automatically by IDX Quantitative Decision Engine for research purposes only. Not personal investment advice.
          </div>
        </div>
      </div>
    </div>
  );
};
