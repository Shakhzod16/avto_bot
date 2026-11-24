export interface Trim {
  id: number;
  name: string;
  price: number | null;
  is_active?: boolean;
}

export interface CarImage {
  id: number;
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
  drive: string;
  transmission: string;
  seats: number;
  description: string | null;
  image_url?: string | null;
  trims: Trim[];
  images: CarImage[];
}

export interface Contacts {
  name: string;
  address: string;
  phones: string[];
  instagram: string;
  map_link: string | null;
  telegram_url?: string | null;
  working_hours?: string | null;
}

export interface CreditResult {
  amount: number;
  initial_payment: number;
  loan_amount: number;
  initial_percent: number;
  months: number;
  annual_rate: number;
  monthly_payment: number;
  disclaimer: string;
}

export type LeadType = "test_drive" | "buy" | "callback";
