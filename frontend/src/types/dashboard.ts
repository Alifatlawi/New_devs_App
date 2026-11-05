export interface DashboardProperty {
  id: string;
  name: string;
  /** IANA time zone, e.g. "Europe/Paris". Monthly totals use the property's local calendar. */
  timezone: string;
}

export interface RevenuePeriod {
  year: number;
  /** 1-12 */
  month: number;
}

export interface RevenueSummaryData {
  property_id: string;
  /** Decimal string already rounded to cents by the API (e.g. "2250.00"). Never do float maths on it. */
  total_revenue: string;
  currency: string;
  reservations_count: number;
  year: number | null;
  month: number | null;
}
