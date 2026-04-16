package ui

// LogoLines is the ANSI Shadow block-letter banner, split per line for
// per-row gradient coloring. 6 lines, ~70 chars wide -- fits in 80-col
// terminals with a 2-space indent.
var LogoLines = [6]string{
	`███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗ ██████╗ ██████╗  ██████╗ `,
	`██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║██╔═══██╗██╔══██╗██╔════╝ `,
	`███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║██║   ██║██████╔╝██║  ███╗`,
	`╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║██║   ██║██╔══██╗██║   ██║`,
	`███████║   ██║   ██║ ╚████║   ██║   ██║  ██║╚██████╔╝██║  ██║╚██████╔╝`,
	`╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ `,
}

// LogoGradientHex defines a 6-step blue-to-purple gradient that rhymes
// with the web dashboard's warm soft-blue accent (#38bdf8) while
// transitioning into the CLI's existing purple identity. True-color hex
// values degrade gracefully via lipgloss's automatic color downsampling.
var LogoGradientHex = [6]string{
	"#38bdf8", // sky-400  (web dashboard accent)
	"#60a5fa", // blue-400
	"#818cf8", // indigo-400
	"#a78bfa", // violet-400
	"#c084fc", // purple-400
	"#a855f7", // purple-500
}

// logoCompact is a single-line brand wordmark for commands that don't
// warrant the full banner (start, stop, status, etc.).
const logoCompact = "synthorg"
