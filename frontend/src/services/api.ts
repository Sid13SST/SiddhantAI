import { PersonaProfile, BookingSlot } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function fetchPersonaProfile(): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/api/v1/search/persona`);
  if (!res.ok) {
    throw new Error('Failed to fetch persona profile');
  }
  return res.json();
}

export interface AvailabilityResponse {
  timezone: string;
  slots: BookingSlot[];
}

export async function fetchAvailability(
  timezone: string = 'IST',
  durationMinutes: number = 30
): Promise<AvailabilityResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/booking/availability?timezone=${timezone}&duration_minutes=${durationMinutes}`
  );
  if (!res.ok) {
    throw new Error('Failed to fetch slot availability');
  }
  return res.json();
}

export interface BookingCreateRequest {
  start_time: string;
  duration_minutes: number;
  attendee_email: string;
  interest_topic?: string;
  timezone: string;
}

export interface BookingCreateResponse {
  confirmation_id: string;
  title: string;
  start_time: string;
  end_time: string;
  timezone: string;
  attendee_email: string;
  description: string;
  html_link: string;
}

export async function createBooking(
  data: BookingCreateRequest
): Promise<BookingCreateResponse> {
  const res = await fetch(`${API_BASE}/api/v1/booking/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create booking');
  }
  return res.json();
}

export interface BookingCancelRequest {
  event_id?: string;
  attendee_email?: string;
}

export async function cancelBooking(data: BookingCancelRequest): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/booking/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to cancel booking');
  }
  return res.json();
}

export interface BookingRescheduleRequest {
  event_id: string;
  new_start_time: string;
  timezone: string;
}

export async function rescheduleBooking(
  data: BookingRescheduleRequest
): Promise<{ status: string; message: string; details: any }> {
  const res = await fetch(`${API_BASE}/api/v1/booking/reschedule`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to reschedule booking');
  }
  return res.json();
}
export { API_BASE };
