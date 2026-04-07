import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type {
  ExperimentDocument,
  ExperimentDocumentPage,
  ExperimentDocumentSearchResponse,
  Question,
} from '../types';

interface DocumentSearchPanelProps {
  question: Question;
  sessionToken: string;
}

type SearchMode = 'lexical' | 'semantic' | 'hybrid';

function highlightQuery(text: string, query: string): string {
  const trimmed = query.trim();
  if (!trimmed) return text;
  const pattern = new RegExp(`(${trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
  return text.replace(pattern, '<mark>$1</mark>');
}

export default function DocumentSearchPanel({
  question,
  sessionToken,
}: DocumentSearchPanelProps) {
  const [documents, setDocuments] = useState<ExperimentDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageData, setPageData] = useState<ExperimentDocumentPage | null>(null);
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
  const [searchResults, setSearchResults] = useState<ExperimentDocumentSearchResponse | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingDocs(true);
    setError(null);
    setSearchResults(null);
    setPageData(null);
    setSelectedDocumentId(null);

    api
      .listRaterDocuments(sessionToken, question.id)
      .then((data) => {
        if (cancelled) return;
        setDocuments(data);
        setSelectedDocumentId(data[0]?.id ?? null);
        setPage(1);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load context documents');
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingDocs(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [question.id, sessionToken]);

  useEffect(() => {
    if (!selectedDocumentId) {
      setPageData(null);
      return;
    }

    let cancelled = false;
    setLoadingPage(true);
    api
      .getRaterDocumentPage(sessionToken, question.id, selectedDocumentId, page, 8)
      .then((data) => {
        if (!cancelled) {
          setPageData(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load document page');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPage(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [page, question.id, selectedDocumentId, sessionToken]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  );

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }

    setSearching(true);
    setError(null);
    try {
      const results = await api.searchRaterDocuments(
        sessionToken,
        question.id,
        selectedDocumentId,
        query.trim(),
        searchMode,
        8
      );
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const jumpToResult = (documentId: number, chunkIndex: number) => {
    setSelectedDocumentId(documentId);
    setPage(Math.floor(chunkIndex / 8) + 1);
  };

  if (loadingDocs) {
    return <div style={{ color: '#666', fontSize: '14px' }}>Loading context documents...</div>;
  }

  if (!documents.length) {
    return null;
  }

  const styles = {
    wrapper: {
      marginTop: '24px',
      borderTop: '1px solid #e0e0e0',
      paddingTop: '20px',
    },
    panel: {
      border: '1px solid #e0e0e0',
      borderRadius: '10px',
      background: '#fafafa',
      padding: '16px',
    },
    title: {
      margin: '0 0 12px 0',
      fontSize: '16px',
      fontWeight: 600,
      color: '#333',
    },
    row: {
      display: 'flex',
      gap: '10px',
      alignItems: 'center',
      marginBottom: '12px',
      flexWrap: 'wrap' as const,
    },
    select: {
      padding: '8px 10px',
      border: '1px solid #d6d6d6',
      borderRadius: '6px',
      fontSize: '14px',
      background: '#fff',
    },
    input: {
      flex: 1,
      minWidth: '200px',
      padding: '8px 10px',
      border: '1px solid #d6d6d6',
      borderRadius: '6px',
      fontSize: '14px',
      background: '#fff',
    },
    button: {
      padding: '8px 12px',
      border: 'none',
      borderRadius: '6px',
      background: '#4a90d9',
      color: '#fff',
      cursor: 'pointer',
      fontSize: '14px',
    },
    resultList: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '10px',
      marginBottom: '14px',
    },
    resultItem: {
      background: '#fff',
      border: '1px solid #e4e4e4',
      borderRadius: '8px',
      padding: '12px',
      cursor: 'pointer',
    },
    resultTitle: {
      fontSize: '13px',
      color: '#4a90d9',
      marginBottom: '6px',
      fontWeight: 600,
    },
    viewer: {
      background: '#fff',
      border: '1px solid #e4e4e4',
      borderRadius: '8px',
      maxHeight: '420px',
      overflowY: 'auto' as const,
      padding: '12px',
    },
    chunk: {
      borderBottom: '1px solid #f0f0f0',
      paddingBottom: '12px',
      marginBottom: '12px',
      fontSize: '14px',
      lineHeight: 1.6,
      whiteSpace: 'pre-wrap' as const,
      color: '#333',
    },
    meta: {
      fontSize: '12px',
      color: '#888',
      marginBottom: '8px',
      fontFamily: 'monospace',
    },
    pager: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginTop: '12px',
      fontSize: '13px',
      color: '#666',
    },
    pagerButton: {
      padding: '6px 10px',
      border: '1px solid #d6d6d6',
      borderRadius: '6px',
      background: '#fff',
      cursor: 'pointer',
    },
    helper: {
      fontSize: '12px',
      color: '#666',
      marginBottom: '12px',
    },
    error: {
      color: '#dc3545',
      fontSize: '13px',
      marginBottom: '10px',
    },
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.panel}>
        <h3 style={styles.title}>Document Context</h3>
        <p style={styles.helper}>
          Browse the uploaded source documents, or search them with exact match, semantic search,
          or a hybrid of both.
        </p>
        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={handleSearch} style={styles.row}>
          <select
            value={selectedDocumentId ?? ''}
            onChange={(e) => {
              setSelectedDocumentId(Number(e.target.value));
              setPage(1);
            }}
            style={styles.select}
          >
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                {document.title}
              </option>
            ))}
          </select>
          <select
            value={searchMode}
            onChange={(e) => setSearchMode(e.target.value as SearchMode)}
            style={styles.select}
          >
            <option value="hybrid">Hybrid</option>
            <option value="lexical">Exact</option>
            <option value="semantic">Semantic</option>
          </select>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the document corpus..."
            style={styles.input}
          />
          <button type="submit" style={styles.button} disabled={searching}>
            {searching ? 'Searching...' : 'Search'}
          </button>
        </form>

        {searchResults && searchResults.results.length > 0 && (
          <div style={styles.resultList}>
            {searchResults.results.map((result) => (
              <div
                key={result.chunk_id}
                style={styles.resultItem}
                onClick={() => jumpToResult(result.document_id, result.chunk_index)}
              >
                <div style={styles.resultTitle}>
                  {result.document_title} · chunk {result.chunk_index + 1} · score {result.score}
                </div>
                <div
                  dangerouslySetInnerHTML={{
                    __html: highlightQuery(result.text, searchResults.query),
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {selectedDocument && (
          <>
            <div style={styles.helper}>
              Viewing {selectedDocument.title} · {selectedDocument.chunk_count} chunks
            </div>
            <div style={styles.viewer}>
              {loadingPage && <div style={{ color: '#666' }}>Loading page...</div>}
              {!loadingPage &&
                pageData?.chunks.map((chunk) => (
                  <div key={chunk.id} style={styles.chunk}>
                    <div style={styles.meta}>
                      chunk {chunk.chunk_index + 1} · chars {chunk.char_start}-{chunk.char_end}
                    </div>
                    <div
                      dangerouslySetInnerHTML={{
                        __html: highlightQuery(chunk.text, searchResults?.query || query),
                      }}
                    />
                  </div>
                ))}
            </div>
            {pageData && (
              <div style={styles.pager}>
                <button
                  type="button"
                  style={styles.pagerButton}
                  disabled={pageData.page <= 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  Previous
                </button>
                <span>
                  Page {pageData.page} of {pageData.total_pages}
                </span>
                <button
                  type="button"
                  style={styles.pagerButton}
                  disabled={pageData.page >= pageData.total_pages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
