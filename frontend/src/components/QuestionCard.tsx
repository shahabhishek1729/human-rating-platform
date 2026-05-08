import { useState, useEffect, useRef } from 'react';
import type { Question } from '../types';

interface QuestionCardProps {
  question: Question;
  onSubmit: (answer: string, confidence: number, timeStarted: string) => Promise<void>;
  disabled?: boolean;
  assistanceAnswer?: string | null;
  assistanceActive?: boolean;
}

function QuestionCard({ question, onSubmit, disabled = false, assistanceAnswer = null, assistanceActive = false }: QuestionCardProps) {
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [freeTextAnswer, setFreeTextAnswer] = useState('');
  const [confidence, setConfidence] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const timeStartedRef = useRef(new Date().toISOString());

  useEffect(() => {
    setSelectedAnswer('');
    setFreeTextAnswer('');
    setConfidence(3);
    setSubmitting(false);
    timeStartedRef.current = new Date().toISOString();
  }, [question.id]);

  // Prefill with AI's suggested answer when assistance completes
  useEffect(() => {
    if (!assistanceAnswer) return;
    if (question.question_type === 'FT') {
      setFreeTextAnswer(assistanceAnswer);
    } else {
      setSelectedAnswer(assistanceAnswer);
    }
  }, [assistanceAnswer]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = async () => {
    const answer = question.question_type === 'FT' ? freeTextAnswer : selectedAnswer;

    if (!answer.trim()) {
      alert('Please provide an answer');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(answer, confidence, timeStartedRef.current);
    } finally {
      setSubmitting(false);
    }
  };

  // Options may use '|' as delimiter (new format, supports options containing commas)
  // or ',' (legacy format). Detect by presence of '|'.
  const options = question.options
    ? question.options.split(question.options.includes('|') ? '|' : ',').map(o => o.trim()).filter(o => o)
    : [];

  const isMC = question.question_type === 'MC' && options.length > 0;
  const canSubmit = !disabled && (isMC ? !!selectedAnswer : !!freeTextAnswer.trim());

  const styles = {
    card: {
      background: '#fff',
      borderRadius: '12px',
      border: '1px solid #e0e0e0',
      padding: '32px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    },
    questionId: {
      fontSize: '12px',
      fontWeight: 500,
      color: '#888',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      marginBottom: '12px',
    },
    parentBox: {
      background: '#f0f4f8',
      border: '1px solid #d6e0ea',
      borderRadius: '8px',
      padding: '16px 20px',
      marginBottom: '20px',
    },
    parentLabel: {
      fontSize: '11px',
      fontWeight: 600,
      color: '#5a7896',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      marginBottom: '6px',
    },
    parentText: {
      fontSize: '15px',
      lineHeight: 1.5,
      color: '#3a4a5c',
      whiteSpace: 'pre-wrap' as const,
      margin: 0,
    },
    questionText: {
      fontSize: '20px',
      lineHeight: 1.5,
      color: '#333',
      marginBottom: '28px',
      whiteSpace: 'pre-wrap' as const,
    },
    optionsGrid: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '10px',
      marginBottom: '24px',
    },
    option: {
      padding: '16px 20px',
      background: '#f8f9fa',
      border: '2px solid transparent',
      borderRadius: '8px',
      cursor: 'pointer',
      fontSize: '15px',
      textAlign: 'left' as const,
      transition: 'all 0.15s',
      color: '#333',
    },
    optionSelected: {
      background: '#e3f2fd',
      borderColor: '#4a90d9',
      color: '#333',
    },
    textarea: {
      width: '100%',
      padding: '16px',
      border: '1px solid #ddd',
      borderRadius: '8px',
      fontSize: '15px',
      lineHeight: 1.5,
      resize: 'vertical' as const,
      marginBottom: '24px',
      boxSizing: 'border-box' as const,
    },
    confidenceSection: {
      marginBottom: '24px',
      padding: '20px',
      background: '#f8f9fa',
      borderRadius: '8px',
    },
    confidenceLabel: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: '12px',
    },
    confidenceTitle: {
      fontSize: '14px',
      fontWeight: 500,
      color: '#333',
    },
    confidenceValue: {
      fontSize: '18px',
      fontWeight: 600,
      color: '#4a90d9',
    },
    slider: {
      width: '100%',
      height: '8px',
      borderRadius: '4px',
      appearance: 'none' as const,
      background: '#ddd',
      outline: 'none',
      cursor: 'pointer',
    },
    sliderLabels: {
      display: 'flex',
      justifyContent: 'space-between',
      marginTop: '8px',
      fontSize: '12px',
      color: '#888',
    },
    submitButton: {
      width: '100%',
      padding: '16px',
      background: canSubmit ? '#4a90d9' : '#ccc',
      color: '#fff',
      border: 'none',
      borderRadius: '8px',
      fontSize: '16px',
      fontWeight: 500,
      cursor: canSubmit ? 'pointer' : 'not-allowed',
      transition: 'background 0.15s',
    },
  };

  return (
    <div style={styles.card}>
      <div style={styles.questionId}>Question {question.question_id}</div>

      {question.parent_question_text && (
        <div style={styles.parentBox}>
          <div style={styles.parentLabel}>Context</div>
          <p style={styles.parentText}>{question.parent_question_text}</p>
        </div>
      )}

      <p style={styles.questionText}>{question.question_text}</p>

      {assistanceActive && assistanceAnswer == null && (
        <p style={{ fontSize: '14px', color: '#888', fontStyle: 'italic', marginBottom: '16px' }}>
          Answer the questions on the right to help inform your response.
        </p>
      )}

      {!assistanceActive && (isMC ? (
        <div style={styles.optionsGrid}>
          {options.map((option, index) => (
            <button
              key={index}
              style={{
                ...styles.option,
                ...(selectedAnswer === option ? styles.optionSelected : {}),
              }}
              onClick={() => setSelectedAnswer(option)}
              onMouseEnter={(e) => {
                if (selectedAnswer !== option) {
                  e.currentTarget.style.background = '#f0f0f0';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedAnswer !== option) {
                  e.currentTarget.style.background = '#f8f9fa';
                }
              }}
            >
              {option}
            </button>
          ))}
        </div>
      ) : (
        <textarea
          value={freeTextAnswer}
          onChange={(e) => setFreeTextAnswer(e.target.value)}
          placeholder="Type your answer here..."
          rows={4}
          style={styles.textarea}
        />
      ))}

      {!assistanceActive && (
        <div style={styles.confidenceSection}>
          <div style={styles.confidenceLabel}>
            <span style={styles.confidenceTitle}>How confident are you?</span>
            <span style={styles.confidenceValue}>{confidence}/5</span>
          </div>
          <input
            type="range"
            min="1"
            max="5"
            value={confidence}
            onChange={(e) => setConfidence(parseInt(e.target.value))}
            style={styles.slider}
          />
          <div style={styles.sliderLabels}>
            <span>Not confident</span>
            <span>Very confident</span>
          </div>
        </div>
      )}

      {(!assistanceActive) && (
        <button
          onClick={handleSubmit}
          disabled={submitting || !canSubmit}
          style={styles.submitButton}
        >
          {submitting ? 'Submitting...' : 'Submit Answer'}
        </button>
      )}
    </div>
  );
}

export default QuestionCard;
