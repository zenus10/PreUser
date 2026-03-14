import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '../store/useProjectStore'
import { useSearchParams } from 'react-router-dom'
import { useLang } from '../i18n/LanguageContext'
import * as api from '../api/client'
import type { ConversationMessage } from '../api/types'

type ChatMode = 'interview' | 'focus_group' | 'report_qa'

export default function ChatPage() {
  const { projectId, personas, analysis } = useProjectStore()
  const { t } = useLang()
  const [searchParams] = useSearchParams()

  const initialMode = (searchParams.get('mode') as ChatMode) || 'interview'
  const initialPersona = searchParams.get('persona') || ''

  const [mode, setMode] = useState<ChatMode>(initialMode)
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>(
    initialPersona ? [initialPersona] : []
  )
  const [topic, setTopic] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const analysisId = analysis?.id

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const personaMap = new Map(personas.map((p) => [p.persona_id, p]))

  const handleStartConversation = async () => {
    if (!analysisId) return
    if (mode !== 'report_qa' && selectedPersonas.length === 0) return

    try {
      setLoading(true)
      const ids = mode === 'report_qa' ? [] : selectedPersonas
      const id = await api.startConversation(analysisId, mode, ids, topic || undefined)
      setConversationId(id)
      setMessages([])
    } catch (e: any) {
      alert('Failed to start conversation: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSend = async () => {
    if (!conversationId || !input.trim() || loading) return

    const userMsg: ConversationMessage = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const responses = await api.sendMessage(conversationId, userMsg.content)
      setMessages((prev) => [...prev, ...responses])
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${e.message}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const togglePersona = (pid: string) => {
    setSelectedPersonas((prev) =>
      prev.includes(pid) ? prev.filter((p) => p !== pid) : [...prev, pid]
    )
  }

  if (!projectId || !analysisId) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        {t('chat_no_project')}
      </div>
    )
  }

  // Setup phase - choose mode and personas
  if (!conversationId) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <h2 className="text-xl font-bold text-gray-900">{t('chat_title')}</h2>

        {/* Mode selector */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">{t('chat_mode_label')}</label>
          <div className="flex gap-3">
            {([
              { value: 'interview', label: t('chat_mode_interview'), desc: t('chat_mode_interview_desc') },
              { value: 'focus_group', label: t('chat_mode_focus_group'), desc: t('chat_mode_focus_group_desc') },
              { value: 'report_qa', label: t('chat_mode_report_qa'), desc: t('chat_mode_report_qa_desc') },
            ] as const).map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`flex-1 p-3 rounded-lg border-2 text-left transition-colors ${
                  mode === m.value
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="font-medium text-sm">{m.label}</div>
                <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Persona selector (for interview and focus_group) */}
        {mode !== 'report_qa' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">
              {t('chat_select_persona')} {mode === 'interview' ? t('chat_select_one') : t('chat_select_multi')}
            </label>
            <div className="grid grid-cols-2 gap-2">
              {personas.map((p) => {
                const selected = selectedPersonas.includes(p.persona_id)
                const disabled =
                  mode === 'interview' &&
                  selectedPersonas.length >= 1 &&
                  !selected

                return (
                  <button
                    key={p.persona_id}
                    onClick={() => !disabled && togglePersona(p.persona_id)}
                    disabled={disabled}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      selected
                        ? 'border-indigo-500 bg-indigo-50'
                        : disabled
                          ? 'border-gray-100 bg-gray-50 opacity-50'
                          : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-medium text-sm">{p.name}</div>
                    <div className="text-xs text-gray-500">
                      {p.age}{t('chat_age_unit')} · {p.occupation}
                    </div>
                    <span
                      className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${
                        p.type === 'core'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-orange-100 text-orange-700'
                      }`}
                    >
                      {p.attitude_tag}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Topic input (for focus_group) */}
        {mode === 'focus_group' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">{t('chat_topic_label')}</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={t('chat_topic_placeholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        )}

        <button
          onClick={handleStartConversation}
          disabled={
            loading ||
            (mode !== 'report_qa' && selectedPersonas.length === 0) ||
            (mode === 'focus_group' && selectedPersonas.length < 2)
          }
          className="w-full py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? t('chat_starting') : t('chat_start')}
        </button>
      </div>
    )
  }

  // Chat phase
  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-gray-200 mb-3 shrink-0">
        <button
          onClick={() => {
            setConversationId(null)
            setMessages([])
          }}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          {t('chat_back')}
        </button>
        <span className="text-sm font-medium text-gray-700">
          {mode === 'interview' && t('chat_with', { name: personaMap.get(selectedPersonas[0])?.name || '?' })}
          {mode === 'focus_group' && t('chat_focus_group', { n: selectedPersonas.length })}
          {mode === 'report_qa' && t('chat_report_qa')}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pb-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {msg.role === 'assistant' && msg.persona_id && (
                <div className="text-xs font-medium text-indigo-600 mb-1">
                  {personaMap.get(msg.persona_id)?.name || msg.persona_id}
                </div>
              )}
              <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-2.5 text-gray-400 text-sm">
              {t('chat_thinking')}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 pt-3 shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={mode === 'report_qa' ? t('chat_input_report') : t('chat_input_default')}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {t('chat_send')}
          </button>
        </div>
      </div>
    </div>
  )
}
