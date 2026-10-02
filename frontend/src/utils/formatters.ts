export const formatNum = (val: number | null | undefined, digits = 2, fallback = '—') => {
  if (val == null || isNaN(Number(val))) {
    return fallback;
  }
  return Number(val).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

export const formatCurrency = (val: number | null | undefined, currency = 'Rp', digits = 0, fallback = '—') => {
  if (val == null || isNaN(Number(val))) {
    return fallback;
  }
  return `${currency} ${Number(val).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
};