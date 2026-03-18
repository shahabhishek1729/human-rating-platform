export interface Experiment {
  id: number;
  name: string;
  created_at: string;
  num_ratings_per_question: number;
  prolific_completion_url: string | null;
  prolific_study_id: string | null;
  prolific_study_status: string | null;
  prolific_study_url: string | null;
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

export interface Session {
  rater_id: number;
  session_start: string;
  session_end_time: string;
  experiment_name: string;
  completion_url: string | null;
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

export interface ExperimentCreate {
  name: string;
  num_ratings_per_question: number;
  prolific: ProlificStudyConfig;
}
