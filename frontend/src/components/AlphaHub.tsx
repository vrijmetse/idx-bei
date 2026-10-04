import React, { useState, useEffect, useMemo } from 'react';
import { 
  Compass, 
  TrendingUp, 
  Coins, 
  ShieldAlert, 
  Star, 
  Search, 
  ArrowRight, 
  FileText, 
  Zap, 
  RotateCw,
  Sparkles,
  Award,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ShieldCheck,
} from 'lucide-react';
import type { Company, StealthAnomaly, DividendOpportunity } from '../types';
import { fetchStealthAccumulation, fetchDividendScreen, fetchDailyBriefing, fetchBrokerFlow, fetchCompaniesList } from '../services/api';
import { DailyBriefingModal } from './DailyBriefingModal';


interface AlphaHubProps {
  companies?: Company[];
  onSelectStock: (ticker: string) => void;
  onOpenMemo: (company: Company) => void;
  isStarred: (code: string) => boolean;
  onToggleStar: (company: Company) => void;
}

export const AlphaHub: React.FC<AlphaHubProps> = ({
  onSelectStock,
  onOpenMemo,
  isStarred,
  onToggleStar,
}) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [championPool, setChampionPool] = useState<Company[]>([]);
  const [totalCompanies, setTotalCompanies] = useState<number>(0);
  const [loadingCompanies, setLoadingCompanies] = useState<boolean>(true);
  const [activeCategory, setActiveCategory] = useState<'all' | 'dca_prime' | 'smart_money' | 'dividends' | 'value' | 'danger' | 'sharia'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [stealthAnomalies, setStealthAnomalies] = useState<StealthAnomaly[]>([]);
  const [dividendOpps, setDividendOpps] = useState<DividendOpportunity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [briefingOpen, setBriefingOpen] = useState<boolean>(false);
  const [briefingData, setBriefingData] = useState<any>(null);
  const [, setBriefingLoading] = useState<boolean>(false);

  // Debounce search query to prevent laggy keystroke API hammering
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Pagination & Sorting state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [sortKey, setSortKey] = useState<string>('compounder_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleOpenBriefing = async () => {
    setBriefingOpen(true);
    if (!briefingData) {
      setBriefingLoading(true);
      try {
        const data = await fetchDailyBriefing();
        setBriefingData(data);
      } catch (e) {
        console.warn('Failed to load briefing from backend, attempting live broker flow:', e);
        try {
          const brokerFlow = await fetchBrokerFlow();
          setBriefingData({
            trade_date: new Date().toISOString().split('T')[0],
            stealth_accumulation: { anomalies: stealthAnomalies },
            foreign_flow_radar: companies.slice(0, 5),
            composite_alpha_rankings: companies.slice(0, 5).map((c) => ({
              StockCode: c.code,
              ROE: c.roe,
              PER: c.per,
            })),
            bandarmology_summary: brokerFlow?.summary || {},
          });
        } catch {
          setBriefingData(null);
        }
      } finally {
        setBriefingLoading(false);
      }
    }
  };

  // Load real backend intelligence
  const loadIntelligence = async () => {
    setLoading(true);
    try {
      const [stealthRes, divRes] = await Promise.all([
        fetchStealthAccumulation().catch(() => null),
        fetchDividendScreen(4.0).catch(() => []),
      ]);

      if (stealthRes?.anomalies) {
        setStealthAnomalies(stealthRes.anomalies);
      }
      if (Array.isArray(divRes)) {
        setDividendOpps(divRes.map((d: any) => ({
          StockCode: d.Ticker || d.code || d.StockCode,
          StockName: d.Name || d.name || d.StockName,
          Price: Number(d.Price ?? d.price ?? 0),
          DPS: Number(d.DPS_IDR ?? d.dps ?? 0),
          DividendYield: Number(d['Yield%'] ?? d.yield ?? 0),
          CumDate: d.CumDate || d.cum_date || '—',
          ExDate: d.ExDate || d.ex_date || '—',
          PayoutRatio: Number(d['DPR%'] ?? d.payout_ratio ?? 0),
          TrapScore: Number(d.TrapScore ?? d.trap_score ?? 25),
          Recommendation: d.Verdict || 'BUY',
        })));
      }
    } catch (e) {
      console.warn('Failed to load alpha intelligence', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIntelligence();
    // Load top compounder candidates so Champion Compounders banner is resilient across table filters
    fetchCompaniesList({ category: 'dca_prime', sort_by: 'compounder_score', sort_dir: 'desc', page: 1, page_size: 25 })
      .then((data) => {
        if (data.companies && data.companies.length > 0) {
          setChampionPool(data.companies);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch companies from API based on filters, sort, and pagination
  useEffect(() => {
    let isMounted = true;
    const fetchCompanies = async () => {
      setLoadingCompanies(true);
      try {
        let apiSortBy = sortKey;
        if ((sortKey === 'compounder_score' || sortKey === 'score')) apiSortBy = 'compounder_score';
        if ((sortKey === 'price_bv' || sortKey === 'pbv')) apiSortBy = 'price_bv';
        if ((sortKey === 'yield' || sortKey === 'dividend_yield_pct')) apiSortBy = 'dividend_yield_pct';

        const params: any = {
          category: activeCategory,
          search: debouncedSearch,
          sort_by: apiSortBy,
          sort_dir: sortDir,
          page: currentPage,
          page_size: pageSize,
        };

        // Apply specific metric filters based on category
        if (activeCategory === 'dividends') {
          params.min_yield = 3.0; // Default min yield for dividend screen
        } else if (activeCategory === 'value') {
          params.max_per = 15.0; // Max PER for value stocks
          params.min_roe = 10.0; // Min ROE for value stocks
        } else if (activeCategory === 'sharia') {
          params.is_sharia = true;
        }

        const data = await fetchCompaniesList(params);
        if (isMounted) {
          setCompanies(data.companies || []);
          setTotalCompanies(data.total_count ?? 0);
        }
      } catch (error) {
        console.error('Failed to fetch companies:', error);
        if (isMounted) {
          setCompanies([]);
          setTotalCompanies(0);
        }
      } finally {
        if (isMounted) {
          setLoadingCompanies(false);
        }
      }
    };

    fetchCompanies();
    return () => {
      isMounted = false;
    };
  }, [activeCategory, debouncedSearch, sortKey, sortDir, currentPage, pageSize]);

  // Top Action Cards computation
  const topSmartMoney = useMemo(() => {
    return stealthAnomalies
      .filter((a) => {
        if (a.Signal !== 'STEALTH_ACCUMULATION') return false;
        const pool = championPool.length > 0 ? championPool : companies;
        const matched = pool.find((c) => c.code === a.StockCode);
        if (matched?.is_value_trap || (matched?.roe != null && matched.roe < 0)) return false;
        if (['PADI', 'BEST', 'PSKT'].includes(a.StockCode)) return false;
        return true;
      })
      .slice(0, 3);
  }, [stealthAnomalies, championPool, companies]);

  const topDividends = useMemo(() => {
    return dividendOpps.filter((d) => (d.TrapScore ?? 0) <= 35 && d.DividendYield >= 5.0).slice(0, 3);
  }, [dividendOpps]);

  const topTraps = useMemo(() => {
    return stealthAnomalies.filter((a) => a.Signal === 'RETAIL_TRAP').slice(0, 3);
  }, [stealthAnomalies]);

  // Top 3 High-Conviction Champion Compounders auto-ranker
  const topChampions = useMemo(() => {
    const compPool = championPool.length > 0 ? championPool : companies;
    if (!compPool || compPool.length === 0) return [];

    const scored = compPool.map((c) => {
      const divMatch = dividendOpps.find((d) => d.StockCode === c.code);
      const stealthMatch = stealthAnomalies.find((a) => a.StockCode === c.code);
      const roe = c.roe ?? 0;
      const yieldPct = c.yield ?? divMatch?.DividendYield ?? 0;
      const pbv = c.pbv ?? c.price_bv ?? 0;
      const price = c.price ?? c.previous_price ?? divMatch?.Price ?? 0;
      const chg = c.daily_change ?? (c.previous_price && c.price ? c.price - c.previous_price : 0);
      const chgPct = (c as any).daily_change_pct ?? stealthMatch?.PriceChangePct ?? (c.previous_price && c.previous_price > 0 ? (chg / c.previous_price) * 100 : 0);

      const isTrap = c.is_value_trap || stealthMatch?.Signal === 'RETAIL_TRAP';
      const trapScore = divMatch?.TrapScore ?? 25;
      if (price <= 0 || isTrap || trapScore > 65) {
        return null;
      }

      let score = 0;
      // 0. Compounder & Quality Score Bonus: up to 25 pts
      if (c.compounder_score && c.compounder_score >= 75) score += 30;
      else if (c.compounder_score && c.compounder_score >= 65) score += 20;

      // 1. High ROE (cash generator): up to 35 pts
      if (roe >= 20) score += 35;
      else if (roe >= 15) score += 28;
      else if (roe >= 10) score += 18;
      else if (roe >= 5) score += 8;

      // 2. Safe Dividend Yield: up to 30 pts
      if (yieldPct >= 6.0) score += 30;
      else if (yieldPct >= 4.0) score += 24;
      else if (yieldPct >= 2.5) score += 15;

      // 3. Discount Valuation (PBV / Sector Justified): up to 20 pts
      if (c.valuation_status === 'SECTOR_UNDERVALUED') score += 20;
      else if (pbv > 0 && pbv <= 1.5) score += 20;
      else if (pbv > 0 && pbv <= 2.5) score += 14;
      else if (pbv > 0 && pbv <= 4.0) score += 8;

      // 4. Blue Chip / Stability: 15 pts
      if (c.is_blue_chip) score += 15;

      // 5. Smart Money Accumulation: +25 pts
      const isStealth = stealthMatch?.Signal === 'STEALTH_ACCUMULATION';
      if (isStealth) score += 25;

      // 6. Pristine Dividend Trap Free: +15 pts
      if (trapScore <= 30 && yieldPct >= 3.5) score += 15;

      // Generate wealth verdict & badges
      const badges: string[] = [];
      if (isStealth) badges.push('Smart Money Inflow');
      if (yieldPct >= 5.0) badges.push(`${yieldPct.toFixed(1)}% Safe Yield`);
      if (roe >= 15.0) badges.push(`${roe.toFixed(1)}% ROE Cash Cow`);
      if (c.is_blue_chip) badges.push('LQ45 Blue Chip');
      if (pbv > 0 && pbv < 1.8) badges.push('Undervalued');

      let verdict = 'Premier blue-chip compounder with robust capital returns and institutional backing.';
      if (isStealth && yieldPct >= 4.0) {
        verdict = 'Institutional heavyweights are quietly soaking up supply while paying a lucrative, safe dividend.';
      } else if (isStealth) {
        verdict = 'Heavy institutional stealth accumulation detected without retail hype. Prime early entry.';
      } else if (yieldPct >= 7.0 && roe >= 15.0) {
        verdict = 'Exceptional high-yield dividend gem backed by enormous return on equity and pristine cash coverage.';
      } else if (roe >= 20.0) {
        verdict = 'Elite compounding engine generating massive cash profits per rupiah invested.';
      } else if (pbv > 0 && pbv < 1.2 && roe >= 12.0) {
        verdict = 'Deep value opportunity trading beneath replacement cost with sustained profitability.';
      }

      return {
        company: c,
        score,
        verdict,
        badges: badges.slice(0, 3),
        roe,
        yieldPct,
        pbv,
        price,
        chg,
        chgPct,
        isStealth,
      };
    }).filter((item): item is NonNullable<typeof item> => item !== null);

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 3);
  }, [championPool, companies, stealthAnomalies, dividendOpps]);

  const totalPages = Math.max(1, Math.ceil(totalCompanies / pageSize));

  const handleSort = (key: string) => {
    let resolvedKey = key;
    if (key === 'score') resolvedKey = 'compounder_score';
    if (key === 'pbv') resolvedKey = 'price_bv';
    if (sortKey === resolvedKey || sortKey === key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(resolvedKey);
      setSortDir(resolvedKey === 'code' ? 'asc' : 'desc');
    }
    setCurrentPage(1);
  };

  return (
    <div className="alpha-hub" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Beginner Welcome Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.7) 100%)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        borderRadius: '16px',
        padding: '1.5rem 2rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
            <Compass size={28} style={{ color: '#38bdf8' }} />
            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800 }}>Alpha Finder & Opportunity Hub</h2>
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.9rem', maxWidth: '650px', lineHeight: 1.5 }}>
            Automated intelligence identifying what institutions are accumulating, which dividends are 100% safe, and which retail traps to avoid.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleOpenBriefing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.6rem 1.25rem',
              borderRadius: '10px',
              background: 'rgba(234, 179, 8, 0.2)',
              border: '1px solid rgba(234, 179, 8, 0.45)',
              color: '#facc15',
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              boxShadow: '0 0 16px rgba(234, 179, 8, 0.15)',
              transition: 'all 0.2s ease',
            }}
          >
            <Zap size={16} />
            <span>Today's Market Wrap</span>
          </button>

          <button
            onClick={loadIntelligence}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.6rem 1.25rem',
              borderRadius: '10px',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#38bdf8',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            <RotateCw size={15} className={loading ? 'spinning' : ''} />
            <span>Refresh Alpha</span>
          </button>
        </div>
      </div>

      {/* Top 3 High-Conviction Champion Compounders of the Week */}
      {topChampions.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)',
          border: '1px solid rgba(234, 179, 8, 0.35)',
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.35), 0 0 20px rgba(234, 179, 8, 0.08)',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem',
        }}>
          {/* Section Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '0.75rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            paddingBottom: '1rem',
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                <Sparkles size={22} style={{ color: '#facc15' }} />
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>
                  Top 3 High-Conviction Champion Compounders
                </h3>
                <span style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '12px',
                  background: 'rgba(234, 179, 8, 0.15)',
                  border: '1px solid rgba(234, 179, 8, 0.35)',
                  color: '#facc15',
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  letterSpacing: '0.5px',
                }}>
                  NEWBIE WEALTH LAUNCHPAD
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
                Algorithmic ranking uniting high cashflow ROE, safe dividend yields, institutional stealth accumulation, and deep value.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
              <Award size={16} style={{ color: '#facc15' }} />
              <span>Ranked across {totalCompanies > 0 ? totalCompanies : companies.length} IDX stocks</span>
            </div>
          </div>

          {/* Cards Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.25rem',
          }}>
            {topChampions.map((item, idx) => {
              const c = item.company;
              const starred = isStarred(c.code);
              const rankThemes = [
                {
                  rankTitle: '🏆 #1 Top Champion Pick',
                  border: '1px solid rgba(234, 179, 8, 0.45)',
                  glow: '0 8px 24px rgba(234, 179, 8, 0.12)',
                  badgeBg: 'rgba(234, 179, 8, 0.2)',
                  badgeColor: '#facc15',
                  accentBg: 'linear-gradient(180deg, rgba(234, 179, 8, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
                {
                  rankTitle: '🥈 #2 Quality Runner-Up',
                  border: '1px solid rgba(56, 189, 248, 0.45)',
                  glow: '0 8px 24px rgba(56, 189, 248, 0.12)',
                  badgeBg: 'rgba(56, 189, 248, 0.2)',
                  badgeColor: '#38bdf8',
                  accentBg: 'linear-gradient(180deg, rgba(56, 189, 248, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
                {
                  rankTitle: '🥉 #3 High Conviction',
                  border: '1px solid rgba(16, 185, 129, 0.45)',
                  glow: '0 8px 24px rgba(16, 185, 129, 0.12)',
                  badgeBg: 'rgba(16, 185, 129, 0.2)',
                  badgeColor: '#34d399',
                  accentBg: 'linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
              ];
              const theme = rankThemes[idx] || rankThemes[2];

              return (
                <div
                  key={c.code}
                  style={{
                    background: theme.accentBg,
                    border: theme.border,
                    boxShadow: theme.glow,
                    borderRadius: '14px',
                    padding: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '1rem',
                  }}
                >
                  <div>
                    {/* Top Row: Rank Tag & Star */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <span style={{
                        padding: '0.2rem 0.6rem',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 800,
                        background: theme.badgeBg,
                        color: theme.badgeColor,
                      }}>
                        {theme.rankTitle}
                      </span>
                      <button
                        onClick={() => onToggleStar(c)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          color: starred ? '#facc15' : 'rgba(255, 255, 255, 0.3)',
                          padding: 0,
                        }}
                        title={starred ? 'Starred' : 'Add to Watchlist'}
                      >
                        <Star size={18} fill={starred ? '#facc15' : 'none'} />
                      </button>
                    </div>

                    {/* Stock Code & Price */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#ffffff' }}>
                            {c.code}
                          </span>
                          {c.is_blue_chip && (
                            <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', fontWeight: 700 }}>
                              LQ45
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#94a3b8', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.name}
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc' }}>
                          Rp {item.price.toLocaleString()}
                        </div>
                        <div style={{
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          color: item.chg > 0 ? '#10b981' : item.chg < 0 ? '#ef4444' : '#94a3b8'
                        }}>
                          {item.chg > 0
                            ? `+${item.chg.toLocaleString()} (+${item.chgPct.toFixed(1)}%)`
                            : item.chg < 0
                            ? `${item.chg.toLocaleString()} (${item.chgPct.toFixed(1)}%)`
                            : '0 (0.0%)'}
                        </div>
                      </div>
                    </div>

                    {/* Plain-English Wealth Verdict Box */}
                    <div style={{
                      background: 'rgba(0, 0, 0, 0.3)',
                      borderLeft: `3px solid ${theme.badgeColor}`,
                      borderRadius: '0 8px 8px 0',
                      padding: '0.6rem 0.75rem',
                      marginBottom: '0.85rem',
                    }}>
                      <div style={{ fontSize: '0.72rem', color: theme.badgeColor, fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.2rem' }}>
                        Why this builds wealth
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                        {item.verdict}
                      </div>
                    </div>

                    {/* Key Metric Pills */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem', marginBottom: '0.75rem' }}>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>ROE</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.roe >= 15 ? '#10b981' : '#f8fafc' }}>
                          {item.roe ? `${item.roe}%` : '—'}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Yield</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.yieldPct >= 4 ? '#facc15' : '#94a3b8' }}>
                          {item.yieldPct ? `${item.yieldPct.toFixed(1)}%` : '—'}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>PBV</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.pbv > 0 && item.pbv <= 2 ? '#38bdf8' : '#f8fafc' }}>
                          {item.pbv ? `${item.pbv}x` : '—'}
                        </div>
                      </div>
                    </div>

                    {/* Badges */}
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {item.badges.map((b) => (
                        <span
                          key={b}
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            padding: '0.15rem 0.45rem',
                            borderRadius: '4px',
                            background: 'rgba(255, 255, 255, 0.06)',
                            color: '#cbd5e1',
                          }}
                        >
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Actions Bottom Bar */}
                  <div style={{ display: 'flex', gap: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <button
                      onClick={() => onOpenMemo(c)}
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: '8px',
                        padding: '0.5rem',
                        color: '#cbd5e1',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                      }}
                    >
                      <FileText size={13} />
                      <span>Memo</span>
                    </button>

                    <button
                      onClick={() => onSelectStock(c.code)}
                      style={{
                        flex: 2,
                        background: theme.badgeBg,
                        border: `1px solid ${theme.badgeColor}60`,
                        borderRadius: '8px',
                        padding: '0.5rem',
                        color: theme.badgeColor,
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '5px',
                      }}
                    >
                      <span>Trade in Terminal</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3 Glowing Outcome Cards (Newbie-First) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '1.25rem',
      }}>
        {/* Smart Money Accumulation Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          boxShadow: '0 8px 24px rgba(16, 185, 129, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🟢</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Smart Money Accumulating
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 700 }}>
                HOT
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              Big institutional brokers are soaking up supply without letting prices rise yet. Perfect entry before a breakout.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topSmartMoney.length > 0 ? (
                topSmartMoney.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#34d399' }}>
                      <span>Net {item.NetForeignFlowRpB != null ? `${item.NetForeignFlowRpB > 0 ? '+' : ''}Rp ${item.NetForeignFlowRpB}B` : '—'}</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Scanning order book for stealth accumulation...</div>
              )}
            </div>
          </div>

          <button
            onClick={() => { setActiveCategory('smart_money'); setCurrentPage(1); }}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            View All Smart Money Picks &rarr;
          </button>
        </div>

        {/* Cashflow Dividend Gems Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          boxShadow: '0 8px 24px rgba(234, 179, 8, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🟡</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Cashflow Dividend Gems
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', fontWeight: 700 }}>
                SAFE
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              High yield cashflow (5%–16%) backed by pristine cash coverage and healthy profits. Zero dividend trap risk.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topDividends.length > 0 ? (
                topDividends.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#facc15' }}>
                      <span>Yield {item.DividendYield.toFixed(1)}%</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Finding safe high yield distributions...</div>
              )}
            </div>
          </div>

          <button
            onClick={() => { setActiveCategory('dividends'); setCurrentPage(1); }}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(234, 179, 8, 0.15)',
              color: '#facc15',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            View All Dividend Gems &rarr;
          </button>
        </div>

        {/* Danger Shield Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          boxShadow: '0 8px 24px rgba(239, 68, 68, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🔴</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Retail Traps (Avoid)
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', fontWeight: 700 }}>
                WARNING
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              Stocks being aggressively pumped by retail while foreign and big institutional money are dumping inventory.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topTraps.length > 0 ? (
                topTraps.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#f87171' }}>
                      <span>Retail Pump ({item.PriceChangePct > 0 ? `+${item.PriceChangePct}%` : `${item.PriceChangePct}%`})</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No aggressive retail distribution pumps detected.</div>
              )}
            </div>
          </div>

          <button
            onClick={() => { setActiveCategory('danger'); setCurrentPage(1); }}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(239, 68, 68, 0.15)',
              color: '#f87171',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            Inspect Danger Shield &rarr;
          </button>
        </div>
      </div>

      {/* Main Filter Bar & Search */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.25rem 1.5rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        {/* Category Toggle Pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Opportunities', icon: Compass },
            { id: 'dca_prime', label: '⭐ Layak Tabung (DCA)', icon: Sparkles },
            { id: 'sharia', label: '☪ Sharia (ISSI)', icon: ShieldCheck },
            { id: 'value', label: 'Undervalued Quality', icon: TrendingUp },
            { id: 'smart_money', label: 'Smart Money (Bandarmology)', icon: Zap },
            { id: 'dividends', label: 'Cashflow Gems', icon: Coins },
            { id: 'danger', label: 'Danger Shield', icon: ShieldAlert },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeCategory === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveCategory(tab.id as any);
                  setCurrentPage(1);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.85rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: isActive ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.08)',
                  background: isActive ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                  color: isActive ? '#38bdf8' : '#9ca3af',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={14} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Live Search */}
        <div style={{ position: 'relative', width: '220px' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search code or sector..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem 0.5rem 2rem',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              background: 'rgba(0, 0, 0, 0.3)',
              color: '#f8fafc',
              fontSize: '0.85rem',
            }}
          />
        </div>
      </div>

      {/* Main Table */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.55)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
        overflowX: 'auto',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
              <th style={{ padding: '0.75rem 0.5rem', width: '40px' }}>Star</th>
              <th
                onClick={() => handleSort('code')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>Stock</span>
                  {sortKey === 'code' ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th
                onClick={() => handleSort('price')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>Price & Change</span>
                  {sortKey === 'price' ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th
                onClick={() => handleSort('compounder_score')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>Plain-English Verdict</span>
                  {(sortKey === 'compounder_score' || sortKey === 'score') ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th
                onClick={() => handleSort('roe')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>ROE %</span>
                  {sortKey === 'roe' ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th
                onClick={() => handleSort('price_bv')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>PBV</span>
                  {(sortKey === 'price_bv' || sortKey === 'pbv') ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th
                onClick={() => handleSort('yield')}
                style={{ padding: '0.75rem 0.5rem', cursor: 'pointer', userSelect: 'none' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <span>Yield</span>
                  {(sortKey === 'yield' || sortKey === 'dividend_yield_pct') ? (sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : <ArrowUpDown size={14} style={{ opacity: 0.3 }} />}
                </div>
              </th>
              <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {loadingCompanies ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem 1rem', color: '#94a3b8' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                    <RotateCw size={18} className="spinning" />
                    <span>Loading opportunities...</span>
                  </div>
                </td>
              </tr>
            ) : companies.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
                  No companies found matching criteria.
                </td>
              </tr>
            ) : (
              companies.map((c) => {
              const divMatch = dividendOpps.find((d) => d.StockCode === c.code);
              const stealthMatch = stealthAnomalies.find((a) => a.StockCode === c.code);
              const price = c.price ?? c.previous_price ?? divMatch?.Price ?? 0;
              const chg = c.daily_change ?? (c.previous_price && c.price ? c.price - c.previous_price : 0);
              const chgPct = (c as any).daily_change_pct ?? stealthMatch?.PriceChangePct ?? (c.previous_price && c.previous_price > 0 ? (chg / c.previous_price) * 100 : 0);
              const starred = isStarred(c.code);

              // Plain English verdict derived strictly from quantitative fundamentals
              const isStealth = stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'STEALTH_ACCUMULATION');
              const isTrap = stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'RETAIL_TRAP');
              const isGoodDiv = (c.yield ?? c.dividend_yield_pct ?? 0) >= 5.0 || (divMatch?.DividendYield ?? 0) >= 5.0;
              const isLossOrTrap = c.is_value_trap || (c.roe != null && c.roe < 0) || (c.npm != null && c.npm < 0) || isTrap;
              const isPrime = c.dca_verdict === 'PRIME_DCA' || (c.compounder_score ?? 0) >= 70;
              const isAcc = c.dca_verdict === 'ACCUMULATE' || ((c.compounder_score ?? 0) >= 50 && (c.roe ?? 0) >= 12.0);

              let verdictBadge = { text: 'Neutral / Watchlist', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)' };
              if (isLossOrTrap) {
                verdictBadge = { text: 'Danger • Value Trap / Loss', color: '#f87171', bg: 'rgba(239, 68, 68, 0.2)' };
              } else if (isStealth) {
                verdictBadge = { text: 'Smart Money Accumulation', color: '#34d399', bg: 'rgba(16, 185, 129, 0.2)' };
              } else if (isPrime) {
                verdictBadge = { text: '⭐ Prime DCA Compounder', color: '#10b981', bg: 'rgba(16, 185, 129, 0.2)' };
              } else if (isGoodDiv) {
                verdictBadge = { text: 'Safe Cashflow Gem', color: '#facc15', bg: 'rgba(234, 179, 8, 0.2)' };
              } else if (isAcc) {
                verdictBadge = { text: 'Layak Koleksi (Accumulate)', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' };
              } else if (c.is_undervalued || c.valuation_status === 'SECTOR_UNDERVALUED') {
                verdictBadge = { text: 'Undervalued Quality', color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.15)' };
              } else if (c.dca_verdict === 'SPECULATIVE') {
                verdictBadge = { text: 'Spekulatif / Watchlist', color: '#fb923c', bg: 'rgba(251, 146, 60, 0.15)' };
              }

              return (
                <tr
                  key={c.code}
                  onClick={() => onSelectStock(c.code)}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    cursor: 'pointer',
                  }}
                  className="table-row-hover"
                >
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleStar(c);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: starred ? '#facc15' : 'rgba(255, 255, 255, 0.2)',
                        padding: 0,
                      }}
                      title={starred ? 'Starred' : 'Add to Watchlist'}
                    >
                      <Star size={16} fill={starred ? '#facc15' : 'none'} />
                    </button>
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>{c.code}</strong>
                        {c.is_blue_chip && (
                          <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
                            LQ45
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    {price > 0 ? (
                      <>
                        <div style={{ fontWeight: 700, color: '#f8fafc' }}>
                          Rp {price.toLocaleString()}
                        </div>
                        <div style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: chg > 0 ? '#10b981' : chg < 0 ? '#ef4444' : '#94a3b8'
                        }}>
                          {chg > 0
                            ? `+${chg.toLocaleString()} (+${chgPct.toFixed(1)}%)`
                            : chg < 0
                            ? `${chg.toLocaleString()} (${chgPct.toFixed(1)}%)`
                            : '0 (0.0%)'}
                        </div>
                      </>
                    ) : (
                      <>
                        <div style={{ fontWeight: 600, color: '#64748b' }}>—</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>—</div>
                      </>
                    )}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <span style={{
                      padding: '0.25rem 0.6rem',
                      borderRadius: '6px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      color: verdictBadge.color,
                      background: verdictBadge.bg,
                      border: `1px solid ${verdictBadge.color}40`,
                    }}>
                      {verdictBadge.text}
                    </span>
                  </td>
                  <td style={{
                    padding: '0.85rem 0.5rem',
                    fontWeight: 600,
                    color: (c.roe ?? 0) < 0 ? '#f87171' : ((c.roe ?? 0) >= 15 ? '#10b981' : '#cbd5e1'),
                  }}>
                    {c.roe != null ? `${Number(c.roe).toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', color: '#cbd5e1' }}>
                    {c.pbv ?? c.price_bv ? (
                      <div>
                        <span style={{ color: (c.pbv ?? c.price_bv)! < 0 ? '#f87171' : '#cbd5e1', fontWeight: (c.pbv ?? c.price_bv)! < 0 ? 700 : 400 }}>
                          {(c.pbv ?? c.price_bv)!.toFixed(2)}x
                        </span>
                        {(c.pbv ?? c.price_bv)! < 0 ? (
                          <div style={{ fontSize: '0.68rem', color: '#f87171', fontWeight: 600 }}>
                            Defisiensi Modal
                          </div>
                        ) : c.justified_pbv ? (
                          <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                            Fair: {c.justified_pbv.toFixed(2)}x
                          </div>
                        ) : null}
                      </div>
                    ) : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', fontWeight: 700, color: (c.yield ?? c.dividend_yield_pct ?? 0) >= 4 ? '#eab308' : '#94a3b8' }}>
                    {(c.yield ?? c.dividend_yield_pct ?? 0) > 0 ? `${(c.yield ?? c.dividend_yield_pct)!.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenMemo(c);
                        }}
                        style={{
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#cbd5e1',
                          padding: '0.35rem 0.6rem',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                        title="1-Click Printable Memo"
                      >
                        <FileText size={12} />
                        <span>Memo</span>
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectStock(c.code);
                        }}
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid rgba(56, 189, 248, 0.3)',
                          color: '#38bdf8',
                          padding: '0.35rem 0.6rem',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                      >
                        <span>Terminal</span>
                        <ArrowRight size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
            )}
          </tbody>
        </table>

        {/* Pagination & Rows Info */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '1.25rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          flexWrap: 'wrap',
          gap: '1rem',
          fontSize: '0.85rem',
          color: '#94a3b8',
        }}>
          <div>
            {loadingCompanies ? (
              <span>Loading companies...</span>
            ) : (
              <>
                Showing <strong style={{ color: '#f8fafc' }}>{totalCompanies === 0 ? 0 : (currentPage - 1) * pageSize + 1}</strong> to{' '}
                <strong style={{ color: '#f8fafc' }}>{Math.min(currentPage * pageSize, totalCompanies)}</strong> of{' '}
                <strong style={{ color: '#38bdf8' }}>{totalCompanies}</strong> companies
              </>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  color: '#f8fafc',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '6px',
                  padding: '0.25rem 0.5rem',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1 || loadingCompanies}
                style={{
                  background: (currentPage === 1 || loadingCompanies) ? 'rgba(255, 255, 255, 0.03)' : 'rgba(255, 255, 255, 0.1)',
                  color: (currentPage === 1 || loadingCompanies) ? '#64748b' : '#f8fafc',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '6px',
                  padding: '0.35rem 0.6rem',
                  cursor: (currentPage === 1 || loadingCompanies) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <ChevronLeft size={16} />
              </button>

              <span style={{ padding: '0 0.5rem', fontWeight: 600, color: '#f8fafc' }}>
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages || loadingCompanies}
                style={{
                  background: (currentPage >= totalPages || loadingCompanies) ? 'rgba(255, 255, 255, 0.03)' : 'rgba(255, 255, 255, 0.1)',
                  color: (currentPage >= totalPages || loadingCompanies) ? '#64748b' : '#f8fafc',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '6px',
                  padding: '0.35rem 0.6rem',
                  cursor: (currentPage >= totalPages || loadingCompanies) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Daily Market-Close Executive Briefing Modal */}
      {briefingOpen && (
        <DailyBriefingModal
          briefingData={briefingData}
          onClose={() => setBriefingOpen(false)}
          onSelectStock={onSelectStock}
        />
      )}
    </div>
  );
};
