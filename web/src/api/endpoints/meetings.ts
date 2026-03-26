import { apiClient, unwrap, unwrapPaginated, type PaginatedResult } from '../client'
import type {
  ApiResponse,
  MeetingFilters,
  MeetingResponse,
  PaginatedResponse,
  TriggerMeetingRequest,
} from '../types'

export async function listMeetings(filters?: MeetingFilters): Promise<PaginatedResult<MeetingResponse>> {
  const response = await apiClient.get<PaginatedResponse<MeetingResponse>>('/meetings', {
    params: filters,
  })
  return unwrapPaginated<MeetingResponse>(response)
}

export async function getMeeting(meetingId: string): Promise<MeetingResponse> {
  const response = await apiClient.get<ApiResponse<MeetingResponse>>(
    `/meetings/${encodeURIComponent(meetingId)}`,
  )
  return unwrap(response)
}

export async function triggerMeeting(
  data: TriggerMeetingRequest,
): Promise<MeetingResponse[]> {
  const response = await apiClient.post<ApiResponse<MeetingResponse[]>>('/meetings/trigger', data)
  return unwrap(response)
}
