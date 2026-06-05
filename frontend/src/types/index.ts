export interface EvidenceItem {
  source: string;
  snippet: string;
}

export interface BookingSlot {
  display: string;
  utc: string;
}

export interface BookingContext {
  step:
    | 'none'
    | 'ask_timezone'
    | 'ask_email'
    | 'ask_topic'
    | 'recommend_slots'
    | 'reschedule_recommend_slots'
    | 'ask_cancellation_email'
    | 'ask_reschedule_email';
  action: 'none' | 'booking' | 'cancellation' | 'reschedule';
  timezone?: string;
  duration?: number;
  email?: string | null;
  topic?: string | null;
  event_id?: string | null;
  available_slots?: BookingSlot[];
}

export interface Citation {
  text: string;
  source: string;
  snippet: string;
  index: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: Citation[];
  sources?: string[];
  confidence?: number;
  bookingContext?: BookingContext;
  loading?: boolean;
}

export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  metadata: {
    source_type?: string;
    file_path?: string;
    title?: string;
    retrieval_tags?: string[];
    [key: string]: any;
  };
}

export interface PersonaProfile {
  name: string;
  role: string;
  summary: string;
  experience: any[];
  skills: string[];
  projects: any[];
}
