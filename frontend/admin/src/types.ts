export type AdminRole = "owner" | "manager";
export type LeadStatus = "new" | "accepted" | "contacted" | "cancelled" | "done";
export type LeadType = "test_drive" | "buy" | "callback";

export interface AdminUser {
  id: number;
  username: string;
  role: AdminRole;
}

export interface Trim {
  id: number;
  car_id: number;
  name: string;
  price: number | null;
  is_active: boolean;
  sort_order: number;
}

export interface CarImage {
  id: number;
  car_id: number;
  path: string;
  thumbnail_path: string | null;
  is_cover: boolean;
  sort_order: number;
}

export interface Car {
  id: number;
  slug: string;
  brand: string;
  model: string;
  body_type: string;
  engine: string;
  power_hp: number;
  emission: string;
  drive: "AWD" | "FWD";
  transmission: string;
  seats: number;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  trims: Trim[];
  images: CarImage[];
}

export interface Lead {
  id: number;
  user_id: number | null;
  name: string;
  phone: string;
  car_id: number | null;
  trim_id: number | null;
  type: LeadType;
  comment: string | null;
  internal_note: string | null;
  status: LeadStatus;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  tg_id: number | null;
  name: string | null;
  username: string | null;
  phone: string | null;
  language: string;
  is_blocked: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminStats {
  users_total: number;
  users_new_30d: number;
  leads_today: number;
  leads_week: number;
  leads_month: number;
  leads_total: number;
  leads_by_status: Record<string, number>;
  leads_by_car: { car: string; count: number }[];
  conversion_new_to_done_percent: number;
  daily_leads_30d: { date: string; count: number }[];
}

export interface AppSettings {
  address: string;
  phones: string[];
  map_link: string | null;
  instagram: string;
  annual_interest_rate: number | null;
  working_hours: string | null;
  banner_text: string | null;
}

export interface BroadcastProgress {
  broadcast_id: string;
  status: "queued" | "running" | "completed" | "failed";
  total: number;
  processed: number;
  sent: number;
  failed: number;
  blocked: number;
  error?: string | null;
}

export interface AuditEntry {
  id: number;
  admin_user_id: number | null;
  action: string;
  entity: string;
  entity_id: string | null;
  before_json: string | null;
  after_json: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AdminAccount {
  id: number;
  username: string;
  role: AdminRole;
  is_active: boolean;
  created_at: string;
}
