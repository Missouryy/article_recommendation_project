export interface Paper {
  id: string
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
