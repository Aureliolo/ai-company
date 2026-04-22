// Package ui: data-driven registries for reusable PickOne pickers.
//
// Adding a new distributed bus backend:
//  1. Append one Option[string] struct literal to BusBackends below.
//  2. Add the matching Python backend class under
//     src/synthorg/communication/bus/.
//  3. Add the matching case arm in
//     src/synthorg/communication/bus/__init__.py::build_message_bus.
//  4. Add the enum value to
//     src/synthorg/communication/enums.py::MessageBusBackend.
//
// No changes to picker.go, init.go, or compose.yml.tmpl are required
// for a new entry to appear in the interactive picker -- the registry
// is the single source of truth.
//
// Framing rules (do not edit casually):
//  - Every option must have at least 2 Pros and 2 Cons. The picker is
//    meant to be a neutral comparison tool, not a recommendation.
//  - Never mark an option as "Recommended". Only mark the shipped
//    default as Default=true.
//  - Keep language specific and verifiable. No "best", "fastest",
//    "modern"; instead "single ~20 MB binary", "microsecond latency".

package ui

// BusBackends is the registry of available message bus backends for
// the `synthorg init` picker. The picker displays these as an
// unbiased comparison with equal-depth pros and cons.
//
// See docs/design/distributed-runtime.md for the full transport
// evaluation and migration path.
var BusBackends = []Option[string]{
	{
		ID:      "internal",
		Label:   "In-process queue (internal)",
		Summary: "asyncio queues inside the backend container. No extra services.",
		Pros: []string{
			"Zero setup, no extra container",
			"Microsecond-latency delivery",
			"Nothing extra to operate or monitor",
			"Works offline",
		},
		Cons: []string{
			"Single Python process only",
			"Messages and task queue are lost on backend crash",
			"No replay after restart",
			"Not observable from outside Python",
		},
		Default: true,
		Value:   "internal",
	},
	{
		ID:      "nats",
		Label:   "NATS JetStream (nats)",
		Summary: "separate ~20 MB container with file-backed streams.",
		Pros: []string{
			"Multi-process and multi-host agent execution",
			"Messages and task queue survive backend crashes",
			"Replay from any stream offset",
			"At-least-once delivery for the task queue with redelivery",
			"Inspectable via the nats CLI and Prometheus metrics",
			"Prerequisite for `synthorg worker start`",
		},
		Cons: []string{
			"Adds one container (~20 MB image, ~15 MB RAM idle)",
			"Network hop adds milliseconds of latency",
			"One more service to monitor and upgrade",
			"Additional configuration surface (URL, credentials, retention)",
		},
		Default: false,
		Value:   "nats",
	},
}
