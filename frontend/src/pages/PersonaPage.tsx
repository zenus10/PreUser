import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useProjectStore } from '../store/useProjectStore'
import { useLang } from '../i18n/LanguageContext'
import * as api from '../api/client'
import type { Persona, PersonaDimensions } from '../api/types'

function DimensionBar({
  label,
  value,
  editable,
  onChange,
}: {
  label: string
  value: number
  editable?: boolean
  onChange?: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-28 shrink-0">{label}</span>
      {editable ? (
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => onChange?.(parseInt(e.target.value))}
          className="flex-1 h-2 accent-indigo-500"
        />
      ) : (
        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-indigo-400 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${value}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        </div>
      )}
      <span className="text-xs text-gray-400 w-8 text-right">{value}</span>
    </div>
  )
}

function PersonaCard({
  persona,
  selected,
  onClick,
  typeLabel,
  typeBg,
  ageUnit,
}: {
  persona: Persona
  selected: boolean
  onClick: () => void
  typeLabel: string
  typeBg: string
  ageUnit: string
}) {
  return (
    <motion.div
      layout
      whileHover={{ scale: 1.02 }}
      onClick={onClick}
      className={`
        p-4 rounded-xl border cursor-pointer transition-all duration-200
        ${selected
          ? 'ring-2 ring-indigo-400 border-indigo-200 bg-white shadow-md'
          : `${typeBg} hover:shadow-sm`
        }
      `}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center text-sm font-bold text-indigo-600">
          {persona.name[0]}
        </div>
        <div className="min-w-0">
          <div className="font-medium text-sm truncate">{persona.name}</div>
          <div className="text-xs text-gray-400">{persona.age}{ageUnit} · {persona.occupation}</div>
        </div>
      </div>
      <div className={`inline-block text-xs px-2 py-0.5 rounded-full ${typeBg}`}>
        {typeLabel}
      </div>
      <p className="text-xs text-gray-500 mt-2 italic line-clamp-2">"{persona.attitude_tag}"</p>
    </motion.div>
  )
}

export default function PersonaPage() {
  const navigate = useNavigate()
  const { t } = useLang()
  const projectId = useProjectStore((s) => s.projectId)
  const personas = useProjectStore((s) => s.personas)
  const fetchAnalysis = useProjectStore((s) => s.fetchAnalysis)
  const status = useProjectStore((s) => s.status)

  const TYPE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
    core: { label: t('persona_type_core'), color: 'text-blue-700', bg: 'bg-blue-50 border-blue-200' },
    cold: { label: t('persona_type_cold'), color: 'text-gray-700', bg: 'bg-gray-50 border-gray-200' },
    resistant: { label: t('persona_type_resistant'), color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200' },
    misuser: { label: t('persona_type_misuser'), color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
  }

  const [selected, setSelected] = useState<Persona | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [editedPersonas, setEditedPersonas] = useState<Persona[]>([])
  const [customDescription, setCustomDescription] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    if (!projectId) { navigate('/', { replace: true }); return }
    if (personas.length === 0) fetchAnalysis()
  }, [projectId, navigate, personas.length, fetchAnalysis])

  useEffect(() => {
    if (personas.length > 0 && !selected) setSelected(personas[0])
  }, [personas, selected])

  useEffect(() => {
    setEditedPersonas([...personas])
  }, [personas])

  const displayPersonas = editMode ? editedPersonas : personas

  const handleDimensionChange = (personaId: string, dim: keyof PersonaDimensions, value: number) => {
    setEditedPersonas((prev) =>
      prev.map((p) =>
        p.persona_id === personaId
          ? { ...p, dimensions: { ...p.dimensions, [dim]: value } }
          : p
      )
    )
    if (selected?.persona_id === personaId) {
      setSelected((prev) =>
        prev ? { ...prev, dimensions: { ...prev.dimensions, [dim]: value } } : prev
      )
    }
  }

  const handleDeletePersona = (personaId: string) => {
    if (!confirm(t('persona_delete_confirm'))) return
    setEditedPersonas((prev) => prev.filter((p) => p.persona_id !== personaId))
    if (selected?.persona_id === personaId) {
      setSelected(editedPersonas.find((p) => p.persona_id !== personaId) || null)
    }
  }

  const handleAddCustomPersona = async () => {
    if (!projectId || !customDescription.trim()) return
    setGenerating(true)
    try {
      const newPersona = await api.generateCustomPersona(projectId, customDescription)
      setEditedPersonas((prev) => [...prev, newPersona])
      setSelected(newPersona)
      setCustomDescription('')
      setShowCustomInput(false)
    } catch (e: any) {
      alert(t('persona_gen_failed') + e.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleSaveAndSimulate = async () => {
    if (!projectId) return
    setSaving(true)
    try {
      await api.updatePersonas(projectId, editedPersonas)
      await api.triggerSimulation(projectId)
      setEditMode(false)
      navigate('/progress')
    } catch (e: any) {
      alert(t('persona_save_failed') + e.message)
    } finally {
      setSaving(false)
    }
  }

  if (personas.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        {t('persona_loading')}
      </div>
    )
  }

  const corePersonas = displayPersonas.filter((p) => p.type === 'core')
  const adversarialPersonas = displayPersonas.filter((p) => p.type !== 'core')

  return (
    <div className="flex flex-col h-full">
      {/* Top action bar */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h2 className="text-lg font-bold text-gray-900">
          {t('persona_title')} ({displayPersonas.length})
        </h2>
        <div className="flex items-center gap-2">
          {!editMode ? (
            <>
              <button
                onClick={() => setEditMode(true)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                {t('persona_edit')}
              </button>
              {status === 'completed' && (
                <button
                  onClick={() => navigate('/chat?mode=interview&persona=' + (selected?.persona_id || ''))}
                  className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  {t('persona_chat')}
                </button>
              )}
            </>
          ) : (
            <>
              <button
                onClick={() => { setEditMode(false); setEditedPersonas([...personas]) }}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                {t('persona_cancel')}
              </button>
              <button
                onClick={() => setShowCustomInput(true)}
                className="px-3 py-1.5 text-sm border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50"
              >
                {t('persona_add_custom')}
              </button>
              <button
                onClick={handleSaveAndSimulate}
                disabled={saving}
                className="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? t('persona_saving') : t('persona_save_simulate')}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Custom persona input */}
      {showCustomInput && (
        <div className="mb-4 p-4 bg-indigo-50 rounded-xl border border-indigo-100 shrink-0">
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            {t('persona_custom_label')}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={customDescription}
              onChange={(e) => setCustomDescription(e.target.value)}
              placeholder={t('persona_custom_placeholder')}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
            <button
              onClick={handleAddCustomPersona}
              disabled={generating || !customDescription.trim()}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {generating ? t('persona_generating') : t('persona_generate')}
            </button>
            <button
              onClick={() => { setShowCustomInput(false); setCustomDescription('') }}
              className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
            >
              {t('persona_cancel')}
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-6 flex-1 overflow-hidden">
        {/* Left: card list */}
        <div className="w-72 shrink-0 overflow-y-auto space-y-6">
          {corePersonas.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">{t('persona_section_core')}</h3>
              <div className="space-y-2">
                {corePersonas.map((p) => {
                  const cfg = TYPE_CONFIG[p.type] || TYPE_CONFIG.core
                  return (
                    <PersonaCard
                      key={p.persona_id}
                      persona={p}
                      selected={selected?.persona_id === p.persona_id}
                      onClick={() => setSelected(p)}
                      typeLabel={cfg.label}
                      typeBg={cfg.bg}
                      ageUnit={t('persona_age_unit')}
                    />
                  )
                })}
              </div>
            </div>
          )}
          {adversarialPersonas.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">{t('persona_section_adversarial')}</h3>
              <div className="space-y-2">
                {adversarialPersonas.map((p) => {
                  const cfg = TYPE_CONFIG[p.type] || TYPE_CONFIG.core
                  return (
                    <PersonaCard
                      key={p.persona_id}
                      persona={p}
                      selected={selected?.persona_id === p.persona_id}
                      onClick={() => setSelected(p)}
                      typeLabel={cfg.label}
                      typeBg={cfg.bg}
                      ageUnit={t('persona_age_unit')}
                    />
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right: detail panel */}
        <AnimatePresence mode="wait">
          {selected && (
            <motion.div
              key={selected.persona_id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="flex-1 bg-white rounded-2xl border border-gray-100 p-6 overflow-y-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-full bg-indigo-100 flex items-center justify-center text-xl font-bold text-indigo-600">
                    {selected.name[0]}
                  </div>
                  <div>
                    <h2 className="text-lg font-bold">{selected.name}</h2>
                    <p className="text-sm text-gray-500">
                      {selected.age}{t('persona_age_unit')} · {selected.occupation} ·{' '}
                      <span className={TYPE_CONFIG[selected.type]?.color}>{TYPE_CONFIG[selected.type]?.label}</span>
                    </p>
                  </div>
                </div>
                {editMode && (
                  <button
                    onClick={() => handleDeletePersona(selected.persona_id)}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1 border border-red-200 rounded"
                  >
                    {t('persona_delete')}
                  </button>
                )}
              </div>

              {/* Attitude tag */}
              <div className="bg-indigo-50 rounded-lg px-4 py-3 mb-6">
                <p className="text-indigo-700 font-medium text-sm italic">
                  "{selected.attitude_tag}"
                </p>
              </div>

              {/* Dimensions */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  {t('persona_dimensions_title')}
                  {editMode && <span className="text-xs text-gray-400 font-normal ml-2">{t('persona_dimensions_hint')}</span>}
                </h3>
                <div className="space-y-2">
                  <DimensionBar
                    label={t('persona_dim_tech')}
                    value={selected.dimensions.tech_sensitivity}
                    editable={editMode}
                    onChange={(v) => handleDimensionChange(selected.persona_id, 'tech_sensitivity', v)}
                  />
                  <DimensionBar
                    label={t('persona_dim_patience')}
                    value={selected.dimensions.patience_threshold}
                    editable={editMode}
                    onChange={(v) => handleDimensionChange(selected.persona_id, 'patience_threshold', v)}
                  />
                  <DimensionBar
                    label={t('persona_dim_pay')}
                    value={selected.dimensions.pay_willingness}
                    editable={editMode}
                    onChange={(v) => handleDimensionChange(selected.persona_id, 'pay_willingness', v)}
                  />
                  <DimensionBar
                    label={t('persona_dim_alt')}
                    value={selected.dimensions.alt_dependency}
                    editable={editMode}
                    onChange={(v) => handleDimensionChange(selected.persona_id, 'alt_dependency', v)}
                  />
                </div>
              </div>

              {/* Background & motivation */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-400 mb-1">{t('persona_background')}</h4>
                  <p className="text-sm text-gray-700">{selected.background}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-400 mb-1">{t('persona_motivation')}</h4>
                  <p className="text-sm text-gray-700">{selected.motivation}</p>
                </div>
              </div>

              {/* Cognitive model */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('persona_cognitive')}</h3>
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">{selected.cognitive_model}</p>
              </div>

              {/* Expected friction points */}
              {selected.expected_friction_points.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('persona_friction')}</h3>
                  <ul className="space-y-1">
                    {selected.expected_friction_points.map((fp, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="text-amber-500 mt-0.5">!</span>
                        <span>{fp}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
