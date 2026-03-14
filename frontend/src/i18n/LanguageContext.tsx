import { createContext, useContext, useState, type ReactNode } from 'react'
import translations, { type Lang, type TranslationKey } from './translations'

interface LangContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string
}

const LangContext = createContext<LangContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    const saved = localStorage.getItem('preuser_lang')
    return (saved === 'en' || saved === 'zh') ? saved : 'zh'
  })

  const handleSetLang = (l: Lang) => {
    setLang(l)
    localStorage.setItem('preuser_lang', l)
  }

  const t = (key: TranslationKey, vars?: Record<string, string | number>): string => {
    let str: string = translations[lang][key] as string
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        str = str.replace(`{${k}}`, String(v))
      })
    }
    return str
  }

  return (
    <LangContext.Provider value={{ lang, setLang: handleSetLang, t }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  const ctx = useContext(LangContext)
  if (!ctx) throw new Error('useLang must be used inside LanguageProvider')
  return ctx
}
