package compose

// NATSConfigContent is the canonical NATS server config the CLI writes
// alongside compose.yml when the distributed bus mode is active. The
// rendered compose file references this via `configs.nats-config.file`.
//
// Settings rationale:
//   - `host: 0.0.0.0` so the broker accepts connections from other
//     services on the synthorg-net docker network.
//   - `jetstream.store_dir: /data` matches the synthorg-nats-data volume
//     mount, persisting JetStream state across container restarts.
//   - `max_payload: 16MB` is sized for SynthOrg's traffic: LLM agent
//     outputs, meeting transcripts, and large tool results routinely
//     exceed NATS's 1MB default. 16MB stays well under the 64MB hard
//     ceiling and gives ample headroom for transcript bundling.
const NATSConfigContent = `host: 0.0.0.0
port: 4222
http_port: 8222
jetstream {
  store_dir: /data
}
max_payload: 16MB
`

// NATSConfigFilename is the on-disk name for the NATS config file the
// CLI writes next to compose.yml. Kept as a package-level constant so
// init/update/start agree on the path without duplicating the string.
const NATSConfigFilename = "nats.conf"
