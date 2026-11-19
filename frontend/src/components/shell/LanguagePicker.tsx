import { ChevronDown, Languages, ShieldCheck } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LANGUAGES, findLanguage } from '@/i18n/languages'

/**
 * A header button naming the current language, opening a menu of every language in its own
 * name (Radix: arrow keys, Home/End, typeahead, Esc back to the button; each row a
 * menuitemradio). One note says which languages are machine-translated, and the menu is where
 * the only thing kept (this choice, in this browser) is said.
 */
export function LanguagePicker() {
  const { t, i18n } = useTranslation()
  const noteId = useId()
  const current = findLanguage(i18n.resolvedLanguage ?? i18n.language)
  return (
    // Not modal: a modal menu hides the rest of the page with aria-hidden, which axe flags while
    // the header's links stay focusable. Esc or a click outside still closes it.
    <DropdownMenu dir={current.dir} modal={false}>
      <DropdownMenuTrigger
        aria-label={t('language.button', { name: current.nativeName })}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-line bg-white px-3 text-[15px] font-medium text-navy hover:border-line-strong hover:bg-[#eef1f4] data-[state=open]:border-line-strong data-[state=open]:bg-[#eef1f4]"
      >
        <Languages aria-hidden="true" className="size-[18px]" />
        <span lang={current.code}>{current.nativeName}</span>
        <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" aria-describedby={noteId} className="w-[min(20rem,90vw)]">
        <div
          id={noteId}
          className="px-3 pt-1.5 pb-2 text-[13px] leading-snug text-muted-foreground"
        >
          {t('language.note')}
        </div>
        <DropdownMenuRadioGroup
          value={current.code}
          onValueChange={(code) => void i18n.changeLanguage(code)}
        >
          {LANGUAGES.map((l) => (
            <DropdownMenuRadioItem key={l.code} value={l.code} lang={l.code} dir={l.dir}>
              {l.nativeName}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <div className="flex gap-2 px-3 pt-1 pb-1.5 text-[13px] leading-snug text-muted-foreground">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-3.5 flex-none text-green" />
          {t('shell.nothingSaved')}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
