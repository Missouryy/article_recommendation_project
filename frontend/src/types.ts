export interface Paper {
  id: string
  short_id?: string
  title: string
  author_names: string[]
  year?: number | string
  journal?: string
  citation_count?: number
  truth_value_score?: number
  abstract?: string
  keywords?: string[]
}

export interface Author {
  id: string
  name: string
  affiliation?: string
  h_index?: number
  citation_count?: number
  paper_count?: number
  research_areas?: string[]
  bio?: string
}

export interface Recommendation {
  paper: Paper;
  reason: string;
}

export interface TruthPaper extends Paper {
  truth_value: number;           // 0-1
  truth_value_percent: number;   // 0-100（后端已算好，一位小数）
  truth_value_text: string;      // "xx.x分"
}

export interface TruthResponse {
  items: TruthPaper[];
  total: number;
}