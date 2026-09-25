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

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export type CampaignCategory = "logo" | "music" | "clipping" | "ugc";
export type CampaignStatus = "draft" | "active" | "paused" | "completed";
export type Platform = "youtube" | "tiktok" | "instagram" | "x";
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

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
