import { useState, useEffect, useCallback } from "react"
import { themeList } from "@/themes/index.ts"

type PageView = "dashboard" | "agent"

const DEFAULT_AGENT = "analyst-3"

export function Compare() {
  const [activeTheme, setActiveTheme] = useState(0)
  const [pageView, setPageView] = useState<PageView>("dashboard")

  const theme = themeList[activeTheme]
  const iframeSrc =
    pageView === "dashboard"
      ? `/${theme.slug}/dashboard`
      : `/${theme.slug}/agent/${DEFAULT_AGENT}`

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key >= "1" && e.key <= "5") {
        setActiveTheme(parseInt(e.key, 10) - 1)
      }
      if (e.key === "d" || e.key === "D") setPageView("dashboard")
      if (e.key === "a" || e.key === "A") setPageView("agent")
    },
    [],
  )

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="h-screen flex flex-col bg-[#09090b]">
      {/* Tab bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[#27272a] bg-[#111113] shrink-0">
        <span className="text-[11px] text-[#71717a] font-mono mr-2">
          SynthOrg Design Exploration
        </span>

        {themeList.map((t, i) => (
          <button
            key={t.id}
            onClick={() => setActiveTheme(i)}
            className={`
              px-3 py-1.5 rounded text-xs font-medium transition-colors
              ${
                i === activeTheme
                  ? "bg-white/10 text-white"
                  : "text-[#a1a1aa] hover:text-white hover:bg-white/5"
              }
            `}
          >
            <span className="font-mono text-[10px] mr-1.5 opacity-50">
              {i + 1}
            </span>
            {t.label}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setPageView("dashboard")}
            className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
              pageView === "dashboard"
                ? "bg-white/10 text-white"
                : "text-[#71717a] hover:text-white"
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setPageView("agent")}
            className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
              pageView === "agent"
                ? "bg-white/10 text-white"
                : "text-[#71717a] hover:text-white"
            }`}
          >
            Agent Profile
          </button>
        </div>

        <span className="text-[9px] text-[#52525b] font-mono ml-3">
          1-5: themes -- D/A: pages
        </span>
      </div>

      {/* Content iframe */}
      <iframe
        key={`${theme.slug}-${pageView}`}
        src={iframeSrc}
        className="flex-1 w-full border-0"
        title={`${theme.label} - ${pageView}`}
      />
    </div>
  )
}
