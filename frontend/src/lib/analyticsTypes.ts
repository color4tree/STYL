export type AnalyticsItemType = "product" | "accessory";
export type AnalyticsEventName =
  | "page_view" | "navigation_click" | "item_impression" | "item_detail_open"
  | "item_details_expand" | "media_open" | "cart_add" | "cart_quantity_change"
  | "cart_remove" | "cart_clear" | "cart_view" | "quote_open" | "quote_form_start"
  | "quote_submit_attempt" | "quote_error" | "catalog_empty" | "item_unavailable"
  | "engagement" | "site_error" | "web_vital";

export type AnalyticsItemReference = { itemType: AnalyticsItemType; itemId: number; quantity?: number };
export type AnalyticsProperties = Partial<AnalyticsItemReference> & {
  action?: "header" | "menu" | "catalog" | "details" | "continue_shopping" | "back_to_collection" | "section" | "quote" | "other";
  toPath?: string;
  source?: "header" | "cart" | "product" | "direct" | "unknown";
  list?: "products" | "accessories";
  mediaType?: "image" | "video";
  mediaIndex?: number;
  lineCount?: number;
  saleUnits?: number;
  activeMs?: number;
  errorCode?: "validation" | "network" | "storage" | "catalog" | "media" | "unknown";
  metric?: "LCP" | "INP" | "CLS";
  value?: number;
};

export type AnalyticsEvent = {
  name: AnalyticsEventName;
  path: string;
  properties?: AnalyticsProperties;
};

export type AnalyticsConfig = {
  enabled: boolean;
  mode: "aggregate-only";
  environment: string;
  timezone: string;
  heartbeatSeconds: number;
  idleSeconds: number;
  maxEvents: number;
  maxBatchBytes: number;
  allowedCampaigns: string[];
};

export type AnalyticsContext = {
  source?: string;
  medium?: string;
  campaign?: string;
  viewport?: "phone" | "tablet" | "desktop";
};

export type AnalyticsBreakdown = { label: string; pageViews: number };
export type AnalyticsItemStats = {
  itemType: AnalyticsItemType; itemId: number; name: string; category: string; currency: string;
  impressions: number; detailViews: number; expansions: number;
  mediaOpens: number; cartAdds: number; quoteOpens: number;
};

export type AnalyticsReport = {
  start: string;
  end: string;
  timezone: string;
  generatedAt: string;
  cutoffAt: string;
  environment: string;
  collectionEnabled: boolean;
  coverage: {
    mode: "aggregate-only";
    trackingSince: string | null;
    lastEventAt: string | null;
    warnings: string[];
    excluded: number;
    rejected: number;
  };
  summary: {
    pageViews: number;
    activeSeconds: number;
    savedInquiries: number | null;
  };
  comparison: { days: number; pageViewsDailyAverage: number; pageViewsChangePercent: number | null };
  countries: AnalyticsBreakdown[];
  sources: AnalyticsBreakdown[];
  campaigns: AnalyticsBreakdown[];
  devices: AnalyticsBreakdown[];
  browsers: AnalyticsBreakdown[];
  pages: { path: string; pageViews: number; activeSeconds: number }[];
  items: AnalyticsItemStats[];
  actions: { name: string; count: number }[];
  errors: { code: string; count: number }[];
  webVitals: { metric: string; count: number; average: number }[];
  daily: { date: string; pageViews: number; activeSeconds: number; inquiries: number }[];
  hourly: { hour: number; pageViews: number; activeSeconds: number }[];
  observations: string[];
};

export type AnalyticsEmailPreview = {
  reportDate: string;
  timezone: string;
  subject: string;
  text: string;
  html: string;
  emailEnabled: boolean;
  recipientsConfigured: boolean;
  nextRunAt: string;
};

export type AnalyticsDelivery = {
  reportDate: string;
  timezone: string;
  recipient: string;
  status: string;
  attempts: number;
  updatedAt: string;
  error: string | null;
};

export type AnalyticsEmailSettings = {
  enabled: boolean;
  recipients: string[];
  revision: number;
  source: "environment" | "admin";
  environment: "local" | "test" | "staging" | "production";
  effectiveEnabled: boolean;
  timezone: string;
  nextRunAt: string;
};
