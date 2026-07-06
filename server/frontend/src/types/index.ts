export interface Task {
  id: number
  name: string
  type: 'keyword' | 'user' | 'mixed'
  keywords: string
  users: string
  schedule: string
  enabled: number
  created_at: string
  updated_at: string
}

export interface TaskRun {
  id: number
  task_id: number
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  error_msg: string
}

export interface Tweet {
  id: number
  tweet_id: string
  task_run_id: number
  task_id: number
  author: string
  text: string
  time: string
  url: string
  crawled_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface Stats {
  total_tasks: number
  enabled_tasks: number
  runs_today: number
  last_run_at: string | null
}
