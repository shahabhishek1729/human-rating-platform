import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import type { Experiment, ProlificStudyConfig } from '../types';

function AdminView() {
  const navigate = useNavigate();
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [numRatings, setNumRatings] = useState(3);

  const [prolificConfig, setProlificConfig] = useState<ProlificStudyConfig>({
    description: '',
    estimated_completion_time: 10,
    reward: 500,
    total_available_places: 50,
    device_compatibility: ['desktop'],
  });

  useEffect(() => {
    loadExperiments();
  }, []);

  const loadExperiments = async () => {
    try {
      setLoading(true);
      const data = await api.listExperiments();
      setExperiments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      const created = await api.createExperiment({
        name,
        num_ratings_per_question: numRatings,
        prolific: prolificConfig,
      });
      setName('');
      setNumRatings(3);
      setProlificConfig({
        description: '',
        estimated_completion_time: 10,
        reward: 500,
        total_available_places: 50,
        device_compatibility: ['desktop'],
      });
      navigate(`/admin/experiments/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleSelectExperiment = (exp: Experiment) => {
    navigate(`/admin/experiments/${exp.id}`);
  };

  const styles = {
    container: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '24px',
    },
    header: {
      marginBottom: '32px',
    },
    title: {
      margin: 0,
      fontSize: '28px',
      fontWeight: 600,
      color: '#333',
    },
    subtitle: {
      margin: '8px 0 0 0',
      fontSize: '14px',
      color: '#666',
    },
    grid: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '24px',
    },
    section: {
      background: '#fff',
      borderRadius: '8px',
      border: '1px solid #e0e0e0',
      overflow: 'hidden',
    },
    sectionHeader: {
      padding: '16px 20px',
      borderBottom: '1px solid #e0e0e0',
      background: '#fafafa',
    },
    sectionTitle: {
      margin: 0,
      fontSize: '14px',
      fontWeight: 600,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px',
      color: '#555',
    },
    sectionBody: {
      padding: '20px',
    },
    inputGroup: {
      marginBottom: '16px',
    },
    label: {
      display: 'block',
      fontSize: '13px',
      fontWeight: 500,
      color: '#333',
      marginBottom: '6px',
    },
    input: {
      width: '100%',
      padding: '10px 12px',
      border: '1px solid #ddd',
      borderRadius: '6px',
      fontSize: '14px',
      boxSizing: 'border-box' as const,
    },
    hint: {
      fontSize: '12px',
      color: '#888',
      marginTop: '6px',
    },
    primaryButton: {
      width: '100%',
      padding: '12px 16px',
      background: '#4a90d9',
      color: '#fff',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: 500,
    },
    experimentList: {
      listStyle: 'none',
      margin: 0,
      padding: 0,
    },
    experimentItem: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '16px 20px',
      borderBottom: '1px solid #eee',
      cursor: 'pointer',
      transition: 'background 0.15s',
    },
    experimentName: {
      fontWeight: 500,
      color: '#333',
      marginBottom: '4px',
    },
    experimentMeta: {
      fontSize: '12px',
      color: '#888',
    },
    viewLink: {
      color: '#4a90d9',
      fontSize: '14px',
      fontWeight: 500,
    },
    emptyState: {
      padding: '40px 20px',
      textAlign: 'center' as const,
      color: '#888',
    },
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>Experiments</h1>
        <p style={styles.subtitle}>Create and manage your rating experiments</p>
      </div>

      {error && <div className="error" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div className="success" style={{ marginBottom: '16px' }}>{success}</div>}

      {/* Two Column Grid */}
      <div style={styles.grid}>
        {/* Create Experiment */}
        <div style={styles.section}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.sectionTitle}>Create New</h2>
          </div>
          <div style={styles.sectionBody}>
            <form onSubmit={handleCreateExperiment}>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Experiment Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Factuality Evaluation Round 1"
                  required
                  style={styles.input}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Ratings per Question</label>
                <input
                  type="number"
                  value={numRatings}
                  onChange={(e) => setNumRatings(parseInt(e.target.value))}
                  min="1"
                  required
                  style={styles.input}
                />
                <div style={styles.hint}>How many different raters should evaluate each question.</div>
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Study Description (for Prolific)</label>
                <textarea
                  value={prolificConfig.description}
                  onChange={(e) => setProlificConfig({ ...prolificConfig, description: e.target.value })}
                  placeholder="Describe the task for Prolific participants..."
                  required
                  style={{ ...styles.input, minHeight: '80px', resize: 'vertical' as const }}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Estimated Completion Time (minutes)</label>
                <input
                  type="number"
                  value={prolificConfig.estimated_completion_time}
                  onChange={(e) => setProlificConfig({ ...prolificConfig, estimated_completion_time: parseInt(e.target.value) || 0 })}
                  min="1"
                  required
                  style={styles.input}
                />
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Reward (cents)</label>
                <input
                  type="number"
                  value={prolificConfig.reward}
                  onChange={(e) => setProlificConfig({ ...prolificConfig, reward: parseInt(e.target.value) || 0 })}
                  min="1"
                  required
                  style={styles.input}
                />
                <div style={styles.hint}>Payment in cents (e.g., 500 = $5.00)</div>
              </div>
              <div style={styles.inputGroup}>
                <label style={styles.label}>Total Available Places</label>
                <input
                  type="number"
                  value={prolificConfig.total_available_places}
                  onChange={(e) => setProlificConfig({ ...prolificConfig, total_available_places: parseInt(e.target.value) || 0 })}
                  min="1"
                  required
                  style={styles.input}
                />
              </div>
              <button type="submit" style={styles.primaryButton}>
                Create Experiment
              </button>
            </form>
          </div>
        </div>

        {/* Experiments List */}
        <div style={styles.section}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.sectionTitle}>Your Experiments</h2>
          </div>
          {loading ? (
            <div style={styles.emptyState}>Loading...</div>
          ) : experiments.length === 0 ? (
            <div style={styles.emptyState}>
              No experiments yet.<br />Create one to get started.
            </div>
          ) : (
            <div style={styles.experimentList}>
              {experiments.map((exp) => (
                <div
                  key={exp.id}
                  style={styles.experimentItem}
                  onClick={() => handleSelectExperiment(exp)}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <div>
                    <div style={styles.experimentName}>{exp.name}</div>
                    <div style={styles.experimentMeta}>
                      {exp.question_count} questions · {exp.rating_count} ratings
                    </div>
                  </div>
                  <span style={styles.viewLink}>View →</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminView;
