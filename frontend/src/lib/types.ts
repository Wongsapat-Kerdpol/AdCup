// Mirrors backend/app/schemas. Decimal fields arrive as strings.

export type UserRole = "brand" | "creator" | "admin";

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: UserRole;
  avatar_url: string | null;
  wallet_balance: string;
  youtube_channel_id: string | null;
  youtube_channel_title: string | null;
  created_at: string;
}

// Creator payout account (GET/PUT /api/payout-method). Only a masked number ever comes back.
export type PayoutMethod = "promptpay" | "bank";

export interface PayoutAccount {
  method: PayoutMethod;
  bank_code: string | null;
  account_masked: string;
  account_name: string;
}

export interface PayoutMethodResponse {
  account: PayoutAccount | null;
  banks: { code: string; name: string }[];
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export type CampaignCategory = "logo" | "music" | "clipping" | "ugc";
export type CampaignStatus = "draft" | "active" | "paused" | "completed";
export type Platform = "youtube" | "tiktok";
export type CampaignSort =
  | "newest"
  | "highest_rate"
  | "highest_budget"
  | "most_available"
  | "ending_soon";

// pending = system check (round 1) · under_review = admin check (round 2) · approved = earning
export type SubmissionStatus = "pending" | "under_review" | "approved" | "rejected";

export interface Campaign {
  id: number;
  title: string;
  category: CampaignCategory;
  platforms: Platform[];
  thumbnail_url: string | null;
  status: CampaignStatus;
  total_budget: string;
  paid_out: string;
  paid_out_percent: number;
  remaining_budget: string;
  rate_per_1k_views: string;
  rate_per_1m_views: string;
  deadline: string | null;
  created_at: string;
  brand: { id: number; display_name: string; avatar_url: string | null };
}

export interface CampaignDetail extends Campaign {
  description: string;
  requirements: string;
  cap_per_post: string | null;
  cap_per_profile: string | null;
  min_views: number;
  is_funded: boolean;
}

// Person 1 — brand campaign management (POST/GET /api/brand/campaigns, PATCH/DELETE /api/brand/campaigns/{id})
export interface CampaignInput {
  title: string;
  description: string;
  requirements: string;
  category: CampaignCategory;
  platforms: Platform[];
  thumbnail_url: string | null;
  rate_per_1k_views: string;
  total_budget: string;
  cap_per_post: string | null;
  cap_per_profile: string | null;
  min_views: number;
  deadline: string | null;
}

export interface BrandCampaign extends CampaignDetail {
  stats: {
    submissions: Record<SubmissionStatus, number>;
    creators: number;
    total_views: number;
  };
}

// Person 2 — submissions (POST /api/submissions, GET /api/submissions/mine,
// GET /api/submissions/campaign/{id}, GET/POST /api/admin/review/*)
export type RejectedBy = "system" | "admin";

export interface Submission {
  id: number;
  campaign_id: number;
  creator_id: number;
  video_url: string;
  platform: string;
  external_video_id: string | null;
  video_title: string | null;
  video_channel_id: string | null;
  video_published_at: string | null;
  view_count: number;
  views_refreshed_at: string | null;
  status: SubmissionStatus;
  system_checked_at: string | null;
  reviewed_by_id: number | null;
  reviewed_at: string | null;
  approved_at: string | null;
  rejected_by: RejectedBy | null;
  rejection_reason: string | null;
  gross_amount: string;
  commission_amount: string;
  net_amount: string;
  paid_views: number;
  created_at: string;
  profile_cap_reached: boolean; // GET /api/submissions/mine only
}

export interface SubmissionForReview extends Submission {
  campaign_title: string;
  campaign_requirements: string;
  creator_name: string;
  // Linked account detection: other accounts of the same person in this campaign, and open flags.
  linked_accounts: { user_id: number; display_name: string; matched: string[] }[];
  group_gross_in_campaign: string;
  cap_per_profile: string | null;
  open_flags: {
    id: number;
    kind: LinkFlagKind;
    reasons: string[];
    score: number | null;
    amount: string | null;
    other_user_id: number | null;
    other_display_name: string | null;
  }[];
}

// Linked account detection — admin (GET /api/admin/links, POST /api/admin/link-flags/{id}/*).
// Only signal TYPES are ever returned, never the values.
export type LinkFlagKind = "suspected" | "hub" | "overage";
export type LinkFlagStatus = "open" | "confirmed" | "dismissed" | "resolved";
export type SignalType = "payout_account" | "google_sub" | "email_norm" | "device_id" | "ip";

export interface LinkedUser {
  id: number;
  display_name: string;
}

export interface LinkFlag {
  id: number;
  kind: LinkFlagKind;
  status: LinkFlagStatus;
  created_at: string;
  users: LinkedUser[];
  reasons: string[];
  score: number | null;
  signal_type: SignalType | null;
  campaign_id: number | null;
  campaign_title: string | null;
  amount: string | null;
  group_gross: string | null;
  cap_per_profile: string | null;
}

export interface LinksResponse {
  flags: LinkFlag[];
  groups: { group_id: number; members: LinkedUser[]; matched: string[] }[];
}

// Person 3 — video platforms (GET /api/platforms)
export interface PlatformStatus {
  name: Platform;
  label: string;
  account_label: string; // "YouTube channel", "TikTok account"
  supported: boolean; // accepted for submissions right now
  connected: boolean; // the current user linked an account on it
  account_name: string | null;
}

// Person 3 — mock checkout (POST /api/payments/checkout/{id})
export type PaymentMethod = "promptpay" | "card";

export interface CheckoutResponse {
  campaign_id: number;
  campaign_status: CampaignStatus;
  transaction_id: number;
  reference: string;
  amount: string;
  method: PaymentMethod;
  paid_at: string;
}

// Person 3 — wallet (GET /api/wallet, POST /api/wallet/withdraw)
export type TransactionType = "campaign_fund" | "payout" | "withdrawal";
export type TransactionStatus = "pending" | "completed" | "failed";

export interface WalletTransaction {
  id: number;
  type: TransactionType;
  status: TransactionStatus;
  gross_amount: string;
  commission_amount: string;
  net_amount: string;
  reference: string | null;
  campaign_id: number | null;
  campaign_title: string | null;
  submission_id: number | null;
  views_from: number | null;
  views_to: number | null;
  created_at: string;
}

export interface Wallet {
  balance: string;
  min_withdrawal: string;
  can_withdraw: boolean;
  withdrawals_on_hold: boolean; // linked account detection: an admin is reviewing the account
  total_earned: string;
  total_commission: string;
  total_withdrawn: string;
  transactions: WalletTransaction[];
}

export interface WithdrawResponse {
  balance: string;
  transaction: WalletTransaction;
}

// Person 3 — admin analytics (GET /api/admin/stats)
export interface AdminStats {
  users: {
    total: number;
    by_role: Record<UserRole, number>;
    new_last_30d: number;
    active_last_30d: number;
  };
  money: {
    total_funded: string;
    total_paid_out: string;
    commission_revenue: string;
    total_withdrawn: string;
    locked_in_pools: string;
    projected_commission: string;
    transaction_count: number;
  };
  daily: { day: string; paid_out: string; commission: string; funded: string }[];
  submissions_by_status: Record<SubmissionStatus, number>;
  campaigns_by_status: Record<CampaignStatus, number>;
  top_campaigns: {
    id: number;
    title: string;
    brand_name: string;
    status: CampaignStatus;
    total_budget: string;
    paid_out: string;
    paid_out_percent: number;
    submissions: number;
    approved: number;
    views: number;
  }[];
}

// Anti-fraud — duplicate-clip warnings (GET /api/admin/duplicates/{submission_id})
export interface DuplicateMatch {
  submission_id: number;
  campaign_id: number;
  campaign_title: string;
  creator_name: string;
  video_url: string;
  status: SubmissionStatus;
  submitted_at: string;
  net_paid: string;
  submitted_earlier: boolean; // sent before the clip being reviewed -> most likely the original
  days_apart: number;
  matched_pictures: number;
  total_pictures: number;
  similarity: number; // 0..1
  closest_distance: number; // Hamming distance out of 64 bits
  mirrored: boolean;
  level: "copy" | "check";
}

export interface DuplicateReport {
  enabled: boolean;
  status: "ok" | "no_pictures" | "unavailable" | "disabled";
  pictures_checked: number;
  level: "copy" | "check" | null;
  matches: DuplicateMatch[];
  comparisons: number;
  linear_comparisons: number;
}

// Admin — who submitted what (GET /api/admin/campaigns/{id}/submissions, /api/admin/submissions/{id})
export interface AdminSubmissionRow {
  id: number;
  campaign_id: number;
  creator_id: number;
  creator_name: string;
  youtube_channel_id: string | null;
  youtube_channel_title: string | null;
  video_url: string;
  external_video_id: string | null;
  video_title: string | null;
  status: SubmissionStatus;
  submitted_at: string;
  view_count: number;
  gross_amount: string;
  net_amount: string;
}

export interface AdminSubmissionDetail extends AdminSubmissionRow {
  campaign_title: string;
  creator_email: string;
  creator_joined_at: string;
  creator_submissions: number;
  creator_net_earned: string;
  video_channel_id: string | null;
  video_published_at: string | null;
  views_refreshed_at: string | null;
  paid_views: number;
  commission_amount: string;
  system_checked_at: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  rejected_by: RejectedBy | null;
  rejection_reason: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// Campaign outlook — GET /api/campaigns/{id}/outlook (is the campaign still worth joining?)
export type OutlookVerdict = "open" | "competitive" | "crowded" | "closed";

export interface CampaignOutlook {
  verdict: OutlookVerdict;
  pool_remaining: string;
  horizon_days: number;
  projected_claims: string;
  pressure: number | null;
  exhausted_in_days: number | null;
  exhausted_on: string | null;
  approved_videos: number;
  in_review_videos: number;
  newcomer: {
    views_per_day: number;
    assumption: "input" | "median" | "default";
    expected_gross: string;
    expected_net: string;
    fill_ratio: number | null;
  };
}

// POST /api/admin/payout-round
export interface PayoutRoundResult {
  campaigns_settled: number;
  payouts: number;
  total_gross: string;
  total_net: string;
}
