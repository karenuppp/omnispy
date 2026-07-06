import axios from 'axios'
import type { Task, TaskRun, Tweet, PaginatedResponse, Stats } from '../types'

const api = axios.create({ baseURL: '/api' })

// Tasks
export function listTasks(page = 1, size = 20) {
  return api.get<PaginatedResponse<Task>>('/tasks', { params: { page, size } })
}

export function getTask(id: number) {
  return api.get<Task>(`/tasks/${id}`)
}

export function createTask(data: Partial<Task>) {
  return api.post<Task>('/tasks', data)
}

export function updateTask(id: number, data: Partial<Task>) {
  return api.put<Task>(`/tasks/${id}`, data)
}

export function deleteTask(id: number) {
  return api.delete(`/tasks/${id}`)
}

export function toggleTask(id: number) {
  return api.post<Task>(`/tasks/${id}/toggle`)
}

export function triggerRun(id: number) {
  return api.post<{ tweets: Tweet[]; count: number }>(`/tasks/${id}/run`)
}

// Runs & Tweets
export function listRuns(taskId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<TaskRun>>(`/tasks/${taskId}/runs`, { params: { page, size } })
}

export function listRunTweets(runId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<Tweet>>(`/runs/${runId}/tweets`, { params: { page, size } })
}

export function listTaskTweets(taskId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<Tweet>>(`/tasks/${taskId}/tweets`, { params: { page, size } })
}

// Search
export function manualSearch(type: 'keyword' | 'user', keywords: string, users: string, limit = 20) {
  return api.post<{ tweets: Tweet[]; count: number }>('/search', { type, keywords, users, limit })
}

// Stats
export function getStats() {
  return api.get<Stats>('/stats')
}
