import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import Analytics from './Analytics';
import type { Experiment, ExperimentStats, Upload } from '../types';

interface ExperimentDetailProps {
  experiment: Experiment;
  onBack: () => void;
  onDeleted: () => void;
  onRefresh: () => void;
}

interface AssistanceMethods {
  searchResults: boolean;
  selectedEvidence: boolean;
  aiConfidence: boolean;
  aiChatAssistant: boolean;
}

function ExperimentDetail({ experiment, onBack, onDeleted, onRefresh }: ExperimentDetailProps) {
  const [stats, setStats] = useState<ExperimentStats | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [includePreview, setIncludePreview] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  // TODO: When the methods team provides assistance methods for experimentation, we should add them here.
  // TODO: Load these from experiment settings in the backend
  // TODO: Save changes to backend when toggled
  const [assistanceMethods, setAssistanceMethods] = useState<AssistanceMethods>({
    searchResults: false,
    selectedEvidence: false,
    aiConfidence: false,
    aiChatAssistant: false,
  });

  const handleAssistanceToggle = (method: keyof AssistanceMethods) => {
    // TODO: Implement API call to save assistance method settings
    // TODO: Disable toggles if experiment has ratings (to prevent mid-experiment changes)
    setAssistanceMethods(prev => ({
      ...prev,
      [method]: !prev[method],
    }));
    setSuccess('Assistance method updated (not yet saved to backend)');
    setTimeout(() => setSuccess(null), 2000);
  };

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getExperimentStats(experiment.id, { includePreview });
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [experiment.id, includePreview]);

  const loadUploads = useCallback(async () => {
    try {
      const data = await api.listUploads(experiment.id);
      setUploads(data);
    } catch {
      // Ignore errors for uploads list
    }
  }, [experiment.id]);

  useEffect(() => {
    loadStats();
    loadUploads();
  }, [loadStats, loadUploads]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    if (experiment.rating_count > 0) {
      if (!window.confirm(
        `This experiment already has ${experiment.rating_count} ratings. ` +
        `Uploading will ADD more questions (not replace existing ones). Continue?`
      )) {
        return;
      }
    }

    setError(null);
    setSuccess(null);

    try {
      const result = await api.uploadQuestions(experiment.id, uploadFile);
      setSuccess(result.message);
      setUploadFile(null);
      (e.target as HTMLFormElement).reset();
      await loadStats();
      await loadUploads();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleDelete = async () => {
    const prolificWarning = experiment.prolific_study_id
      ? ' The linked Prolific study will also be deleted.'
      : '';
    if (window.confirm(`Delete "${experiment.name}"? This cannot be undone.${prolificWarning}`)) {
      try {
        await api.deleteExperiment(experiment.id);
        onDeleted();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    }
  };

  const handlePublishProlific = async () => {
    if (!window.confirm('Publish this study on Prolific? Participants will be able to start immediately.')) {
      return;
    }
    setError(null);
    setIsPublishing(true);
    try {
      await api.publishProlificStudy(experiment.id);
      setSuccess('Study published on Prolific!');
      setTimeout(() => setSuccess(null), 3000);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish study');
    } finally {
      setIsPublishing(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Copied to clipboard!');
    setTimeout(() => setSuccess(null), 2000);
  };

  if (showAnalytics) {
    return (
      <Analytics
        experimentId={experiment.id}
        experimentName={experiment.name}
        onBack={() => setShowAnalytics(false)}
      />
    );
  }

  const styles = {
    container: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '24px',
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      marginBottom: '24px',
      paddingBottom: '16px',
      borderBottom: '1px solid #e0e0e0',
    },
    backButton: {
      background: 'none',
      border: '1px solid #ddd',
      padding: '8px 16px',
      borderRadius: '6px',
      cursor: 'pointer',
      color: '#666',
    },
    title: {
      margin: 0,
      fontSize: '24px',
      fontWeight: 600,
    },
    grid: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '24px',
    },
    column: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '20px',
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
    statsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '16px',
    },
    statItem: {
      textAlign: 'center' as const,
      padding: '16px',
      background: '#f8f9fa',
      borderRadius: '6px',
    },
    statValue: {
      fontSize: '28px',
      fontWeight: 700,
      color: '#333',
    },
    statLabel: {
      fontSize: '12px',
      color: '#666',
      marginTop: '4px',
    },
    buttonGroup: {
      display: 'flex',
      gap: '10px',
      marginTop: '16px',
    },
    primaryButton: {
      flex: 1,
      padding: '12px 16px',
      background: '#4a90d9',
      color: '#fff',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: 500,
    },
    secondaryButton: {
      flex: 1,
      padding: '12px 16px',
      background: '#fff',
      color: '#333',
      border: '1px solid #ddd',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: 500,
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
      fontFamily: 'monospace',
      background: '#f8f9fa',
      cursor: 'pointer',
      boxSizing: 'border-box' as const,
    },
    hint: {
      fontSize: '12px',
      color: '#888',
      marginTop: '6px',
    },
    uploadList: {
      marginBottom: '16px',
    },
    uploadItem: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 12px',
      background: '#f8f9fa',
      borderRadius: '4px',
      marginBottom: '8px',
      fontSize: '13px',
    },
    warning: {
      background: '#fff3cd',
      border: '1px solid #ffc107',
      borderRadius: '6px',
      padding: '12px',
      marginBottom: '16px',
      fontSize: '13px',
    },
    dangerSection: {
      borderColor: '#f5c6cb',
    },
    dangerHeader: {
      background: '#fff5f5',
    },
    dangerButton: {
      background: '#dc3545',
      color: '#fff',
      border: 'none',
      padding: '10px 20px',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
    },
    toggleRow: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      padding: '16px 0',
      borderBottom: '1px solid #eee',
    },
    toggleInfo: {
      flex: 1,
      paddingRight: '16px',
    },
    toggleLabel: {
      fontSize: '14px',
      fontWeight: 500,
      color: '#333',
      marginBottom: '4px',
    },
    toggleDescription: {
      fontSize: '12px',
      color: '#888',
      lineHeight: 1.4,
    },
    toggle: {
      position: 'relative' as const,
      width: '44px',
      height: '24px',
      flexShrink: 0,
    },
    toggleTrack: {
      width: '44px',
      height: '24px',
      borderRadius: '12px',
      cursor: 'pointer',
      transition: 'background 0.2s',
    },
    toggleThumb: {
      position: 'absolute' as const,
      top: '2px',
      width: '20px',
      height: '20px',
      borderRadius: '50%',
      background: '#fff',
      boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      transition: 'left 0.2s',
    },
    comingSoon: {
      fontSize: '10px',
      color: '#888',
      background: '#f0f0f0',
      padding: '2px 6px',
      borderRadius: '4px',
      marginLeft: '8px',
    },
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <button onClick={onBack} style={styles.backButton}>← Back</button>
        <h1 style={styles.title}>{experiment.name}</h1>
      </div>

      {error && <div className="error" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div className="success" style={{ marginBottom: '16px' }}>{success}</div>}

      {/* Two Column Grid */}
      <div style={styles.grid}>
        {/* Left Column */}
        <div style={styles.column}>
          {/* Overview Stats */}
          <div style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Overview</h2>
            </div>
            <div style={styles.sectionBody}>
              {stats && (
                <>
                  <div style={styles.statsGrid}>
                    <div style={styles.statItem}>
                      <div style={styles.statValue}>{stats.total_questions}</div>
                      <div style={styles.statLabel}>Questions</div>
                    </div>
                    <div style={styles.statItem}>
                      <div style={styles.statValue}>{stats.questions_complete}</div>
                      <div style={styles.statLabel}>Complete</div>
                    </div>
                    <div style={styles.statItem}>
                      <div style={styles.statValue}>{stats.total_ratings}</div>
                      <div style={styles.statLabel}>Ratings</div>
                    </div>
                    <div style={styles.statItem}>
                      <div style={styles.statValue}>{stats.total_raters}</div>
                      <div style={styles.statLabel}>Raters</div>
                    </div>
                  </div>
                  <div style={{ ...styles.toggleRow, borderBottom: 'none', paddingBottom: '8px' }}>
                    <div style={styles.toggleInfo}>
                      <div style={styles.toggleLabel}>Include preview data</div>
                      <div style={styles.toggleDescription}>
                        Show data from preview sessions in stats, analytics, and exports.
                      </div>
                    </div>
                    <div style={styles.toggle}>
                      <div
                        style={{
                          ...styles.toggleTrack,
                          background: includePreview ? '#4a90d9' : '#ddd',
                        }}
                        onClick={() => setIncludePreview(!includePreview)}
                      />
                      <div
                        style={{
                          ...styles.toggleThumb,
                          left: includePreview ? '22px' : '2px',
                        }}
                      />
                    </div>
                  </div>
                  <div style={styles.buttonGroup}>
                    <button style={styles.primaryButton} onClick={() => setShowAnalytics(true)}>
                      View Analytics
                    </button>
                    <a href={api.getExportUrl(experiment.id, { includePreview })} download style={{ flex: 1 }}>
                      <button style={{ ...styles.secondaryButton, width: '100%' }}>
                        Export CSV
                      </button>
                    </a>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Prolific Integration */}
          <div style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Prolific Integration</h2>
            </div>
            <div style={styles.sectionBody}>
              {experiment.prolific_study_id ? (
                <>
                  <div style={styles.inputGroup}>
                    <label style={styles.label}>Prolific Study ID</label>
                    <input
                      type="text"
                      value={experiment.prolific_study_id}
                      readOnly
                      onClick={(e) => {
                        (e.target as HTMLInputElement).select();
                        copyToClipboard(experiment.prolific_study_id!);
                      }}
                      style={styles.input}
                    />
                  </div>
                  <div style={styles.inputGroup}>
                    <label style={styles.label}>Study Status</label>
                    <div>
                      <span style={{
                        display: 'inline-block',
                        padding: '4px 10px',
                        borderRadius: '4px',
                        fontSize: '13px',
                        fontWeight: 500,
                        background: experiment.prolific_study_status === 'ACTIVE' ? '#d4edda' : '#fff3cd',
                        color: experiment.prolific_study_status === 'ACTIVE' ? '#155724' : '#856404',
                      }}>
                        {experiment.prolific_study_status}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginTop: '8px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => {
                        window.open(experiment.prolific_study_url!, '_blank');
                      }}
                      style={styles.secondaryButton}
                    >
                      Open on Prolific
                    </button>
                    <button
                      onClick={() => {
                        const previewId = `preview_${Date.now()}`;
                        const url = `${window.location.origin}/rate?experiment_id=${experiment.id}&PROLIFIC_PID=${previewId}&STUDY_ID=preview&SESSION_ID=preview&preview=true`;
                        window.open(url, '_blank');
                      }}
                      style={styles.secondaryButton}
                    >
                      Preview as Participant
                    </button>
                    <button
                      onClick={handlePublishProlific}
                      disabled={isPublishing}
                      style={{
                        ...styles.primaryButton,
                        ...(isPublishing ? { opacity: 0.6, cursor: 'not-allowed' } : {}),
                      }}
                    >
                      {isPublishing ? 'Publishing...' : 'Publish on Prolific'}
                    </button>
                  </div>
                  {experiment.prolific_completion_url && (
                    <div style={{ ...styles.inputGroup, marginTop: '16px' }}>
                      <label style={styles.label}>Completion URL</label>
                      <input
                        type="text"
                        value={experiment.prolific_completion_url}
                        readOnly
                        style={styles.input}
                      />
                      <div style={styles.hint}>Raters redirect here when finished.</div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: '#6c757d', fontStyle: 'italic' }}>
                  No Prolific study linked to this experiment.
                </div>
              )}
            </div>
          </div>

          {/* Danger Zone */}
          <div style={{ ...styles.section, ...styles.dangerSection }}>
            <div style={{ ...styles.sectionHeader, ...styles.dangerHeader }}>
              <h2 style={{ ...styles.sectionTitle, color: '#dc3545' }}>Danger Zone</h2>
            </div>
            <div style={styles.sectionBody}>
              <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
                Permanently delete this experiment and all associated data.
              </p>
              <button onClick={handleDelete} style={styles.dangerButton}>
                Delete Experiment
              </button>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div style={styles.column}>
          {/* Questions */}
          <div style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Questions</h2>
            </div>
            <div style={styles.sectionBody}>
              {/* Uploaded files list */}
              {uploads.length > 0 && (
                <div style={styles.uploadList}>
                  {uploads.map((upload) => (
                    <div key={upload.id} style={styles.uploadItem}>
                      <span style={{ fontFamily: 'monospace' }}>{upload.filename}</span>
                      <span style={{ color: '#666' }}>
                        {upload.question_count} questions
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Warning if ratings exist */}
              {experiment.rating_count > 0 && (
                <div style={styles.warning}>
                  <strong>Note:</strong> Uploading adds questions, doesn't replace existing ones.
                </div>
              )}

              {/* Upload form */}
              <form onSubmit={handleUpload}>
                <div style={styles.inputGroup}>
                  <label style={styles.label}>Add Questions from CSV</label>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    style={{ fontSize: '14px' }}
                  />
                  <div style={styles.hint}>
                    Required: question_id, question_text. Optional: gt_answer, options, question_type, metadata
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={!uploadFile}
                  style={{
                    ...styles.primaryButton,
                    opacity: uploadFile ? 1 : 0.5,
                    cursor: uploadFile ? 'pointer' : 'not-allowed',
                  }}
                >
                  Upload CSV
                </button>
              </form>
            </div>
          </div>

          {/* Rater Assistance Methods */}
          <div style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Rater Assistance Methods</h2>
            </div>
            <div style={styles.sectionBody}>
              {/* Search Results Toggle */}
              <div style={styles.toggleRow}>
                <div style={styles.toggleInfo}>
                  <div style={styles.toggleLabel}>
                    Search Results
                    <span style={styles.comingSoon}>Coming Soon</span>
                  </div>
                  <div style={styles.toggleDescription}>
                    Display relevant search results from web sources to help raters verify factual claims.
                  </div>
                </div>
                <div style={styles.toggle}>
                  <div
                    style={{
                      ...styles.toggleTrack,
                      background: assistanceMethods.searchResults ? '#4a90d9' : '#ddd',
                    }}
                    onClick={() => handleAssistanceToggle('searchResults')}
                  />
                  <div
                    style={{
                      ...styles.toggleThumb,
                      left: assistanceMethods.searchResults ? '22px' : '2px',
                    }}
                  />
                </div>
              </div>

              {/* Selected Evidence Toggle */}
              <div style={styles.toggleRow}>
                <div style={styles.toggleInfo}>
                  <div style={styles.toggleLabel}>
                    Selected Evidence
                    <span style={styles.comingSoon}>Coming Soon</span>
                  </div>
                  <div style={styles.toggleDescription}>
                    Show pre-selected evidence passages that are relevant to the question being rated.
                  </div>
                </div>
                <div style={styles.toggle}>
                  <div
                    style={{
                      ...styles.toggleTrack,
                      background: assistanceMethods.selectedEvidence ? '#4a90d9' : '#ddd',
                    }}
                    onClick={() => handleAssistanceToggle('selectedEvidence')}
                  />
                  <div
                    style={{
                      ...styles.toggleThumb,
                      left: assistanceMethods.selectedEvidence ? '22px' : '2px',
                    }}
                  />
                </div>
              </div>

              {/* AI Confidence Toggle */}
              <div style={styles.toggleRow}>
                <div style={styles.toggleInfo}>
                  <div style={styles.toggleLabel}>
                    AI Confidence Score
                    <span style={styles.comingSoon}>Coming Soon</span>
                  </div>
                  <div style={styles.toggleDescription}>
                    Display the AI model's confidence level for its response to provide additional context.
                  </div>
                </div>
                <div style={styles.toggle}>
                  <div
                    style={{
                      ...styles.toggleTrack,
                      background: assistanceMethods.aiConfidence ? '#4a90d9' : '#ddd',
                    }}
                    onClick={() => handleAssistanceToggle('aiConfidence')}
                  />
                  <div
                    style={{
                      ...styles.toggleThumb,
                      left: assistanceMethods.aiConfidence ? '22px' : '2px',
                    }}
                  />
                </div>
              </div>

              {/* AI Chat Assistant Toggle */}
              <div style={{ ...styles.toggleRow, borderBottom: 'none' }}>
                <div style={styles.toggleInfo}>
                  <div style={styles.toggleLabel}>
                    AI Chat Assistant
                    <span style={styles.comingSoon}>Coming Soon</span>
                  </div>
                  <div style={styles.toggleDescription}>
                    Allow raters to ask questions to an AI assistant for help understanding or researching topics.
                  </div>
                </div>
                <div style={styles.toggle}>
                  <div
                    style={{
                      ...styles.toggleTrack,
                      background: assistanceMethods.aiChatAssistant ? '#4a90d9' : '#ddd',
                    }}
                    onClick={() => handleAssistanceToggle('aiChatAssistant')}
                  />
                  <div
                    style={{
                      ...styles.toggleThumb,
                      left: assistanceMethods.aiChatAssistant ? '22px' : '2px',
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExperimentDetail;
