import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import type { ChatMessage, Source } from '../types';
import { chat } from '../services/api';

const ExternalLinkIcon = () => (
  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
  </svg>
);

function getSourceLinkLabel(source: Source): string {
  const s = (source.source || '').toLowerCase();
  if (s === 'clinvar') return 'View on ClinVar';
  if (s === 'pharmgkb') return 'View on PharmGKB';
  if (s === 'gnomad') return 'View on gnomAD';
  return 'View on PubMed';
}

interface RAGChatData {
  gene: string;
  variant: string;
  prediction: string;
  confidence: number;
  consequence: string;
  ragResponse: string;
  sources: Source[];
}

interface ChatInterfaceProps {
  ragChatData: RAGChatData | null;
  onClearRagData?: () => void;
}

const SourceList: React.FC<{ sources: Source[]; small?: boolean }> = ({ sources, small }) => {
  const [expanded, setExpanded] = useState(false);
  if (!sources || sources.length === 0) return null;
  return (
    <div className={small ? 'ml-2 mt-1' : 'px-6 pb-4'}>
      <button
        onClick={() => setExpanded(v => !v)}
        className={`flex items-center gap-1 font-medium ${small ? 'text-xs text-blue-500 hover:text-blue-700' : 'text-sm text-blue-600 hover:text-blue-800'}`}
      >
        <svg className={`transition-transform ${expanded ? 'rotate-90' : ''} ${small ? 'h-3 w-3' : 'h-4 w-4'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {expanded ? 'Hide' : 'Show'} Sources ({sources.length})
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {sources.map((source, idx) => (
            <div key={idx} className={`bg-gray-50 rounded border border-gray-200 hover:bg-gray-100 transition-colors ${small ? 'p-2' : 'p-3'}`}>
              <div className="flex items-start gap-2">
                <span className={`px-1.5 py-0.5 bg-blue-100 text-blue-700 font-medium rounded shrink-0 ${small ? 'text-xs' : 'text-xs'}`}>
                  [{idx + 1}]
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      {source.title && (
                        <p className={`font-medium text-gray-900 leading-snug ${small ? 'text-xs' : 'text-sm'}`}>{source.title}</p>
                      )}
                      {(source.pmid || source.url) && (
                        <div className="flex items-center gap-2 mt-1">
                          {source.pmid && (
                            <span className="text-xs text-gray-500">PMID: {source.pmid}</span>
                          )}
                          {source.url && (
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                              {getSourceLinkLabel(source)}
                              <ExternalLinkIcon />
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 shrink-0">
                      {(source.score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const ChatInterface: React.FC<ChatInterfaceProps> = ({ ragChatData, onClearRagData }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [messageSources, setMessageSources] = useState<(Source[] | null)[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const overlayInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isExpanded]);

  useEffect(() => {
    if (ragChatData) {
      setMessages([{ role: 'assistant', content: ragChatData.ragResponse }]);
      setMessageSources([ragChatData.sources || null]);
      setIsExpanded(false);
    }
  }, [ragChatData]);

  // Focus overlay input when expanded
  useEffect(() => {
    if (isExpanded && overlayInputRef.current) {
      setTimeout(() => overlayInputRef.current?.focus(), 320);
    }
  }, [isExpanded]);

  // Prevent body scroll when overlay is open
  useEffect(() => {
    if (isExpanded) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isExpanded]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    setIsExpanded(true);
    const userMessage: ChatMessage = { role: 'user', content: inputValue.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const variantContext = ragChatData ? {
        gene: ragChatData.gene,
        variant: ragChatData.variant,
        prediction: ragChatData.prediction,
        confidence: ragChatData.confidence,
        consequence: ragChatData.consequence
      } : null;

      const response = await chat({
        messages: [...messages, userMessage],
        variant_context: variantContext
      });

      setMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
      setMessageSources(prev => [...prev, null, response.sources || null]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to get response');
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const getGeneSpecificQuestions = (gene: string): string[] => {
    const geneQuestions: Record<string, string[]> = {
      'SCN1A': [
        'What is Dravet syndrome?',
        'Why are sodium channel blockers contraindicated?',
        'Is stiripentol effective for SCN1A variants?',
        'What is the typical age of seizure onset?'
      ],
      'SCN2A': [
        'What seizure types are associated with SCN2A?',
        'How does age of onset affect treatment?',
        'Is phenytoin recommended for SCN2A variants?',
        'What is the difference between gain and loss of function?'
      ],
      'KCNQ2': [
        'What is benign familial neonatal seizures?',
        'Do seizures typically resolve with age?',
        'Is carbamazepine effective for KCNQ2?',
        'What is the long-term prognosis?'
      ],
      'KCNQ3': [
        'How does KCNQ3 differ from KCNQ2?',
        'What medications target potassium channels?',
        'Is developmental outcome typically normal?',
        'What monitoring is recommended?'
      ],
      'TSC1': [
        'What is tuberous sclerosis complex?',
        'Are mTOR inhibitors recommended?',
        'What non-neurological features should be monitored?',
        'Is vigabatrin effective for infantile spasms?'
      ],
      'TSC2': [
        'How does TSC2 differ from TSC1 in severity?',
        'What is the role of everolimus?',
        'What seizure types are most common?',
        'Is ketogenic diet recommended?'
      ],
      'MECP2': [
        'What is Rett syndrome?',
        'What seizure types occur in MECP2 disorders?',
        'Are there disease-modifying treatments?',
        'What is the typical developmental trajectory?'
      ],
      'CDKL5': [
        'What is CDKL5 deficiency disorder?',
        'How does it differ from Rett syndrome?',
        'What treatments are available?',
        'What is the seizure onset age?'
      ],
      'SCN8A': [
        'What is SCN8A encephalopathy?',
        'Is sodium channel blockade recommended?',
        'What is the seizure onset age?',
        'How severe is the developmental impact?'
      ],
      'GABRA1': [
        'What GABA receptor does GABRA1 encode?',
        'What seizure types are associated?',
        'Are benzodiazepines effective?',
        'What is the prognosis?'
      ],
      'GABRG2': [
        'What is GEFS+ syndrome?',
        'How do GABRG2 variants affect GABA receptors?',
        'What treatments are recommended?',
        'What is the difference between GEFS+ and Dravet?'
      ],
      'CACNA1A': [
        'What is episodic ataxia type 2?',
        'Are hemiplegic migraines associated?',
        'Is acetazolamide effective?',
        'What is the seizure phenotype?'
      ]
    };
    return geneQuestions[gene] || [
      `What is the role of ${gene} in epilepsy?`,
      `What medications are recommended for ${gene} variants?`,
      `What medications should be avoided?`,
      `What is the typical prognosis?`
    ];
  };

  const suggestedQuestions = ragChatData ? (() => {
    const allQuestions = getGeneSpecificQuestions(ragChatData.gene);
    const askedQuestions = messages.filter(m => m.role === 'user').map(m => m.content.toLowerCase().trim());
    return allQuestions.filter(q => {
      const qLower = q.toLowerCase();
      return !askedQuestions.some(asked =>
        qLower.includes(asked) || asked.includes(qLower) ||
        (asked.includes('avoid') && qLower.includes('avoid')) ||
        (asked.includes('prognosis') && qLower.includes('prognosis')) ||
        (asked.includes('recommended') && qLower.includes('recommended'))
      );
    }).slice(0, 4);
  })() : [];

  const handleSuggestedQuestion = (question: string) => {
    setInputValue(question);
    setIsExpanded(true);
  };

  const followUpCount = messages.filter(m => m.role === 'user').length;

  if (!ragChatData) return null;

  return (
    <div className="space-y-6">
      {/* Variant Summary Card */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-red-100 text-red-800 text-xs font-bold rounded">
            PATHOGENIC
          </span>
          <span className="text-lg font-semibold text-gray-900">{ragChatData.gene}</span>
        </div>
        <p className="text-sm text-gray-600 mt-1">
          {ragChatData.variant} • {ragChatData.consequence.replace(/_/g, ' ')} • {ragChatData.confidence.toFixed(1)}% confidence
        </p>
      </div>

      {/* RAG Response Card */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="p-4 bg-blue-50 border-b border-blue-100">
          <h3 className="font-medium text-blue-900 flex items-center gap-2">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Clinical Information & Treatment Recommendations
          </h3>
        </div>
        <div className="p-6">
          <div className="prose prose-sm max-w-none text-gray-700">
            <ReactMarkdown
              rehypePlugins={[rehypeRaw]}
              components={{
                h2: ({ children }) => <h2 className="text-xl font-bold text-gray-900 mt-6 mb-3 first:mt-0">{children}</h2>,
                h3: ({ children }) => <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2">{children}</h3>,
                ul: ({ children }) => <ul className="space-y-2 ml-4">{children}</ul>,
                li: ({ children }) => <li className="text-gray-700">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                p: ({ children }) => <p className="mb-3 leading-relaxed">{children}</p>,
              }}
            >
              {messages.length > 0 ? messages[0].content : ragChatData.ragResponse}
            </ReactMarkdown>
          </div>
        </div>
        <SourceList sources={ragChatData.sources} />
      </div>

      {/* Collapsed Chat Trigger Card */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="p-4 bg-gray-50 border-b flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900">Ask Follow-up Questions</h3>
            <p className="text-sm text-gray-500">
              {followUpCount > 0 ? `${followUpCount} question${followUpCount > 1 ? 's' : ''} asked` : 'Get more details about this variant and treatment options'}
            </p>
          </div>
          {followUpCount > 0 && (
            <button
              onClick={() => setIsExpanded(true)}
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              View chat
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
          )}
        </div>

        {/* Suggested Questions */}
        {suggestedQuestions.length > 0 && (
          <div className="px-4 py-3 border-b bg-gray-50">
            <p className="text-xs text-gray-500 mb-2">Suggested questions:</p>
            <div className="flex flex-wrap gap-2">
              {suggestedQuestions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedQuestion(question)}
                  className="text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-full hover:bg-blue-50 hover:border-blue-300 transition-colors"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Collapsed input — triggers overlay on focus */}
        <form onSubmit={handleSubmit} className="p-4 border-t">
          <div className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={() => setIsExpanded(true)}
              placeholder="Ask a follow-up question..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </form>
      </div>

      {/* Full-screen Chat Overlay */}
      <div
        className={`fixed inset-0 z-50 transition-all duration-300 ${isExpanded ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          onClick={() => setIsExpanded(false)}
        />

        {/* Sliding panel */}
        <div
          className={`absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl flex flex-col transition-transform duration-300 ease-out ${isExpanded ? 'translate-y-0' : 'translate-y-full'}`}
          style={{ height: '90vh' }}
        >
          {/* Overlay Header */}
          <div className="flex items-center justify-between px-5 py-4 bg-blue-600 rounded-t-2xl shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <div>
                <p className="font-semibold text-white text-sm">Clinical Assistant</p>
                <p className="text-blue-200 text-xs">{ragChatData.gene} • {ragChatData.variant}</p>
              </div>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500 hover:bg-blue-400 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              Minimize
            </button>
          </div>

          {/* Drag handle indicator */}
          <div className="flex justify-center pt-1 pb-0 shrink-0">
            <div className="w-10 h-1 bg-gray-200 rounded-full" />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.map((message, idx) => {
              const sources = messageSources[idx];
              return (
                <div key={idx}>
                  <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {message.role === 'assistant' && (
                      <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center shrink-0 mr-2 mt-1">
                        <svg className="h-3.5 w-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                      </div>
                    )}
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white rounded-br-sm'
                          : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                      }`}
                    >
                      {message.role === 'user' ? (
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      ) : (
                        <div className="text-sm prose prose-sm max-w-none">
                          <ReactMarkdown
                            rehypePlugins={[rehypeRaw]}
                            components={{
                              h2: ({ children }) => <h2 className="text-base font-bold text-gray-900 mt-3 mb-1 first:mt-0">{children}</h2>,
                              h3: ({ children }) => <h3 className="text-sm font-semibold text-gray-800 mt-2 mb-1">{children}</h3>,
                              p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                              ul: ({ children }) => <ul className="ml-3 space-y-1 my-1">{children}</ul>,
                              li: ({ children }) => <li className="text-gray-700">{children}</li>,
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>
                  </div>
                  {/* Per-message sources */}
                  {message.role === 'assistant' && sources && sources.length > 0 && (
                    <div className="ml-9 mt-1">
                      <SourceList sources={sources} small />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start items-center gap-2">
                <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
                  <svg className="h-3.5 w-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex items-center space-x-1.5">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested questions inside overlay (only when few messages) */}
          {messages.length <= 1 && suggestedQuestions.length > 0 && (
            <div className="px-4 py-2 border-t bg-gray-50 shrink-0">
              <p className="text-xs text-gray-500 mb-2">Suggested:</p>
              <div className="flex flex-wrap gap-1.5">
                {suggestedQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => setInputValue(q)}
                    className="text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-full hover:bg-blue-50 hover:border-blue-300 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="px-4 py-2 bg-red-50 border-t border-red-200 shrink-0">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Overlay Input */}
          <form onSubmit={handleSubmit} className="p-4 border-t bg-white shrink-0">
            <div className="flex gap-2 items-center">
              <input
                ref={overlayInputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={`Ask about ${ragChatData.gene} or treatment options...`}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm bg-gray-50"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !inputValue.trim()}
                className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
