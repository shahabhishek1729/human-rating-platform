export type ExperimentType = 'rating' | 'chat' | 'delegation';

export interface Experiment {
  id: number;
  name: string;
  created_at: string;
  num_ratings_per_question: number;
  experiment_type: ExperimentType;
  prolific_completion_url: string | null;
  question_count: number;
  rating_count: number;
}

export interface Question {
  id: number;
  question_id: string;
  question_text: string;
  options: string | null;
  question_type: string;
}

export interface ExperimentStats {
  experiment_name: string;
  total_questions: number;
  questions_complete: number;
  total_ratings: number;
  total_raters: number;
  target_ratings_per_question: number;
}

export interface Upload {
  id: number;
  filename: string;
  uploaded_at: string;
  question_count: number;
}

export interface ExperimentDocument {
  id: number;
  title: string;
  source_filename: string;
  chunk_count: number;
  created_at: string;
}

export interface ExperimentDocumentChunk {
  id: number;
  chunk_index: number;
  text: string;
  char_start: number;
  char_end: number;
}

export interface ExperimentDocumentPage {
  document_id: number;
  title: string;
  page: number;
  page_size: number;
  total_pages: number;
  total_chunks: number;
  chunks: ExperimentDocumentChunk[];
}

export interface ExperimentDocumentSearchResult {
  chunk_id: number;
  document_id: number;
  document_title: string;
  chunk_index: number;
  score: number;
  text: string;
  char_start: number;
  char_end: number;
}

export interface ExperimentDocumentSearchResponse {
  query: string;
  mode: 'lexical' | 'semantic' | 'hybrid';
  results: ExperimentDocumentSearchResult[];
}

export interface Session {
  rater_id: number;
  session_start: string;
  session_end_time: string;
  experiment_name: string;
  completion_url: string | null;
  experiment_type: ExperimentType;
  delegation_task_id: string | null;
  rater_session_token: string;
}

export interface RatingSubmit {
  question_id: number;
  answer: string;
  confidence: number;
  time_started: string;
}

export interface Analytics {
  experiment_name: string;
  overview: {
    total_ratings: number;
    total_questions: number;
    total_raters: number;
    avg_response_time_seconds: number;
    min_response_time_seconds?: number;
    max_response_time_seconds?: number;
    avg_confidence: number;
  };
  questions: QuestionAnalytics[];
  raters: RaterAnalytics[];
}

export interface QuestionAnalytics {
  question_id: string;
  question_text: string;
  num_ratings: number;
  avg_response_time_seconds: number;
  avg_confidence: number;
  answer_distribution: Record<string, number>;
}

export interface RaterAnalytics {
  prolific_id: string;
  study_id: string | null;
  session_start: string | null;
  num_ratings: number;
  total_response_time_seconds: number;
  avg_response_time_seconds: number;
  avg_confidence: number;
}

export interface ProlificStudyConfig {
  description: string;
  estimated_completion_time: number;
  reward: number;
  total_available_places: number;
  device_compatibility: string[];
}

export interface PlatformStatus {
  prolific_enabled: boolean;
  prolific_mode: 'disabled' | 'real';
}

export interface ExperimentCreate {
  name: string;
  num_ratings_per_question: number;
  experiment_type: ExperimentType;
  prolific_completion_url: string;
  prolific?: ProlificStudyConfig;
}

export interface SubtaskData {
  id: number;
  description: string;
  ai_answer: string;
  ai_reasoning: string;
  ai_confidence: number;
  needs_human_input: boolean;
}

export interface DelegationTask {
  id: string;
  instructions: string;
  question: string;
  delegation_data: SubtaskData[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ExperimentRound {
  id: number;
  round_number: number;
  prolific_study_id: string;
  prolific_study_status: string;
  places_requested: number;
  created_at: string;
  prolific_study_url: string;
}

export interface PilotStudyCreate {
  description: string;
  estimated_completion_time: number;
  reward: number;
  pilot_hours: number;
  device_compatibility: string[];
}

export interface RecommendationResponse {
  avg_time_per_question_seconds: number;
  remaining_rating_actions: number;
  total_hours_remaining: number;
  recommended_places: number;
  is_complete: boolean;
}
