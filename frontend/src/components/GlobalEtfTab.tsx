import React, { useState, useEffect, useMemo } from 'react';
import { 
  Globe, 
  RotateCw, 
  HelpCircle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { fetchGlobalETFs } from '../services/api';

export const GlobalEtfTab: React.FC = () => {
  const [etfs, setEtfs] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showEducation, setShowEducation] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchGlobalETFs();
      if (res && res.etfs) {
        setEtfs(res.etfs);
      }
    } catch (e: any) {
      console.error('Failed to load global ETFs', e);
      setError('Gagal memuat data ETF global. Pastikan koneksi internet stabil.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredEtfs = useMemo(() => {
    return etfs.filter((item) => {
      // Category filter
      if (selectedCategory !== 'all' && item.category !== selectedCategory) {
        return false;
      }
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTicker = item.ticker.toLowerCase().includes(q);
        const matchName = item.name.toLowerCase().includes(q);
        const matchUnderlying = item.underlying?.toLowerCase().includes(q);
        if (!matchTicker && !matchName && !matchUnderlying) return false;
      }
      return true;
    });
  }, [etfs, selectedCategory, searchQuery]);

  // Key spotlight picks
  const smh = etfs.find((e) => e.ticker === 'SMH');
  const jepq = etfs.find((e) => e.ticker === 'JEPQ');
  const msty = etfs.find((e) => e.ticker === 'MSTY');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', animation: 'fadeIn 0.3s ease' }}>
      {/* Header Banner */}
      <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
            <Globe size={24} style={{ color: 'var(--accent-blue)' }} />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc' }}>
              Global ETF & Pluang Radar
            </h2>
            <span style={{
              background: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--accent-blue)',
              padding: '0.2rem 0.6rem',
              borderRadius: '12px',
              fontSize: '0.75rem',
              fontWeight: 700,
              border: '1px solid rgba(56, 189, 248, 0.3)'
            }}>
              W-8BEN 15% TAX ADJUSTED
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '750px' }}>
            Pantau ETF Wall Street paling populer yang tersedia di aplikasi <strong>Pluang</strong> (kustodian DriveWealth AS). Dilengkapi kalkulator hasil bersih setelah pajak dividen 15% dan sistem pendeteksi jebakan pengikisan modal (NAV Decay Trap).
          </p>
        </div>

        <button 
          onClick={loadData}
          disabled={loading}
          className="btn-glass"
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', padding: '0.6rem 1rem' }}
        >
          <RotateCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh Data
        </button>
      </div>

      {/* 3 Top Spotlight Action Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: '1.25rem' }}>
        {/* Card 1: Top Growth Champion */}
        <div className="glass-card" style={{
          borderLeft: '4px solid #38bdf8',
          background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.05) 0%, rgba(15, 23, 42, 0.6) 100%)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.8rem' }}>
            <span style={{
              background: 'rgba(56, 189, 248, 0.2)',
              color: '#38bdf8',
              padding: '0.2rem 0.6rem',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              👑 TOP GROWTH CHAMPION
            </span>
            <strong style={{ fontSize: '1.2rem', color: '#fff' }}>${smh?.metrics?.current_price || '603.33'}</strong>
          </div>
          <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1.1rem', color: '#f8fafc' }}>
            SMH • VanEck Semiconductor
          </h3>
          <p style={{ margin: '0 0 0.8rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Juara return bursa global 3 tahun terakhir (+339%). Saat ini sedang diskon <strong>-10.2%</strong> dari rekor tertinggi. Pajak Capital Gain di AS: <strong>0%</strong>.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>3-Yr Return: <strong style={{ color: '#10b981' }}>+339.4%</strong></span>
            <span style={{ color: '#38bdf8', fontWeight: 700 }}>REKOMENDASI: BUY / DCA</span>
          </div>
        </div>

        {/* Card 2: Best Monthly Cashflow */}
        <div className="glass-card" style={{
          borderLeft: '4px solid #10b981',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(15, 23, 42, 0.6) 100%)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.8rem' }}>
            <span style={{
              background: 'rgba(16, 185, 129, 0.2)',
              color: '#10b981',
              padding: '0.2rem 0.6rem',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              💵 BEST MONTHLY INCOME
            </span>
            <strong style={{ fontSize: '1.2rem', color: '#fff' }}>${jepq?.metrics?.current_price || '61.09'}</strong>
          </div>
          <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1.1rem', color: '#f8fafc' }}>
            JEPQ • JPMorgan Nasdaq Premium
          </h3>
          <p style={{ margin: '0 0 0.8rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Dividen ~11.8% per tahun cair bulanan. Modal pokok tetap tumbuh sehat <strong>+19.6%</strong> tanpa tergerus. Net Yield setelah pajak 15%: <strong>10.0%</strong>.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Pencairan: <strong style={{ color: '#fff' }}>Bulanan</strong></span>
            <span style={{ color: '#10b981', fontWeight: 700 }}>REKOMENDASI: BUY FOR INCOME</span>
          </div>
        </div>

        {/* Card 3: NAV Decay Trap Warning */}
        <div className="glass-card" style={{
          borderLeft: '4px solid #ef4444',
          background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, rgba(15, 23, 42, 0.6) 100%)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.8rem' }}>
            <span style={{
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#ef4444',
              padding: '0.2rem 0.6rem',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              ⚠️ CAPITAL DECAY TRAP
            </span>
            <strong style={{ fontSize: '1.2rem', color: '#fff' }}>${msty?.metrics?.current_price || '15.66'}</strong>
          </div>
          <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1.1rem', color: '#f8fafc' }}>
            MSTY • YieldMax MSTR Option
          </h3>
          <p style={{ margin: '0 0 0.8rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Jebakan dividen semu! Harga modal anjlok <strong>-75.9%</strong> dalam 1 tahun. Kenaikan dibatasi sementara penurunan ikut jatuh bebas.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Status: <strong style={{ color: '#ef4444' }}>Kerusakan Modal</strong></span>
            <span style={{ color: '#ef4444', fontWeight: 700 }}>REKOMENDASI: HINDARI</span>
          </div>
        </div>
      </div>

      {/* Educational Collapsible Guide */}
      <div className="glass-card" style={{ padding: '1.25rem', border: '1px solid rgba(255,255,255,0.08)' }}>
        <div 
          onClick={() => setShowEducation(!showEducation)}
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <HelpCircle size={18} style={{ color: 'var(--accent-blue)' }} />
            <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
              Panduan Penting untuk Pemula (Pajak AS & Strategi Pluang)
            </h4>
          </div>
          {showEducation ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>

        {showEducation && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.85rem', borderRadius: '8px' }}>
              <strong style={{ color: '#38bdf8', display: 'block', marginBottom: '0.3rem' }}>
                1. Pajak Kenaikan Harga (Capital Gain) = 0% di AS
              </strong>
              Pemerintah AS membebaskan pajak capital gain untuk investor asing (WNI). Jika Anda beli <strong>SMH, QQQ, atau VOO</strong> lalu harganya naik, seluruh keuntungannya 100% utuh tanpa potongan pajak AS.
            </div>
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.85rem', borderRadius: '8px' }}>
              <strong style={{ color: '#f59e0b', display: 'block', marginBottom: '0.3rem' }}>
                2. Pajak Dividen Dipotong Otomatis 15%
              </strong>
              Untuk dividen tunai (seperti JEPQ/QQQI), kustodian AS langsung memotong pajak 15% (tarif treaty W-8BEN) sebelum uang masuk ke saldo Pluang Anda, baik uangnya ditarik ke bank maupun dibelikan saham lagi.
            </div>
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.85rem', borderRadius: '8px' }}>
              <strong style={{ color: '#ef4444', display: 'block', marginBottom: '0.3rem' }}>
                3. Kenapa MSTY/AMDY Berbahaya untuk Ditabung?
              </strong>
              Strategi opsi YieldMax membatasi keuntungan atas saat pasar naik, tetapi membiarkan penurunan ke bawah ikut terjun bebas. Modal pokok tergerus berkepanjangan sehingga uang gajian dividen nominalnya ikut menciut.
            </div>
          </div>
        )}
      </div>

      {/* Filter Tabs and Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'Semua ETF' },
            { id: 'growth', label: '🚀 Growth & Tech' },
            { id: 'income', label: '💵 Monthly Income' },
            { id: 'defensive', label: '🛡️ Defensive & Gold' },
            { id: 'speculative', label: '⚠️ High Risk / Traps' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedCategory(tab.id)}
              className={selectedCategory === tab.id ? 'btn-primary' : 'btn-glass'}
              style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem', borderRadius: '8px' }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <input 
          type="text"
          placeholder="Cari Ticker (e.g. SMH, JEPQ)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input-glass"
          style={{ width: '240px', padding: '0.45rem 0.8rem', fontSize: '0.85rem' }}
        />
      </div>

      {/* Main Interactive Table */}
      <div className="glass-card" style={{ padding: '0', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>
              <th style={{ padding: '0.9rem 1rem' }}>TICKER & NAMA</th>
              <th style={{ padding: '0.9rem 1rem' }}>HARGA</th>
              <th style={{ padding: '0.9rem 1rem' }}>1-YR RETURN</th>
              <th style={{ padding: '0.9rem 1rem' }}>3-YR RETURN</th>
              <th style={{ padding: '0.9rem 1rem' }}>DISKON 52W</th>
              <th style={{ padding: '0.9rem 1rem' }}>GROSS YIELD</th>
              <th style={{ padding: '0.9rem 1rem' }}>NET YIELD (15% TAX)</th>
              <th style={{ padding: '0.9rem 1rem' }}>KESEHATAN MODAL</th>
              <th style={{ padding: '0.9rem 1rem', textAlign: 'right' }}>VONIS KEPUTUSAN</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  Memuat data metrik ETF global...
                </td>
              </tr>
            ) : filteredEtfs.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  Tidak ada ETF yang cocok dengan kriteria pencarian.
                </td>
              </tr>
            ) : (
              filteredEtfs.map((etf) => {
                const m = etf.metrics || {};
                const v = etf.verdict || {};
                const isDiscounted = (m.pullback_52w_pct ?? 0) <= -8.0;

                return (
                  <tr 
                    key={etf.ticker}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Ticker & Name */}
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontWeight: 800, color: '#f8fafc', fontSize: '0.95rem' }}>{etf.ticker}</span>
                        <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)' }}>
                          {etf.issuer}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {etf.name}
                      </div>
                    </td>

                    {/* Price */}
                    <td style={{ padding: '0.85rem 1rem', fontWeight: 700, fontFamily: 'monospace', color: '#fff' }}>
                      ${m.current_price?.toFixed(2) || '—'}
                    </td>

                    {/* 1-Yr Return */}
                    <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', color: (m.total_return_1y ?? 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {(m.total_return_1y ?? 0) >= 0 ? '+' : ''}{m.total_return_1y?.toFixed(1) || '—'}%
                    </td>

                    {/* 3-Yr Return */}
                    <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', fontWeight: 700, color: (m.total_return_3y ?? 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {m.total_return_3y != null ? `${m.total_return_3y >= 0 ? '+' : ''}${m.total_return_3y.toFixed(1)}%` : '—'}
                    </td>

                    {/* 52W High Gap */}
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <span style={{
                        fontFamily: 'monospace',
                        color: isDiscounted ? '#38bdf8' : 'var(--text-secondary)',
                        fontWeight: isDiscounted ? 700 : 400
                      }}>
                        {m.pullback_52w_pct != null ? `${m.pullback_52w_pct.toFixed(1)}%` : '—'}
                      </span>
                      {isDiscounted && (
                        <span style={{ display: 'block', fontSize: '0.65rem', color: '#38bdf8' }}>Area Diskon</span>
                      )}
                    </td>

                    {/* Gross Yield */}
                    <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', color: (m.gross_yield_pct ?? 0) > 8 ? '#f59e0b' : '#fff' }}>
                      {m.gross_yield_pct?.toFixed(1) || '0.0'}%
                    </td>

                    {/* Net Yield (15% Tax) */}
                    <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', fontWeight: 700, color: (m.net_after_tax_yield_pct ?? 0) > 8 ? 'var(--accent-green)' : 'var(--text-secondary)' }}>
                      {m.net_after_tax_yield_pct?.toFixed(1) || '0.0'}%
                    </td>

                    {/* NAV Health Badge */}
                    <td style={{ padding: '0.85rem 1rem' }}>
                      {etf.nav_risk === 'CRITICAL_TRAP' && (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}>
                          MODAL RUSAK
                        </span>
                      )}
                      {etf.nav_risk === 'HIGH_RISK' && (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b' }}>
                          RISIKO TERGERUS
                        </span>
                      )}
                      {etf.nav_risk === 'LOW_RISK_INCOME' && (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(16, 185, 129, 0.2)', color: '#10b981' }}>
                          MODAL TUMBUH
                        </span>
                      )}
                      {etf.nav_risk === 'PRIME_GROWTH' && (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
                          PRIME GROWTH
                        </span>
                      )}
                      {etf.nav_risk === 'DEFENSIVE' && (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(168, 85, 247, 0.2)', color: '#a855f7' }}>
                          DEFENSIVE
                        </span>
                      )}
                    </td>

                    {/* Verdict */}
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>
                      <span style={{
                        padding: '0.25rem 0.65rem',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        background: v.bg || 'rgba(255,255,255,0.05)',
                        color: v.color || '#fff',
                        border: `1px solid ${v.border || 'transparent'}`
                      }}>
                        {v.action || 'HOLD'}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
