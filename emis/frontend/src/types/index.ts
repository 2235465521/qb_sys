// EMIS 全局 TypeScript 类型定义

// ── 通用 ─────────────────────────────────────────────────

export interface ApiResponse<T> {
  count?: number
  results?: T[]
  data?: T
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── 行政区划字典 ──────────────────────────────────────────

export interface Province {
  id: number
  code: string
  name: string
}

export interface City {
  id: number
  code: string
  name: string
  province_id: number
}

export interface District {
  id: number
  code: string
  name: string
  city_id: number
}

// ── 企业 ─────────────────────────────────────────────────

export interface Company {
  id: number
  name: string
  credit_code: string
  legal_person: string
  province_id?: number
  city_id?: number
  district_id?: number
  province_name: string
  city_name: string
  district_name: string
  latitude: number | null
  longitude: number | null
  contact: string
  address?: string
  status: 'active' | 'disabled'
  distance_km?: number | null
  standards_count?: number
  created_at: string
}

export interface CompanySearchParams {
  keyword?: string
  province_id?: number
  city_id?: number
  district_id?: number
  lat?: number
  lng?: number
  radius_km?: number
  ics?: string
  ccs?: string
  standard_logic?: 'AND' | 'OR'
  page?: number
}

// ── 标准 ─────────────────────────────────────────────────

export type StandardType = 'enterprise' | 'group' | 'national' | 'industry' | 'local'

export interface Standard {
  id: number
  standard_no: string
  clean_id: string
  type: StandardType
  type_display: string
  title: string
  company_name: string
  company_detail?: Company
  is_parsed: 'unparsed' | 'references_parsed' | 'indicators_parsed'
  citation_count: number
  status: string
  status_display: string
  publish_date?: string
  implement_date?: string
  pdf_url?: string | null
  all_chain?: number[]
  created_at: string
  normative_references?: NormativeReference[]
  snippet?: string
}

export interface NormativeReference {
  id: number
  cited_standard_no: string
  latest_standard_no: string
}

// ── 会员 ─────────────────────────────────────────────────

export type MemberStatus = 'active' | 'frozen' | 'expired'

export interface OrganizationCategory {
  id: number;
  name: string;
  code: string;
  is_system: boolean;
  created_at: string;
}

export interface MemberOrgRole {
  id: number;
  category: number;
  category_name: string;
  category_code: string;
  org_name: string;
  position: string;
}

export interface Member {
  id: number
  name: string
  company: string
  phone: string
  status: MemberStatus
  status_display: string
  notes: string
  roles?: MemberOrgRole[]
  created_at: string
}

// ── 短信 ─────────────────────────────────────────────────

export interface SmsTemplate {
  id: number
  name: string
  content: string
  is_active: boolean
  created_at: string
}

export interface SmsTask {
  id: number
  template: number
  template_name: string
  target_group: string
  status: string
  status_display: string
  total_count: number
  sent_count: number
  failed_count: number
  created_at: string
}
