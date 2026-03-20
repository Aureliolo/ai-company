# Changelog

## [0.4.2](https://github.com/Aureliolo/synthorg/compare/v0.4.1...v0.4.2) (2026-03-20)


### Features

* implement LLM fallback for uncertain security evaluations ([#647](https://github.com/Aureliolo/synthorg/issues/647)) ([d13f6c9](https://github.com/Aureliolo/synthorg/commit/d13f6c9c77178fcd5525fab10dece63d9029175c))
* implement quota degradation FALLBACK and QUEUE strategies ([#650](https://github.com/Aureliolo/synthorg/issues/650)) ([5828051](https://github.com/Aureliolo/synthorg/commit/582805184ca923b2f87793140b0f3a60b0919e88))


### Bug Fixes

* CLI falsely reports missing images after update ([#648](https://github.com/Aureliolo/synthorg/issues/648)) ([aeb4680](https://github.com/Aureliolo/synthorg/commit/aeb4680dd643c507d25184febcfbb5bd2e677bdc))
* observability sink routing gaps and agent correlation binding ([#646](https://github.com/Aureliolo/synthorg/issues/646)) ([9bb56eb](https://github.com/Aureliolo/synthorg/commit/9bb56eb36f54bca69c755e4409d5ba7279727c83))
* setup wizard UX issues (step indicator, discovery, auth, toggle) ([#651](https://github.com/Aureliolo/synthorg/issues/651)) ([2f58421](https://github.com/Aureliolo/synthorg/commit/2f58421e52d404faf15bd8c0ca1314bbe9f721ef))


### Maintenance

* silence false-positive ESLint security warnings ([#649](https://github.com/Aureliolo/synthorg/issues/649)) ([e2dc171](https://github.com/Aureliolo/synthorg/commit/e2dc1718d23df2aeb7652a027d082c3d6be6bc05))

## [0.4.1](https://github.com/Aureliolo/synthorg/compare/v0.4.0...v0.4.1) (2026-03-20)


### Bug Fixes

* CLI update resilience + setup wizard UX overhaul ([#642](https://github.com/Aureliolo/synthorg/issues/642)) ([774e4e4](https://github.com/Aureliolo/synthorg/commit/774e4e461a832c6bad1d04a56aeaea75262b7856))

## [0.4.0](https://github.com/Aureliolo/synthorg/compare/v0.3.10...v0.4.0) (2026-03-20)


### Bug Fixes

* add WebSocket reconnect feedback and fix setup provider validation ([#636](https://github.com/Aureliolo/synthorg/issues/636)) ([77f14f0](https://github.com/Aureliolo/synthorg/commit/77f14f09f70a731dd8c7e09dd7468cc50040eb47))
* **api:** controller consistency, input validation, and auth rate limiting ([#638](https://github.com/Aureliolo/synthorg/issues/638)) ([1192a60](https://github.com/Aureliolo/synthorg/commit/1192a60b4633991fa84a314560983277d78fc143))
* **cli:** handle ignored errors in version parsing and flag reading ([#635](https://github.com/Aureliolo/synthorg/issues/635)) ([cfd7ce4](https://github.com/Aureliolo/synthorg/commit/cfd7ce4b41c8a3ceaf25c9cfda5382f11d81a2a5))
* prevent Litestar from destroying structlog file sinks and add provider auto-probe ([#639](https://github.com/Aureliolo/synthorg/issues/639)) ([476ee5f](https://github.com/Aureliolo/synthorg/commit/476ee5fc602556d0badfa0fb323dffd85228c838))


### Documentation

* add releasing instructions to CLAUDE.md ([#640](https://github.com/Aureliolo/synthorg/issues/640)) ([2e08ca4](https://github.com/Aureliolo/synthorg/commit/2e08ca4837a16695cc8aaebc1700503820aef9dc))

## [0.3.10](https://github.com/Aureliolo/synthorg/compare/v0.3.9...v0.3.10) (2026-03-20)


### Bug Fixes

* **ci:** generate required secrets in DAST workflow ([#623](https://github.com/Aureliolo/synthorg/issues/623)) ([6ae297f](https://github.com/Aureliolo/synthorg/commit/6ae297f881ba102cf73dd59f5b1b5bd723008279))
* **cli:** doctor image check reads compose file and fix API docs URL ([#625](https://github.com/Aureliolo/synthorg/issues/625)) ([5202e53](https://github.com/Aureliolo/synthorg/commit/5202e53771d6210712fb5e8f581bca3dee0e6ece))
* **engine:** sanitize error messages in checkpoint reconciliation and compaction summaries ([#632](https://github.com/Aureliolo/synthorg/issues/632)) ([5394ed7](https://github.com/Aureliolo/synthorg/commit/5394ed72f78a2b5439c98e25144d69005d36cea6))
* mitigate TOCTOU DNS rebinding gap in git clone SSRF prevention ([#633](https://github.com/Aureliolo/synthorg/issues/633)) ([1846f6e](https://github.com/Aureliolo/synthorg/commit/1846f6eef0650968e19b97c4c66002d04104006e))
* resolve post-startup log loss, add provider model discovery, and improve setup wizard UX ([#634](https://github.com/Aureliolo/synthorg/issues/634)) ([2df8d11](https://github.com/Aureliolo/synthorg/commit/2df8d1137caebbfca0e9819c33a29a867821e5c1))


### Maintenance

* bump https://github.com/astral-sh/ruff-pre-commit from v0.15.6 to 0.15.7 ([#628](https://github.com/Aureliolo/synthorg/issues/628)) ([c641d2c](https://github.com/Aureliolo/synthorg/commit/c641d2c35e0e8f43e2cc3f21253b656a580441f1))
* bump python from `584e89d` to `fb83750` in /docker/backend ([#627](https://github.com/Aureliolo/synthorg/issues/627)) ([1a36eca](https://github.com/Aureliolo/synthorg/commit/1a36ecab3783108b27c1d58038fb3cfee8671ac9))
* bump python from `584e89d` to `fb83750` in /docker/sandbox ([#629](https://github.com/Aureliolo/synthorg/issues/629)) ([fd3e69a](https://github.com/Aureliolo/synthorg/commit/fd3e69aa0ec8c8d43d5660d270b13372f81a4109))
* bump the minor-and-patch group across 2 directories with 3 updates ([#630](https://github.com/Aureliolo/synthorg/issues/630)) ([67d14c4](https://github.com/Aureliolo/synthorg/commit/67d14c4f95f9ce3621254ea2c214ae31a5949349))
* bump the minor-and-patch group with 2 updates ([#631](https://github.com/Aureliolo/synthorg/issues/631)) ([2e51b60](https://github.com/Aureliolo/synthorg/commit/2e51b60e9bdd2cedb7631c28aad38bc381303b13))
* **ci:** add timeout-minutes, harden fuzz script, extend CVE audit ([#626](https://github.com/Aureliolo/synthorg/issues/626)) ([25420e2](https://github.com/Aureliolo/synthorg/commit/25420e2714e5f4d94d78b877d16d4653a462dc47))

## [0.3.9](https://github.com/Aureliolo/synthorg/compare/v0.3.8...v0.3.9) (2026-03-19)


### Features

* add company description field to setup wizard ([#617](https://github.com/Aureliolo/synthorg/issues/617)) ([7c43693](https://github.com/Aureliolo/synthorg/commit/7c43693c8db1dd651760abe320ca416d576dcd5a))
* implement approval review gate and timeout scheduler ([#620](https://github.com/Aureliolo/synthorg/issues/620)) ([229d366](https://github.com/Aureliolo/synthorg/commit/229d366e9248b3afcbe3f238b9ef7910618976b5))


### Bug Fixes

* generate settings encryption key on init and flush log file handlers ([#621](https://github.com/Aureliolo/synthorg/issues/621)) ([60c5744](https://github.com/Aureliolo/synthorg/commit/60c574448c6bbb1e06761111f8eaae87c7c4462d))


### Maintenance

* remove premature versioning, migrations, and backward-compat scaffolding ([#618](https://github.com/Aureliolo/synthorg/issues/618)) ([5f6550b](https://github.com/Aureliolo/synthorg/commit/5f6550b1f9d41e97af50e121717dabde9bf82c72))

## [0.3.8](https://github.com/Aureliolo/synthorg/compare/v0.3.7...v0.3.8) (2026-03-19)


### Features

* dynamic settings UI with auto-discovery and basic/advanced toggle ([#600](https://github.com/Aureliolo/synthorg/issues/600)) ([11b32b7](https://github.com/Aureliolo/synthorg/commit/11b32b7b486e7a9145cb14a63067d04b63150235))


### Bug Fixes

* **ci:** remove dst: . from GoReleaser archive config ([#598](https://github.com/Aureliolo/synthorg/issues/598)) ([c8bf862](https://github.com/Aureliolo/synthorg/commit/c8bf862ae4a17680911241b2f543628054cfe9c4))
* **engine:** wire compaction_callback and plan_execute_config through auto-selection ([#601](https://github.com/Aureliolo/synthorg/issues/601)) ([795327f](https://github.com/Aureliolo/synthorg/commit/795327f33364d276c723aea1dc5ff93f4fa0226e))
* harden setup wizard completion and status checks ([#616](https://github.com/Aureliolo/synthorg/issues/616)) ([d99d7b7](https://github.com/Aureliolo/synthorg/commit/d99d7b7f22de60113fda657ab7fe39e83dcbd0ba))


### Maintenance

* add /codebase-audit skill for deep parallel codebase auditing ([#613](https://github.com/Aureliolo/synthorg/issues/613)) ([db02320](https://github.com/Aureliolo/synthorg/commit/db0232081b0c24a61784538d430a84167587f023))

## [0.3.7](https://github.com/Aureliolo/synthorg/compare/v0.3.6...v0.3.7) (2026-03-19)


### Features

* **engine:** implement Hybrid Plan + ReAct execution loop ([#582](https://github.com/Aureliolo/synthorg/issues/582)) ([008147c](https://github.com/Aureliolo/synthorg/commit/008147c698d3443c95618be4d783a5d3d3813005))
* implement first-run setup wizard ([#584](https://github.com/Aureliolo/synthorg/issues/584)) ([dfed931](https://github.com/Aureliolo/synthorg/commit/dfed93123bfd24fabc50bc52d46211343835efea))


### Bug Fixes

* **api:** address ZAP DAST scan findings ([#579](https://github.com/Aureliolo/synthorg/issues/579)) ([ce9a3e0](https://github.com/Aureliolo/synthorg/commit/ce9a3e077ab6af5743a8150333d225d0de9ab0d3))
* **ci:** remove CLI SBOM generation, reset failed v0.3.7 ([#595](https://github.com/Aureliolo/synthorg/issues/595)) ([d0f4992](https://github.com/Aureliolo/synthorg/commit/d0f4992e3a495e70ffeb43d1e1af6cdf6ba78130))
* **ci:** reset failed v0.3.7 release and fix syft SBOM scan ([#593](https://github.com/Aureliolo/synthorg/issues/593)) ([d1508c2](https://github.com/Aureliolo/synthorg/commit/d1508c2f1414d5e9a7dd07753581038584febee0))
* **cli:** auto-delete binary on Windows, prune images, fix GoReleaser ([#590](https://github.com/Aureliolo/synthorg/issues/590)) ([eb7c691](https://github.com/Aureliolo/synthorg/commit/eb7c691c333f36f2123fea68a8a4d9637111442d))
* **cli:** regenerate compose and re-exec binary on update ([#576](https://github.com/Aureliolo/synthorg/issues/576)) ([3f226eb](https://github.com/Aureliolo/synthorg/commit/3f226eb79b46de59c1e94319a046765353392de4))


### CI/CD

* add SBOM generation to Docker and CLI releases ([#580](https://github.com/Aureliolo/synthorg/issues/580)) ([db459cf](https://github.com/Aureliolo/synthorg/commit/db459cf0892c46f9a887126edd70aeaafe6b70d8))


### Maintenance

* **main:** release 0.3.7 ([#583](https://github.com/Aureliolo/synthorg/issues/583)) ([bf58779](https://github.com/Aureliolo/synthorg/commit/bf587792d8a5fb5508fb373d45e01648dc732dec))
* **main:** release 0.3.7 ([#592](https://github.com/Aureliolo/synthorg/issues/592)) ([2e8e633](https://github.com/Aureliolo/synthorg/commit/2e8e633afee489f4288f09a86580e50eb1e32d3f))
* **main:** release 0.3.7 ([#594](https://github.com/Aureliolo/synthorg/issues/594)) ([139dfc1](https://github.com/Aureliolo/synthorg/commit/139dfc1ab4d0cee3dc2b5d8be1a473761011fc8f))
* reset failed v0.3.7 release ([#591](https://github.com/Aureliolo/synthorg/issues/591)) ([b69000d](https://github.com/Aureliolo/synthorg/commit/b69000da37ae9092ff59698a15cf10abd3d06ebb))

## [0.3.6](https://github.com/Aureliolo/synthorg/compare/v0.3.5...v0.3.6) (2026-03-19)


### Features

* **cli:** add backup subcommands (backup, backup list, backup restore) ([#568](https://github.com/Aureliolo/synthorg/issues/568)) ([4c06b1d](https://github.com/Aureliolo/synthorg/commit/4c06b1d6bbe21a45cb7a83591afc824c4cc7b9a8))
* **engine:** implement execution loop auto-selection based on task complexity ([#567](https://github.com/Aureliolo/synthorg/issues/567)) ([5bfc2c6](https://github.com/Aureliolo/synthorg/commit/5bfc2c6b9bb8f2909596a3336f6056de81b8cb2b))


### Bug Fixes

* activate structured logging pipeline -- wire 8-sink system, integrate Uvicorn, suppress spam ([#572](https://github.com/Aureliolo/synthorg/issues/572)) ([9b6bf33](https://github.com/Aureliolo/synthorg/commit/9b6bf332954984d099c5967768581d70534a379d))
* **cli:** bump grpc-go v1.79.3 -- CVE-2026-33186 auth bypass ([#574](https://github.com/Aureliolo/synthorg/issues/574)) ([f0171c9](https://github.com/Aureliolo/synthorg/commit/f0171c932d4fa8fa32ebae71988ddeded82b4b9a))
* resolve OpenAPI schema validation warnings for union/optional fields ([#558](https://github.com/Aureliolo/synthorg/issues/558)) ([5d96b2b](https://github.com/Aureliolo/synthorg/commit/5d96b2bdb4cec91b762a97820e0100324e7651fc))


### CI/CD

* bump codecov/codecov-action from 5.5.2 to 5.5.3 in the minor-and-patch group ([#571](https://github.com/Aureliolo/synthorg/issues/571)) ([267f685](https://github.com/Aureliolo/synthorg/commit/267f6858d999a0653047dd57a196907fafd1a0d8))
* ignore chainguard/python in Dependabot docker updates ([#575](https://github.com/Aureliolo/synthorg/issues/575)) ([1935eaa](https://github.com/Aureliolo/synthorg/commit/1935eaaf357d7b01ff5c47903be7e3aa7f7ff79f))


### Maintenance

* bump the major group across 1 directory with 2 updates ([#570](https://github.com/Aureliolo/synthorg/issues/570)) ([b98f82c](https://github.com/Aureliolo/synthorg/commit/b98f82c55e1375fd3ffafbd1b941f62dbc8b49d6))
* bump the minor-and-patch group across 2 directories with 4 updates ([#569](https://github.com/Aureliolo/synthorg/issues/569)) ([3295168](https://github.com/Aureliolo/synthorg/commit/32951688f1e8b7f715ab1f0bf6bf33cf8d23b8f0))

## [0.3.5](https://github.com/Aureliolo/synthorg/compare/v0.3.4...v0.3.5) (2026-03-18)


### Features

* **api:** auto-wire backend services at startup ([#555](https://github.com/Aureliolo/synthorg/issues/555)) ([0e52c47](https://github.com/Aureliolo/synthorg/commit/0e52c471c43ea24392f0329f64580577b9c0cfff))


### Bug Fixes

* **api:** resolve WebSocket 403 rejection ([#549](https://github.com/Aureliolo/synthorg/issues/549)) ([#556](https://github.com/Aureliolo/synthorg/issues/556)) ([60453d2](https://github.com/Aureliolo/synthorg/commit/60453d2aca0b3d0a9715bcc479209c2a3b54b9c4))
* **cli:** verify SLSA provenance via GitHub attestation API ([#548](https://github.com/Aureliolo/synthorg/issues/548)) ([91d4f79](https://github.com/Aureliolo/synthorg/commit/91d4f79eb946825ef4b0bffd133353e292a4cadb)), closes [#532](https://github.com/Aureliolo/synthorg/issues/532)


### Performance

* **test:** speed up test suite -- reduce Hypothesis examples and eliminate real sleeps ([#557](https://github.com/Aureliolo/synthorg/issues/557)) ([d5f3a41](https://github.com/Aureliolo/synthorg/commit/d5f3a411b48db3e69e6be822afc19e64c27d0ba8))


### Refactoring

* replace _ErrorResponseSpec NamedTuple with TypedDict ([#554](https://github.com/Aureliolo/synthorg/issues/554)) ([71cc6e1](https://github.com/Aureliolo/synthorg/commit/71cc6e10ef12fe2ab064b16bfccf8d9861d966c1))


### Maintenance

* **docker:** suppress pydantic v1 warning on Python 3.14 ([#552](https://github.com/Aureliolo/synthorg/issues/552)) ([cbe1f05](https://github.com/Aureliolo/synthorg/commit/cbe1f051ae36c4d6f6601444324f40309266e83c)), closes [#551](https://github.com/Aureliolo/synthorg/issues/551)

## [0.3.4](https://github.com/Aureliolo/synthorg/compare/v0.3.3...v0.3.4) (2026-03-18)


### Bug Fixes

* **cli:** support cosign v3 bundle format for signature verification ([#546](https://github.com/Aureliolo/synthorg/issues/546)) ([6115eff](https://github.com/Aureliolo/synthorg/commit/6115eff5de14b5a18ebbe789f8a77d21f38e7f8c)), closes [#532](https://github.com/Aureliolo/synthorg/issues/532)

## [0.3.3](https://github.com/Aureliolo/synthorg/compare/v0.3.2...v0.3.3) (2026-03-18)


### Features

* **backup:** implement automated backup and restore system ([#541](https://github.com/Aureliolo/synthorg/issues/541)) ([867b7c1](https://github.com/Aureliolo/synthorg/commit/867b7c1b473a4da7472e6982cc971de9fffd9416))
* **providers:** runtime provider management with CRUD, presets, and multi-auth ([#540](https://github.com/Aureliolo/synthorg/issues/540)) ([936c345](https://github.com/Aureliolo/synthorg/commit/936c3455f635fe72da87230ae3d57f18a889f36e)), closes [#451](https://github.com/Aureliolo/synthorg/issues/451)
* **tools:** wire per-category sandbox backend selection ([#534](https://github.com/Aureliolo/synthorg/issues/534)) ([311a1ab](https://github.com/Aureliolo/synthorg/commit/311a1abd6978ecbb268b844ab711bd0e199c6dc3))


### Bug Fixes

* **ci:** add COSIGN_EXPERIMENTAL=1 for OCI referrer mode in cosign sign ([#543](https://github.com/Aureliolo/synthorg/issues/543)) ([226ed2f](https://github.com/Aureliolo/synthorg/commit/226ed2f3b976cd95cc96bf58be0eafc5581189a1))
* **cli:** switch cosign verification from .sig tags to OCI referrers ([#533](https://github.com/Aureliolo/synthorg/issues/533)) ([8ee5471](https://github.com/Aureliolo/synthorg/commit/8ee547140ab9c06c5ed900f2b3171fc2bbc26572)), closes [#532](https://github.com/Aureliolo/synthorg/issues/532)


### CI/CD

* bump wrangler from 4.74.0 to 4.75.0 in /.github in the minor-and-patch group ([#535](https://github.com/Aureliolo/synthorg/issues/535)) ([de15867](https://github.com/Aureliolo/synthorg/commit/de158670810dd25e2fdceb3191af302e5c299245))


### Maintenance

* bump github.com/google/go-containerregistry from 0.21.2 to 0.21.3 in /cli in the minor-and-patch group ([#536](https://github.com/Aureliolo/synthorg/issues/536)) ([4a09aed](https://github.com/Aureliolo/synthorg/commit/4a09aed16e4ec0ef557690041f8b35fa44a3a733))
* bump litellm from 1.82.3 to 1.82.4 in the minor-and-patch group ([#538](https://github.com/Aureliolo/synthorg/issues/538)) ([9f7f83d](https://github.com/Aureliolo/synthorg/commit/9f7f83d8cf31d44ae8f08108b64e60857785dbd3))
* bump vue-tsc from 3.2.5 to 3.2.6 in /web in the minor-and-patch group across 1 directory ([#537](https://github.com/Aureliolo/synthorg/issues/537)) ([eb3dc4e](https://github.com/Aureliolo/synthorg/commit/eb3dc4ea7e46e62729bab26a87a2ed849e09f564))
* **main:** release 0.3.3 ([#539](https://github.com/Aureliolo/synthorg/issues/539)) ([c3de2a2](https://github.com/Aureliolo/synthorg/commit/c3de2a24c3612a6d4f7f3cd3932a53507472530f))
* revert v0.3.3 release artifacts (Docker signing failed) ([#544](https://github.com/Aureliolo/synthorg/issues/544)) ([7f48f52](https://github.com/Aureliolo/synthorg/commit/7f48f5262a7124ae79d51a4e4dd523d18b42d93a))

## [0.3.2](https://github.com/Aureliolo/synthorg/compare/v0.3.1...v0.3.2) (2026-03-17)


### Features

* **settings:** route structural data reads through SettingsService ([#525](https://github.com/Aureliolo/synthorg/issues/525)) ([289f604](https://github.com/Aureliolo/synthorg/commit/289f6047681fa8b4eecd227e317360a4f32bf0d4))


### Bug Fixes

* **cli:** add fallback arch detection in PowerShell installer ([#529](https://github.com/Aureliolo/synthorg/issues/529)) ([0250afb](https://github.com/Aureliolo/synthorg/commit/0250afbf5aabca8ba8e2e9ca2b01cc8fff3bdf8a)), closes [#521](https://github.com/Aureliolo/synthorg/issues/521)


### CI/CD

* bump the minor-and-patch group with 2 updates ([#517](https://github.com/Aureliolo/synthorg/issues/517)) ([46bdd1a](https://github.com/Aureliolo/synthorg/commit/46bdd1a49080ac1127aa99b7729edc92bc9ab195))
* bump wrangler from 4.73.0 to 4.74.0 in /.github in the minor-and-patch group ([#511](https://github.com/Aureliolo/synthorg/issues/511)) ([903b71a](https://github.com/Aureliolo/synthorg/commit/903b71ae73fd0b7d7642eb17958e6763141478c5))


### Maintenance

* bump node from `7a4ef57` to `44bcbf4` in /docker/sandbox ([#515](https://github.com/Aureliolo/synthorg/issues/515)) ([3cbddd1](https://github.com/Aureliolo/synthorg/commit/3cbddd1ce4ef665f20aa3be9d5a67786d7ff7364))
* bump python from `6a27522` to `584e89d` in /docker/backend ([#513](https://github.com/Aureliolo/synthorg/issues/513)) ([0715910](https://github.com/Aureliolo/synthorg/commit/0715910445ea5db5b924b69c985fee6e3f9a236c))
* bump python from `6a27522` to `584e89d` in /docker/sandbox ([#514](https://github.com/Aureliolo/synthorg/issues/514)) ([787dfe1](https://github.com/Aureliolo/synthorg/commit/787dfe1cbfa86b3de63a84e4888e6508402660bd))
* bump the minor-and-patch group across 1 directory with 2 updates ([#527](https://github.com/Aureliolo/synthorg/issues/527)) ([e96c0d4](https://github.com/Aureliolo/synthorg/commit/e96c0d44879aa91f374c969c9522342ca4dd3384))
* bump the minor-and-patch group across 2 directories with 3 updates ([#512](https://github.com/Aureliolo/synthorg/issues/512)) ([b95ba3d](https://github.com/Aureliolo/synthorg/commit/b95ba3da089c97e137de29e0b287239809db7960))
* **docker:** disable Mem0 telemetry in container config ([#531](https://github.com/Aureliolo/synthorg/issues/531)) ([9fc29eb](https://github.com/Aureliolo/synthorg/commit/9fc29ebeb8c24e88153a8c9abd54f9772dd79afd))
* improve GitHub issue templates with structured forms ([#528](https://github.com/Aureliolo/synthorg/issues/528)) ([4fb66cf](https://github.com/Aureliolo/synthorg/commit/4fb66cf45d59523b21461b1ffe0820abac34acfe)), closes [#522](https://github.com/Aureliolo/synthorg/issues/522)

## [0.3.1](https://github.com/Aureliolo/synthorg/compare/v0.3.0...v0.3.1) (2026-03-17)


### Features

* **api:** RFC 9457 Phase 2 — ProblemDetail and content negotiation ([#496](https://github.com/Aureliolo/synthorg/issues/496)) ([30f7c49](https://github.com/Aureliolo/synthorg/commit/30f7c49ff2562919988ed510abd805ba3752ae92))
* **cli:** verify container image signatures and SLSA provenance on pull ([#492](https://github.com/Aureliolo/synthorg/issues/492)) ([bef272d](https://github.com/Aureliolo/synthorg/commit/bef272d37e0020e9f33da2ce611d33cf749d570f)), closes [#491](https://github.com/Aureliolo/synthorg/issues/491)
* **engine:** implement context budget management in execution loops ([#520](https://github.com/Aureliolo/synthorg/issues/520)) ([181eb8a](https://github.com/Aureliolo/synthorg/commit/181eb8a7f289e72239916a7832fb64bc5b47f1e1)), closes [#416](https://github.com/Aureliolo/synthorg/issues/416)
* implement settings persistence layer (DB-backed config) ([#495](https://github.com/Aureliolo/synthorg/issues/495)) ([4bd99f7](https://github.com/Aureliolo/synthorg/commit/4bd99f7c242cf611ec2dadcaaf3d46a21bec20c3)), closes [#450](https://github.com/Aureliolo/synthorg/issues/450)
* **memory:** implement dual-mode archival in memory consolidation ([#524](https://github.com/Aureliolo/synthorg/issues/524)) ([4603c9e](https://github.com/Aureliolo/synthorg/commit/4603c9e1196b7f5f49e727e3469ce347c7f05f40)), closes [#418](https://github.com/Aureliolo/synthorg/issues/418)
* migrate config consumers to read through SettingsService ([#510](https://github.com/Aureliolo/synthorg/issues/510)) ([32f553d](https://github.com/Aureliolo/synthorg/commit/32f553d6d166d8ba6ca13186de267ae5d9cc5139))
* **settings:** implement settings change subscriptions for service hot-reload ([#526](https://github.com/Aureliolo/synthorg/issues/526)) ([53f908e](https://github.com/Aureliolo/synthorg/commit/53f908ed11a925cbb084f2b8cead8539ca0d138a)), closes [#503](https://github.com/Aureliolo/synthorg/issues/503)
* **settings:** register API config in SettingsService with 2-phase init ([#518](https://github.com/Aureliolo/synthorg/issues/518)) ([29f7481](https://github.com/Aureliolo/synthorg/commit/29f7481c03607592f6c3e3f2051eee4352840637))
* **tools:** add SSRF prevention for git clone URLs ([#505](https://github.com/Aureliolo/synthorg/issues/505)) ([492dd0d](https://github.com/Aureliolo/synthorg/commit/492dd0d40ec7890bb41325214cf9288190aa303d))
* **tools:** wire RootConfig.git_clone to GitCloneTool instantiation ([#519](https://github.com/Aureliolo/synthorg/issues/519)) ([b7d8172](https://github.com/Aureliolo/synthorg/commit/b7d81729e7c39590ed382f71bf005046c94be01f))


### Bug Fixes

* **api:** replace JWT query parameter with one-time ticket for WebSocket auth ([#493](https://github.com/Aureliolo/synthorg/issues/493)) ([22a25f6](https://github.com/Aureliolo/synthorg/commit/22a25f6f03685a3509875ca2d1299c432db34301)), closes [#343](https://github.com/Aureliolo/synthorg/issues/343)


### Documentation

* add uv cache lock contention handling to worktree skill ([#500](https://github.com/Aureliolo/synthorg/issues/500)) ([bd85a8d](https://github.com/Aureliolo/synthorg/commit/bd85a8dd15bb716addb29c96488f22d4d3b21745))
* document RFC 9457 dual response formats in OpenAPI schema ([#506](https://github.com/Aureliolo/synthorg/issues/506)) ([8dd2524](https://github.com/Aureliolo/synthorg/commit/8dd25245ec9c01e0de53f334dec8adb1c5154836))


### Maintenance

* upgrade jsdom from 28 to 29 ([#499](https://github.com/Aureliolo/synthorg/issues/499)) ([1ea2249](https://github.com/Aureliolo/synthorg/commit/1ea2249720482e20281424488a6f17bb012a8410))

## [0.3.0](https://github.com/Aureliolo/synthorg/compare/v0.2.9...v0.3.0) (2026-03-16)


### Features

* **cli:** prettify status output with table, links, and --json flag ([#490](https://github.com/Aureliolo/synthorg/issues/490)) ([61fa8af](https://github.com/Aureliolo/synthorg/commit/61fa8afe55667a34eca3b53aa5604e12f15f36cd))


### Bug Fixes

* **api:** don't require password change after self-service setup ([#488](https://github.com/Aureliolo/synthorg/issues/488)) ([ba13e04](https://github.com/Aureliolo/synthorg/commit/ba13e041969f71ab4dd6925a9487c91dc94776f9))

## [0.2.9](https://github.com/Aureliolo/synthorg/compare/v0.2.8...v0.2.9) (2026-03-16)


### Bug Fixes

* **api:** auto-wire persistence backend from SYNTHORG_DB_PATH env var ([#486](https://github.com/Aureliolo/synthorg/issues/486)) ([7973b07](https://github.com/Aureliolo/synthorg/commit/7973b07f990ee01b369bccabf679101693efc7da))
* **cli:** completion cleanup on uninstall + init backend selection ([#484](https://github.com/Aureliolo/synthorg/issues/484)) ([97ccb51](https://github.com/Aureliolo/synthorg/commit/97ccb51416b55815a9befc8d1b05abedf41ef7d5))
* **docker:** keep sandbox container alive with sleep infinity ([#485](https://github.com/Aureliolo/synthorg/issues/485)) ([b9f400f](https://github.com/Aureliolo/synthorg/commit/b9f400f165a19b37438051029f405f28285c06ba))

## [0.2.8](https://github.com/Aureliolo/synthorg/compare/v0.2.7...v0.2.8) (2026-03-16)


### Features

* add RRF rank fusion to memory ranking ([#478](https://github.com/Aureliolo/synthorg/issues/478)) ([42242b5](https://github.com/Aureliolo/synthorg/commit/42242b51e5f6d4c2d034d569d20652f5175abf91))
* collaboration scoring enhancements — LLM sampling and human override ([#477](https://github.com/Aureliolo/synthorg/issues/477)) ([b3f3330](https://github.com/Aureliolo/synthorg/commit/b3f33303e9a2dbcb57c59b7ed32cc5fda292398d))


### Bug Fixes

* add .gitattributes to enforce LF line endings for Go files ([#483](https://github.com/Aureliolo/synthorg/issues/483)) ([1b8c7b6](https://github.com/Aureliolo/synthorg/commit/1b8c7b618a55194ddd925b9e0c11a9b481e2f2d7))
* **cli:** Windows uninstall, update UX, health check, sigstore ([#476](https://github.com/Aureliolo/synthorg/issues/476)) ([470ca72](https://github.com/Aureliolo/synthorg/commit/470ca7251235294b7d30a042d28988fea12695c3))


### Refactoring

* **web:** extract WebSocket subscription into reusable composable ([#475](https://github.com/Aureliolo/synthorg/issues/475)) ([96e6c46](https://github.com/Aureliolo/synthorg/commit/96e6c466b115462b1a2248310d5d778e0232592c)), closes [#351](https://github.com/Aureliolo/synthorg/issues/351)


### Maintenance

* bump hypothesis from 6.151.5 to 6.151.9 in the minor-and-patch group ([#482](https://github.com/Aureliolo/synthorg/issues/482)) ([a7297d5](https://github.com/Aureliolo/synthorg/commit/a7297d57401efbca38ae38364c2d39c773cd3ec7))
* bump nginxinc/nginx-unprivileged from `aec540f` to `ccbac1a` in /docker/web ([#479](https://github.com/Aureliolo/synthorg/issues/479)) ([176e052](https://github.com/Aureliolo/synthorg/commit/176e052ec4957652bef98cdbed2d3b864f63f089))

## [0.2.7](https://github.com/Aureliolo/synthorg/compare/v0.2.6...v0.2.7) (2026-03-15)


### Bug Fixes

* pre-create release tag before Release Please runs ([#473](https://github.com/Aureliolo/synthorg/issues/473)) ([568187b](https://github.com/Aureliolo/synthorg/commit/568187b2ff6c30f32ba62910463c42dff102fa57))
* **site:** show success message after contact form submission ([#474](https://github.com/Aureliolo/synthorg/issues/474)) ([f782e48](https://github.com/Aureliolo/synthorg/commit/f782e487241b045e12cb734818e8597b8b3962cd))


### Maintenance

* add path filtering to pre-push Python hooks ([#470](https://github.com/Aureliolo/synthorg/issues/470)) ([ef51797](https://github.com/Aureliolo/synthorg/commit/ef51797d1d8ea1f7e430b7eef94ae8c474248a86))

## [0.2.6](https://github.com/Aureliolo/synthorg/compare/v0.2.5...v0.2.6) (2026-03-15)


### Features

* add intra-loop stagnation detector ([#415](https://github.com/Aureliolo/synthorg/issues/415)) ([#458](https://github.com/Aureliolo/synthorg/issues/458)) ([8e9f34f](https://github.com/Aureliolo/synthorg/commit/8e9f34f9a2118a5cbbbcbc0076e384d353d1b3c2))
* add RFC 9457 structured error responses (Phase 1) ([#457](https://github.com/Aureliolo/synthorg/issues/457)) ([6612a99](https://github.com/Aureliolo/synthorg/commit/6612a994c625489741f2c20887fa9fe91bf232fc)), closes [#419](https://github.com/Aureliolo/synthorg/issues/419)
* implement AgentStateRepository for runtime state persistence ([#459](https://github.com/Aureliolo/synthorg/issues/459)) ([5009da7](https://github.com/Aureliolo/synthorg/commit/5009da7915ef02e79995ecbc3c8425704b9517ba))
* **site:** add SEO essentials, contact form, early-access banner ([#467](https://github.com/Aureliolo/synthorg/issues/467)) ([11b645e](https://github.com/Aureliolo/synthorg/commit/11b645ee8b72aba0b48c17e1c00b3781cedb7b20)), closes [#466](https://github.com/Aureliolo/synthorg/issues/466)


### Bug Fixes

* CLI improvements — config show, completion install, enhanced doctor, Sigstore verification ([#465](https://github.com/Aureliolo/synthorg/issues/465)) ([9e08cec](https://github.com/Aureliolo/synthorg/commit/9e08cec314faa82d6baf603bf51db31528f41d19))
* **site:** add reCAPTCHA v3, main landmark, and docs sitemap ([#469](https://github.com/Aureliolo/synthorg/issues/469)) ([fa6d35c](https://github.com/Aureliolo/synthorg/commit/fa6d35c0025fd9a7507d1bf3f307f6ce435721c1))
* use force-tag-creation instead of manual tag creation hack ([#462](https://github.com/Aureliolo/synthorg/issues/462)) ([2338004](https://github.com/Aureliolo/synthorg/commit/23380049d5a824731d47a22d7baf64af32375ff2))

## [0.2.5](https://github.com/Aureliolo/synthorg/compare/v0.2.4...v0.2.5) (2026-03-15)


### Features

* default sandbox to enabled, polish CLI output, add sandbox CI build ([#455](https://github.com/Aureliolo/synthorg/issues/455)) ([a4869b6](https://github.com/Aureliolo/synthorg/commit/a4869b698afa252cac951a2903a782d3ab34a5a4))


### Bug Fixes

* export .intoto.jsonl provenance for OpenSSF Scorecard ([#456](https://github.com/Aureliolo/synthorg/issues/456)) ([2feed09](https://github.com/Aureliolo/synthorg/commit/2feed0913244258cd84926da18c4a7d1b5a856f7))


### Maintenance

* add pyrightconfig.json and fix all pyright errors ([#448](https://github.com/Aureliolo/synthorg/issues/448)) ([f60746a](https://github.com/Aureliolo/synthorg/commit/f60746a50f7539b389ff8605cff6b940ecb39856))

## [0.2.4](https://github.com/Aureliolo/synthorg/compare/v0.2.3...v0.2.4) (2026-03-15)


### Bug Fixes

* attach cosign signatures and provenance bundle to release assets ([#438](https://github.com/Aureliolo/synthorg/issues/438)) ([f191a4d](https://github.com/Aureliolo/synthorg/commit/f191a4dc810b90434ee01a44fe9827ac2f738232))
* create git tag explicitly for draft releases ([#432](https://github.com/Aureliolo/synthorg/issues/432)) ([1f5120e](https://github.com/Aureliolo/synthorg/commit/1f5120ee80bca0441a38b399d9b26675e5029df8))
* docker healthcheck, CI optimization, and container hardening ([#436](https://github.com/Aureliolo/synthorg/issues/436)) ([4d32bca](https://github.com/Aureliolo/synthorg/commit/4d32bca76ceb20715457713f16a9d97f284ecb87))
* ensure security headers on all HTTP responses ([#437](https://github.com/Aureliolo/synthorg/issues/437)) ([837f2fc](https://github.com/Aureliolo/synthorg/commit/837f2fcca858cec4e2083a43c5ad5a0899ae6bc9))
* make install scripts usable immediately without terminal restart ([#433](https://github.com/Aureliolo/synthorg/issues/433)) ([b45533c](https://github.com/Aureliolo/synthorg/commit/b45533c9742b6f1d43cf386804d52cf996eaf663))
* migrate pids_limit to deploy.resources.limits.pids ([#439](https://github.com/Aureliolo/synthorg/issues/439)) ([66b94fd](https://github.com/Aureliolo/synthorg/commit/66b94fdb7f1d121df0463a13df01a2f0c3a8f52a))
* use cosign --bundle flag for checksums signing ([#443](https://github.com/Aureliolo/synthorg/issues/443)) ([19735b9](https://github.com/Aureliolo/synthorg/commit/19735b98dbe9152fd1071dd54eb13fa5eee6502c))


### Refactoring

* redesign release notes layout ([#434](https://github.com/Aureliolo/synthorg/issues/434)) ([239aaf7](https://github.com/Aureliolo/synthorg/commit/239aaf783135a9cb163cc573c62975a4fb04ab5a))


### Maintenance

* **main:** release 0.2.4 ([#431](https://github.com/Aureliolo/synthorg/issues/431)) ([63b03c4](https://github.com/Aureliolo/synthorg/commit/63b03c4c1f5c2469aae38f47a89b6e79210ebe4e))
* remove stale v0.2.4 changelog section from failed release ([#446](https://github.com/Aureliolo/synthorg/issues/446)) ([769de10](https://github.com/Aureliolo/synthorg/commit/769de107cf10513469d61e850d9340b5066bf26a))
* reset version to 0.2.3 for re-release ([#444](https://github.com/Aureliolo/synthorg/issues/444)) ([8579993](https://github.com/Aureliolo/synthorg/commit/857999326232b13a41bbe40215ac21460c5b7268))
* **site:** replace hero CTA with license link and scroll arrow ([#440](https://github.com/Aureliolo/synthorg/issues/440)) ([56af41c](https://github.com/Aureliolo/synthorg/commit/56af41c833d82857ccf3f60020687ed7d85ca49d))
* **web:** adopt @vue/tsconfig preset ([#435](https://github.com/Aureliolo/synthorg/issues/435)) ([7d4b214](https://github.com/Aureliolo/synthorg/commit/7d4b214cc22ec99b922dd46bb529e9c8af476b23))

## [0.2.3](https://github.com/Aureliolo/synthorg/compare/v0.2.2...v0.2.3) (2026-03-15)


### Bug Fixes

* use draft releases to support immutable release policy ([#429](https://github.com/Aureliolo/synthorg/issues/429)) ([a6c7444](https://github.com/Aureliolo/synthorg/commit/a6c7444b12239422a98a81c294a139cce96abc4a))

## [0.2.2](https://github.com/Aureliolo/synthorg/compare/v0.2.1...v0.2.2) (2026-03-15)


### Bug Fixes

* restore golangci-lint to v2.11.3 (broken by replace_all in [#425](https://github.com/Aureliolo/synthorg/issues/425)) ([#427](https://github.com/Aureliolo/synthorg/issues/427)) ([8ba9375](https://github.com/Aureliolo/synthorg/commit/8ba9375fbb4f8372486a05f3a6600f2a5710702d))

## [0.2.1](https://github.com/Aureliolo/synthorg/compare/v0.2.0...v0.2.1) (2026-03-15)


### Bug Fixes

* upgrade goreleaser to v2.14.3 (v2.11.3 never existed) ([#425](https://github.com/Aureliolo/synthorg/issues/425)) ([df6650d](https://github.com/Aureliolo/synthorg/commit/df6650d514976d6dfd73babe94fda107dd5714f1))

## [0.2.0](https://github.com/Aureliolo/synthorg/compare/v0.1.4...v0.2.0) (2026-03-15)


### Features

* add /get/ installation page for CLI installer ([#413](https://github.com/Aureliolo/synthorg/issues/413)) ([6a47e4a](https://github.com/Aureliolo/synthorg/commit/6a47e4aa89db39ebde26b33b4bc7bde713262e6a))
* add cross-platform Go CLI for container lifecycle management ([#401](https://github.com/Aureliolo/synthorg/issues/401)) ([0353d9e](https://github.com/Aureliolo/synthorg/commit/0353d9ee46a0a97d425ae8daba087a6b72228a43)), closes [#392](https://github.com/Aureliolo/synthorg/issues/392)
* add explicit ScanOutcome signal to OutputScanResult ([#394](https://github.com/Aureliolo/synthorg/issues/394)) ([be33414](https://github.com/Aureliolo/synthorg/commit/be334141af54dbe5bc16ac2380350f76da012c38)), closes [#284](https://github.com/Aureliolo/synthorg/issues/284)
* add meeting scheduler, event-triggered meetings, and Go CLI lint fixes ([#407](https://github.com/Aureliolo/synthorg/issues/407)) ([5550fa1](https://github.com/Aureliolo/synthorg/commit/5550fa1cf31f86c39183bf002fba793e19392cb6))
* wire MultiAgentCoordinator into runtime ([#396](https://github.com/Aureliolo/synthorg/issues/396)) ([7a9e516](https://github.com/Aureliolo/synthorg/commit/7a9e5166952693a23d22f2bfb6750557c89936db))


### Bug Fixes

* CLA signatures branch + declutter repo root ([#409](https://github.com/Aureliolo/synthorg/issues/409)) ([cabe953](https://github.com/Aureliolo/synthorg/commit/cabe95301d4e44267aa2ddfd93580083b7e8c155))
* correct Release Please branch name in release workflow ([#410](https://github.com/Aureliolo/synthorg/issues/410)) ([515d816](https://github.com/Aureliolo/synthorg/commit/515d816b36fba0d7b95385df92f3f7e711936d40))
* replace slsa-github-generator with attest-build-provenance, fix DAST ([#424](https://github.com/Aureliolo/synthorg/issues/424)) ([eeaadff](https://github.com/Aureliolo/synthorg/commit/eeaadff789f6179fe99874cf9f2caf89b6d3e6ea))
* resolve CodeQL path-injection alerts in Go CLI ([#412](https://github.com/Aureliolo/synthorg/issues/412)) ([f41bf16](https://github.com/Aureliolo/synthorg/commit/f41bf1642fbf6c5242d336980bb7e413b52d2c13))


### Refactoring

* rename package from ai_company to synthorg ([#422](https://github.com/Aureliolo/synthorg/issues/422)) ([df27c6e](https://github.com/Aureliolo/synthorg/commit/df27c6e4c43546201e9e9d459981039acf177655)), closes [#398](https://github.com/Aureliolo/synthorg/issues/398)


### Tests

* add fuzz and property-based testing across all layers ([#421](https://github.com/Aureliolo/synthorg/issues/421)) ([115a742](https://github.com/Aureliolo/synthorg/commit/115a742c7259a08c9c714ac47ec52704fb997e49))


### CI/CD

* add SLSA L3 provenance for CLI binaries and container images ([#423](https://github.com/Aureliolo/synthorg/issues/423)) ([d3dc75d](https://github.com/Aureliolo/synthorg/commit/d3dc75d3f6449959504ddd032d56e769f5f3f679))
* bump the major group with 4 updates ([#405](https://github.com/Aureliolo/synthorg/issues/405)) ([20c7a04](https://github.com/Aureliolo/synthorg/commit/20c7a04a5fccd3296cdad57df4af757e9f6abb57))


### Maintenance

* bump github.com/spf13/cobra from 1.9.1 to 1.10.2 in /cli in the minor-and-patch group ([#402](https://github.com/Aureliolo/synthorg/issues/402)) ([e31edbb](https://github.com/Aureliolo/synthorg/commit/e31edbb5d2e21439c88c98ef8c1847d23759e94a))
* narrow BSL Additional Use Grant and add CLA ([#408](https://github.com/Aureliolo/synthorg/issues/408)) ([5ab15bd](https://github.com/Aureliolo/synthorg/commit/5ab15bd1355063144076d735815ad3e34d1cbbb0)), closes [#406](https://github.com/Aureliolo/synthorg/issues/406)

## [0.1.4](https://github.com/Aureliolo/synthorg/compare/v0.1.3...v0.1.4) (2026-03-14)


### License

* narrow BSL 1.1 Additional Use Grant — free production use for non-competing organizations with fewer than 500 employees and contractors ([#406](https://github.com/Aureliolo/synthorg/issues/406))
* add Contributor License Agreement (CLA) with automated enforcement for dual-licensing support
* add licensing rationale documentation page explaining BSL choice, what's permitted, and invitation for feedback
* auto-update BSL Change Date to 3 years ahead on each release


### Features

* add approval workflow gates to TaskEngine ([#387](https://github.com/Aureliolo/synthorg/issues/387)) ([2db968a](https://github.com/Aureliolo/synthorg/commit/2db968a21fb0f0afa42eb990ee70cbb7b71d2ae5))
* implement checkpoint recovery strategy ([#367](https://github.com/Aureliolo/synthorg/issues/367)) ([f886838](https://github.com/Aureliolo/synthorg/commit/f886838af9789a1ed9834f1c16883e893c764761))


### CI/CD

* add npm and pre-commit ecosystems to Dependabot ([#369](https://github.com/Aureliolo/synthorg/issues/369)) ([54e5fe7](https://github.com/Aureliolo/synthorg/commit/54e5fe7c0351cd44ffd638fe662a4394e4a2eeea))
* bump actions/setup-node from 4.4.0 to 6.3.0 ([#360](https://github.com/Aureliolo/synthorg/issues/360)) ([2db5105](https://github.com/Aureliolo/synthorg/commit/2db5105429da3937daa8d0bb58593cc8dacd756f))
* bump github/codeql-action from 3.32.6 to 4.32.6 ([#361](https://github.com/Aureliolo/synthorg/issues/361)) ([ce766e8](https://github.com/Aureliolo/synthorg/commit/ce766e8b655af0cb80674a37eabd379ba0794011))
* group major dependabot bumps per ecosystem ([#388](https://github.com/Aureliolo/synthorg/issues/388)) ([3c43aef](https://github.com/Aureliolo/synthorg/commit/3c43aef7660a78fbfa337d448d954d21ed928806))


### Maintenance

* bump @vitejs/plugin-vue from 5.2.4 to 6.0.5 in /web ([#382](https://github.com/Aureliolo/synthorg/issues/382)) ([d7054ee](https://github.com/Aureliolo/synthorg/commit/d7054ee2c379341211e8dbd088ec2d03f8887e9c))
* bump @vue/tsconfig from 0.7.0 to 0.9.0 in /web in the minor-and-patch group across 1 directory ([#371](https://github.com/Aureliolo/synthorg/issues/371)) ([64fa08b](https://github.com/Aureliolo/synthorg/commit/64fa08b63ab8e7c30fbb2b94c40b2a3aa9044df4))
* bump astro from 5.18.1 to 6.0.4 in /site ([#376](https://github.com/Aureliolo/synthorg/issues/376)) ([d349317](https://github.com/Aureliolo/synthorg/commit/d349317a189e97e625b39d038387b9e324e56d8f))
* bump https://github.com/astral-sh/ruff-pre-commit from v0.15.5 to 0.15.6 ([#372](https://github.com/Aureliolo/synthorg/issues/372)) ([dcacb2e](https://github.com/Aureliolo/synthorg/commit/dcacb2eb3a890b7b1e4907a881b3fe87ba11f083))
* bump https://github.com/gitleaks/gitleaks from v8.24.3 to 8.30.1 ([#375](https://github.com/Aureliolo/synthorg/issues/375)) ([a18e6ed](https://github.com/Aureliolo/synthorg/commit/a18e6ed04f9bcb02b132f1e0ff161046948bc3fa))
* bump https://github.com/hadolint/hadolint from v2.12.0 to 2.14.0 ([#373](https://github.com/Aureliolo/synthorg/issues/373)) ([47b906b](https://github.com/Aureliolo/synthorg/commit/47b906b63e46678d2acec50f5a45f2916cd65086))
* bump https://github.com/pre-commit/pre-commit-hooks from v5.0.0 to 6.0.0 ([#374](https://github.com/Aureliolo/synthorg/issues/374)) ([1926555](https://github.com/Aureliolo/synthorg/commit/1926555d8116d3d60902bce789c1f3e0e6ec96e0))
* bump litellm from 1.82.1 to 1.82.2 in the minor-and-patch group ([#385](https://github.com/Aureliolo/synthorg/issues/385)) ([fa4f7b7](https://github.com/Aureliolo/synthorg/commit/fa4f7b76809c7b8c2c99c839b23994f87c7a60b5))
* bump node from 22-alpine to 25-alpine in /docker/web ([#359](https://github.com/Aureliolo/synthorg/issues/359)) ([8d56cd3](https://github.com/Aureliolo/synthorg/commit/8d56cd362ff1ce544d2be858751e504cace1b12c))
* bump node from 22-slim to 25-slim in /docker/sandbox ([#358](https://github.com/Aureliolo/synthorg/issues/358)) ([3de8748](https://github.com/Aureliolo/synthorg/commit/3de8748af5a77058f5d6f496a693b731f13b1490))
* bump pinia from 2.3.1 to 3.0.4 in /web ([#381](https://github.com/Aureliolo/synthorg/issues/381)) ([c78dcc2](https://github.com/Aureliolo/synthorg/commit/c78dcc2de57340836d504b836242c2e67497a7db))
* bump the major group across 1 directory with 9 updates ([#389](https://github.com/Aureliolo/synthorg/issues/389)) ([9fa621b](https://github.com/Aureliolo/synthorg/commit/9fa621bc33d78373608179b639108cb03dc83115))
* bump the minor-and-patch group with 2 updates ([#362](https://github.com/Aureliolo/synthorg/issues/362)) ([6ede2ce](https://github.com/Aureliolo/synthorg/commit/6ede2cee6fe97b39b37e37997b7cc102fd0f5994))
* bump vue-router from 4.6.4 to 5.0.3 in /web ([#378](https://github.com/Aureliolo/synthorg/issues/378)) ([6c60f6c](https://github.com/Aureliolo/synthorg/commit/6c60f6c822d7a975c012dc588041348f119e0744))
* expand review skills to 18 smart conditional agents ([#364](https://github.com/Aureliolo/synthorg/issues/364)) ([494013f](https://github.com/Aureliolo/synthorg/commit/494013feb1c6d4e7977c75cf4f42714bf1615bbd))

## [0.1.3](https://github.com/Aureliolo/synthorg/compare/v0.1.2...v0.1.3) (2026-03-13)


### Features

* add Mem0 memory backend adapter ([#345](https://github.com/Aureliolo/synthorg/issues/345)) ([2788db8](https://github.com/Aureliolo/synthorg/commit/2788db881f85a4e9e211b834b396943b3c588edf)), closes [#206](https://github.com/Aureliolo/synthorg/issues/206)
* centralized single-writer TaskEngine with full CRUD API ([#328](https://github.com/Aureliolo/synthorg/issues/328)) ([9c1a3e1](https://github.com/Aureliolo/synthorg/commit/9c1a3e150082ec4263148b4fcc71e5ba7c7a072d))
* incremental AgentEngine → TaskEngine status sync ([#331](https://github.com/Aureliolo/synthorg/issues/331)) ([7a68d34](https://github.com/Aureliolo/synthorg/commit/7a68d34a815efc20dbe409a597a93b9820b2227b)), closes [#323](https://github.com/Aureliolo/synthorg/issues/323)
* web dashboard pages — views, components, tests, and review fixes ([#354](https://github.com/Aureliolo/synthorg/issues/354)) ([b165ec4](https://github.com/Aureliolo/synthorg/commit/b165ec4d5d3e2a70852ef952a417fbcb053129c2))
* web dashboard with Vue 3 + PrimeVue + Tailwind CSS ([#347](https://github.com/Aureliolo/synthorg/issues/347)) ([06416b1](https://github.com/Aureliolo/synthorg/commit/06416b1d876528754db5a1363d5ebb58bde1bf2a))


### Bug Fixes

* harden coordination pipeline with validators, logging, and fail-fast ([#333](https://github.com/Aureliolo/synthorg/issues/333)) ([2f10d49](https://github.com/Aureliolo/synthorg/commit/2f10d495df099ba7d8eaaceb0cd717670fad7748)), closes [#205](https://github.com/Aureliolo/synthorg/issues/205)
* repo-wide security hardening from ZAP, Scorecard, and CodeQL audit ([#357](https://github.com/Aureliolo/synthorg/issues/357)) ([27eb288](https://github.com/Aureliolo/synthorg/commit/27eb28840ecffaa34a030e99d19add3af00a38f0))


### CI/CD

* add pip-audit, hadolint, OSSF Scorecard, ZAP DAST, and pre-push hooks ([#350](https://github.com/Aureliolo/synthorg/issues/350)) ([2802d20](https://github.com/Aureliolo/synthorg/commit/2802d20d16897582021b516fb3742495ff3fc30e))
* add workflow_dispatch trigger to PR Preview for Dependabot PRs ([#326](https://github.com/Aureliolo/synthorg/issues/326)) ([4c7b6d9](https://github.com/Aureliolo/synthorg/commit/4c7b6d935ef842ced3269ecad0a9e7b011adbf3b))
* bump astral-sh/setup-uv from 7.4.0 to 7.5.0 in the minor-and-patch group ([#335](https://github.com/Aureliolo/synthorg/issues/335)) ([98dd8ca](https://github.com/Aureliolo/synthorg/commit/98dd8caa30f60ad99e6cf46fa7d116db5e61a5b6))


### Maintenance

* bump the minor-and-patch group across 1 directory with 3 updates ([#352](https://github.com/Aureliolo/synthorg/issues/352)) ([031b1c9](https://github.com/Aureliolo/synthorg/commit/031b1c95fc069d38134e070d92ae121164e18233))
* **deps:** bump devalue from 5.6.3 to 5.6.4 in /site in the npm_and_yarn group across 1 directory ([#324](https://github.com/Aureliolo/synthorg/issues/324)) ([9a9c600](https://github.com/Aureliolo/synthorg/commit/9a9c600509d2d77c3487082521a8c3496cd3d6c1))
* migrate docs build from MkDocs to Zensical ([#330](https://github.com/Aureliolo/synthorg/issues/330)) ([fa8bf1d](https://github.com/Aureliolo/synthorg/commit/fa8bf1dfcc129e334d1b426dd5f9560aec0a6e81)), closes [#329](https://github.com/Aureliolo/synthorg/issues/329)

## [0.1.2](https://github.com/Aureliolo/synthorg/compare/v0.1.1...v0.1.2) (2026-03-12)


### Features

* add /review-dep-pr skill for dependency update PR review ([#315](https://github.com/Aureliolo/synthorg/issues/315)) ([56f6565](https://github.com/Aureliolo/synthorg/commit/56f6565d801ff47f2a86f09dfc3f2693472dc62b))
* add static OpenAPI reference page with Scalar UI ([#319](https://github.com/Aureliolo/synthorg/issues/319)) ([77cdbcc](https://github.com/Aureliolo/synthorg/commit/77cdbccb71fcb974665350b892b98fd8af43e635))


### Bug Fixes

* correct API reference link path in rest-api.md ([#320](https://github.com/Aureliolo/synthorg/issues/320)) ([3d08f92](https://github.com/Aureliolo/synthorg/commit/3d08f92278ba082b7ed44d8306b49151d8b0ebe2))


### CI/CD

* bump actions/setup-node from 4.4.0 to 6.3.0 ([#311](https://github.com/Aureliolo/synthorg/issues/311)) ([3c99d6f](https://github.com/Aureliolo/synthorg/commit/3c99d6fd9711d526e07304cf756968796026f821))
* bump actions/setup-python from 5.6.0 to 6.2.0 ([#312](https://github.com/Aureliolo/synthorg/issues/312)) ([3273553](https://github.com/Aureliolo/synthorg/commit/327355336046db5fa67bdca88fa6f3fba059aac0))
* bump astral-sh/setup-uv from 6.0.1 to 7.4.0 ([#310](https://github.com/Aureliolo/synthorg/issues/310)) ([b63cee7](https://github.com/Aureliolo/synthorg/commit/b63cee7fc5550da799161943b5ac25894aeeda7e))


### Maintenance

* bump mkdocstrings[python] from 0.29.1 to 1.0.3 ([#314](https://github.com/Aureliolo/synthorg/issues/314)) ([d46ccad](https://github.com/Aureliolo/synthorg/commit/d46ccadda5b8db00b2f7e848a6e678a56f6972ff))
* bump the minor-and-patch group with 2 updates ([#313](https://github.com/Aureliolo/synthorg/issues/313)) ([6337ae4](https://github.com/Aureliolo/synthorg/commit/6337ae4b90e52d869db8ba253dce59c2c3387ca1))
* improve review-dep-pr skill and add Codecov Test Analytics ([#317](https://github.com/Aureliolo/synthorg/issues/317)) ([eb5782e](https://github.com/Aureliolo/synthorg/commit/eb5782ee31749a3926a0262bc8bce4e8cd303413))

## [0.1.1](https://github.com/Aureliolo/synthorg/compare/v0.1.0...v0.1.1) (2026-03-11)


### Features

* add PR preview deployments via Cloudflare Pages ([#302](https://github.com/Aureliolo/synthorg/issues/302)) ([b73c45a](https://github.com/Aureliolo/synthorg/commit/b73c45a806d3edc5f541263485cf9e922748ea17))


### Bug Fixes

* correct deploy-pages SHA and improve preview cleanup reliability ([#304](https://github.com/Aureliolo/synthorg/issues/304)) ([584d64a](https://github.com/Aureliolo/synthorg/commit/584d64a1f564a7ad75ad3ffaa9a44eabf788a707))
* harden API key hashing with HMAC-SHA256 and clean up legacy changelog ([#292](https://github.com/Aureliolo/synthorg/issues/292)) ([5e85353](https://github.com/Aureliolo/synthorg/commit/5e85353c29b1748fb16034f2d9f92166fb5c0908))
* upgrade upload-pages-artifact to v4 and add zizmor workflow linting ([#299](https://github.com/Aureliolo/synthorg/issues/299)) ([2eac571](https://github.com/Aureliolo/synthorg/commit/2eac571bc44273ff99a2e10448859561b90328f3))
* use Cloudflare Pages API default per_page for pagination ([#305](https://github.com/Aureliolo/synthorg/issues/305)) ([9fec245](https://github.com/Aureliolo/synthorg/commit/9fec245e202ce58df4327ffd2055e501e53551a3))


### Documentation

* remove milestone references and rebrand to SynthOrg ([#289](https://github.com/Aureliolo/synthorg/issues/289)) ([57a03e0](https://github.com/Aureliolo/synthorg/commit/57a03e0193f17ca1b9f0064841201ded33eb70ea))
* set up documentation site, release CI, and sandbox hardening ([#298](https://github.com/Aureliolo/synthorg/issues/298)) ([0dec9da](https://github.com/Aureliolo/synthorg/commit/0dec9da5ce88aa212a1b74d99340497f3d4bd843))
* split DESIGN_SPEC.md into 7 focused design pages ([#308](https://github.com/Aureliolo/synthorg/issues/308)) ([9ea0788](https://github.com/Aureliolo/synthorg/commit/9ea078818cace13729adf27647a75d800571069c))

## [0.1.0](https://github.com/Aureliolo/synthorg/compare/v0.0.0...v0.1.0) (2026-03-11)


### Features

* add autonomy levels and approval timeout policies ([#42](https://github.com/Aureliolo/synthorg/issues/42), [#126](https://github.com/Aureliolo/synthorg/issues/126)) ([#197](https://github.com/Aureliolo/synthorg/issues/197)) ([eecc25a](https://github.com/Aureliolo/synthorg/commit/eecc25a1177f15101d02fb3dc7b95f3d9c023279))
* add CFO cost optimization service with anomaly detection, reports, and approval decisions ([#186](https://github.com/Aureliolo/synthorg/issues/186)) ([a7fa00b](https://github.com/Aureliolo/synthorg/commit/a7fa00bf9ef113b02aa8ef4bc13ddcb8c61ea972))
* add code quality toolchain (ruff, mypy, pre-commit, dependabot) ([#63](https://github.com/Aureliolo/synthorg/issues/63)) ([36681a8](https://github.com/Aureliolo/synthorg/commit/36681a8c44d31a2c6e9acc3f55eea7d108c3c36c))
* add configurable cost tiers and subscription/quota-aware tracking ([#67](https://github.com/Aureliolo/synthorg/issues/67)) ([#185](https://github.com/Aureliolo/synthorg/issues/185)) ([9baedfa](https://github.com/Aureliolo/synthorg/commit/9baedfa5c134c9803065b5c7cd524ff03c66ce4f))
* add container packaging, Docker Compose, and CI pipeline ([#269](https://github.com/Aureliolo/synthorg/issues/269)) ([435bdfe](https://github.com/Aureliolo/synthorg/commit/435bdfed1e7a5df5767ff31d991021bf3dfd3e12)), closes [#267](https://github.com/Aureliolo/synthorg/issues/267)
* add coordination error taxonomy classification pipeline ([#146](https://github.com/Aureliolo/synthorg/issues/146)) ([#181](https://github.com/Aureliolo/synthorg/issues/181)) ([70c7480](https://github.com/Aureliolo/synthorg/commit/70c748010325824f44f77a798e48241f4703ee0a))
* add cost-optimized, hierarchical, and auction assignment strategies ([#175](https://github.com/Aureliolo/synthorg/issues/175)) ([ce924fa](https://github.com/Aureliolo/synthorg/commit/ce924faba2fdb10ab430c35f530a750cfd709b30)), closes [#173](https://github.com/Aureliolo/synthorg/issues/173)
* add design specification, license, and project setup ([8669a09](https://github.com/Aureliolo/synthorg/commit/8669a0947d92647bc6a7d7be2a5b334710e5808a))
* add env var substitution and config file auto-discovery ([#77](https://github.com/Aureliolo/synthorg/issues/77)) ([7f53832](https://github.com/Aureliolo/synthorg/commit/7f53832f9c62210658e91a0e2cf980332deea603))
* add FastestStrategy routing + vendor-agnostic cleanup ([#140](https://github.com/Aureliolo/synthorg/issues/140)) ([09619cb](https://github.com/Aureliolo/synthorg/commit/09619cb7dc8f7e6bacd5ec4b6beb1b0ca8475149)), closes [#139](https://github.com/Aureliolo/synthorg/issues/139)
* add HR engine and performance tracking ([#45](https://github.com/Aureliolo/synthorg/issues/45), [#47](https://github.com/Aureliolo/synthorg/issues/47)) ([#193](https://github.com/Aureliolo/synthorg/issues/193)) ([2d091ea](https://github.com/Aureliolo/synthorg/commit/2d091eaef9219ff68520b65e6427bcf2ec025fc5))
* add issue auto-search and resolution verification to PR review skill ([#119](https://github.com/Aureliolo/synthorg/issues/119)) ([deecc39](https://github.com/Aureliolo/synthorg/commit/deecc394c7a90ffc1c69f31eb5c170ebd0cf3250))
* add mandatory JWT + API key authentication ([#256](https://github.com/Aureliolo/synthorg/issues/256)) ([c279cfe](https://github.com/Aureliolo/synthorg/commit/c279cfe9527ee74d97a97634c5beb193f3331320))
* add memory retrieval, ranking, and context injection pipeline ([#41](https://github.com/Aureliolo/synthorg/issues/41)) ([873b0aa](https://github.com/Aureliolo/synthorg/commit/873b0aaf838ff06e2c2c1bf9785c83447228d81e))
* add pluggable MemoryBackend protocol with models, config, and events ([#180](https://github.com/Aureliolo/synthorg/issues/180)) ([46cfdd4](https://github.com/Aureliolo/synthorg/commit/46cfdd423aadf2f5f22b3f13c98313855bfbc26f))
* add pluggable MemoryBackend protocol with models, config, and events ([#32](https://github.com/Aureliolo/synthorg/issues/32)) ([46cfdd4](https://github.com/Aureliolo/synthorg/commit/46cfdd423aadf2f5f22b3f13c98313855bfbc26f))
* add pluggable output scan response policies ([#263](https://github.com/Aureliolo/synthorg/issues/263)) ([b9907e8](https://github.com/Aureliolo/synthorg/commit/b9907e8d77546b4a7a4bb1a31094975fc583be7d))
* add pluggable PersistenceBackend protocol with SQLite implementation ([#36](https://github.com/Aureliolo/synthorg/issues/36)) ([f753779](https://github.com/Aureliolo/synthorg/commit/f753779bd5628d12ade34d4250db7a768de9a975))
* add progressive trust and promotion/demotion subsystems ([#43](https://github.com/Aureliolo/synthorg/issues/43), [#49](https://github.com/Aureliolo/synthorg/issues/49)) ([3a87c08](https://github.com/Aureliolo/synthorg/commit/3a87c0836ea95290eafa42ce4cfec4564c1cd36a))
* add retry handler, rate limiter, and provider resilience ([#100](https://github.com/Aureliolo/synthorg/issues/100)) ([b890545](https://github.com/Aureliolo/synthorg/commit/b8905453fa51a2ca60ffa05f6c4d3598e1d11bc7))
* add SecOps security agent with rule engine, audit log, and ToolInvoker integration ([#40](https://github.com/Aureliolo/synthorg/issues/40)) ([83b7b6c](https://github.com/Aureliolo/synthorg/commit/83b7b6cd062f16353b19ad0ab8ad41b2d951ac16))
* add shared org memory and memory consolidation/archival ([#125](https://github.com/Aureliolo/synthorg/issues/125), [#48](https://github.com/Aureliolo/synthorg/issues/48)) ([4a0832b](https://github.com/Aureliolo/synthorg/commit/4a0832b10194232a133c61b6dd6fb12fc579f951))
* design unified provider interface ([#86](https://github.com/Aureliolo/synthorg/issues/86)) ([3e23d64](https://github.com/Aureliolo/synthorg/commit/3e23d6422b2bd76979ad01af65876bc95928bdcc))
* expand template presets, rosters, and add inheritance ([#80](https://github.com/Aureliolo/synthorg/issues/80), [#81](https://github.com/Aureliolo/synthorg/issues/81), [#84](https://github.com/Aureliolo/synthorg/issues/84)) ([15a9134](https://github.com/Aureliolo/synthorg/commit/15a91349d7e0305d0d33c9de8eb283fdd2184442))
* implement agent runtime state vs immutable config split ([#115](https://github.com/Aureliolo/synthorg/issues/115)) ([4cb1ca5](https://github.com/Aureliolo/synthorg/commit/4cb1ca541ccfa5bea44e4b197eedc24e79179c21))
* implement AgentEngine core orchestrator ([#11](https://github.com/Aureliolo/synthorg/issues/11)) ([#143](https://github.com/Aureliolo/synthorg/issues/143)) ([f2eb73a](https://github.com/Aureliolo/synthorg/commit/f2eb73a1c1864c844b547caf71890354f6031a69))
* implement AuditRepository for security audit log persistence ([#279](https://github.com/Aureliolo/synthorg/issues/279)) ([94bc29f](https://github.com/Aureliolo/synthorg/commit/94bc29fbf745576da51b8b942faf7aa0047dbe9a))
* implement basic tool system (registry, invocation, results) ([#15](https://github.com/Aureliolo/synthorg/issues/15)) ([c51068b](https://github.com/Aureliolo/synthorg/commit/c51068b11de77fb15699c203840651044ab482fa))
* implement built-in file system tools ([#18](https://github.com/Aureliolo/synthorg/issues/18)) ([325ef98](https://github.com/Aureliolo/synthorg/commit/325ef988c2c5312215c7eaf20401d904863c049d))
* implement communication foundation — message bus, dispatcher, and messenger ([#157](https://github.com/Aureliolo/synthorg/issues/157)) ([8e71bfd](https://github.com/Aureliolo/synthorg/commit/8e71bfd0e3cf84dd36c48f17b933d0554c6f932e))
* implement company template system with 7 built-in presets ([#85](https://github.com/Aureliolo/synthorg/issues/85)) ([cbf1496](https://github.com/Aureliolo/synthorg/commit/cbf14963be4547749d493e1ba5cc40d75c67a6c5))
* implement conflict resolution protocol ([#122](https://github.com/Aureliolo/synthorg/issues/122)) ([#166](https://github.com/Aureliolo/synthorg/issues/166)) ([e03f9f2](https://github.com/Aureliolo/synthorg/commit/e03f9f2e09c0493d5ca51a98d83481bd828b9113))
* implement core entity and role system models ([#69](https://github.com/Aureliolo/synthorg/issues/69)) ([acf9801](https://github.com/Aureliolo/synthorg/commit/acf9801f4b68b1538c07329d9d61771267978bce))
* implement crash recovery with fail-and-reassign strategy ([#149](https://github.com/Aureliolo/synthorg/issues/149)) ([e6e91ed](https://github.com/Aureliolo/synthorg/commit/e6e91ed3dd19397c3d9d456bbdd8cc2fd8c1cfac))
* implement engine extensions — Plan-and-Execute loop and call categorization ([#134](https://github.com/Aureliolo/synthorg/issues/134), [#135](https://github.com/Aureliolo/synthorg/issues/135)) ([#159](https://github.com/Aureliolo/synthorg/issues/159)) ([9b2699f](https://github.com/Aureliolo/synthorg/commit/9b2699f3b9b1b07912a6a09e0cd21644f432d744))
* implement enterprise logging system with structlog ([#73](https://github.com/Aureliolo/synthorg/issues/73)) ([2f787e5](https://github.com/Aureliolo/synthorg/commit/2f787e5b2576a0403f6b86c9daa16dfbbfd2e243))
* implement graceful shutdown with cooperative timeout strategy ([#130](https://github.com/Aureliolo/synthorg/issues/130)) ([6592515](https://github.com/Aureliolo/synthorg/commit/6592515617742851c1d355422ac40266af3b5127))
* implement hierarchical delegation and loop prevention ([#12](https://github.com/Aureliolo/synthorg/issues/12), [#17](https://github.com/Aureliolo/synthorg/issues/17)) ([6be60b6](https://github.com/Aureliolo/synthorg/commit/6be60b65dd6cac4f61a023b274353325e1690eae))
* implement LiteLLM driver and provider registry ([#88](https://github.com/Aureliolo/synthorg/issues/88)) ([ae3f18b](https://github.com/Aureliolo/synthorg/commit/ae3f18b22ca81e99fea84c9f0ccbab8da1ee5605)), closes [#4](https://github.com/Aureliolo/synthorg/issues/4)
* implement LLM decomposition strategy and workspace isolation ([#174](https://github.com/Aureliolo/synthorg/issues/174)) ([aa0eefe](https://github.com/Aureliolo/synthorg/commit/aa0eefe2a1ef3d945adea10979fd4eea45c8c1d7))
* implement meeting protocol system ([#123](https://github.com/Aureliolo/synthorg/issues/123)) ([ee7caca](https://github.com/Aureliolo/synthorg/commit/ee7cacacad859427c7a2a67f4ce5e72046b15b1b))
* implement message and communication domain models ([#74](https://github.com/Aureliolo/synthorg/issues/74)) ([560a5d2](https://github.com/Aureliolo/synthorg/commit/560a5d2e29625aeae080babeed1ddb4195dc3743))
* implement model routing engine ([#99](https://github.com/Aureliolo/synthorg/issues/99)) ([d3c250b](https://github.com/Aureliolo/synthorg/commit/d3c250b8f341fcf0fece7373c1b295e05f83721c))
* implement parallel agent execution ([#22](https://github.com/Aureliolo/synthorg/issues/22)) ([#161](https://github.com/Aureliolo/synthorg/issues/161)) ([65940b3](https://github.com/Aureliolo/synthorg/commit/65940b3f5bb10692d257fbfda6f4bc692db8aab4))
* implement per-call cost tracking service ([#7](https://github.com/Aureliolo/synthorg/issues/7)) ([#102](https://github.com/Aureliolo/synthorg/issues/102)) ([c4f1f1c](https://github.com/Aureliolo/synthorg/commit/c4f1f1c9952991fbccc3a44dd4c4b2e65cdd9033))
* implement personality injection and system prompt construction ([#105](https://github.com/Aureliolo/synthorg/issues/105)) ([934dd85](https://github.com/Aureliolo/synthorg/commit/934dd85c499a922496392865cf35edb1e75166bd))
* implement single-task execution lifecycle ([#21](https://github.com/Aureliolo/synthorg/issues/21)) ([#144](https://github.com/Aureliolo/synthorg/issues/144)) ([c7e64e4](https://github.com/Aureliolo/synthorg/commit/c7e64e46f85dbd8d2b8b01aad7babd3a00f78bdb))
* implement subprocess sandbox for tool execution isolation ([#131](https://github.com/Aureliolo/synthorg/issues/131)) ([#153](https://github.com/Aureliolo/synthorg/issues/153)) ([3c8394e](https://github.com/Aureliolo/synthorg/commit/3c8394e905b914de1c81b5d7ed1544920cfb1411))
* implement task assignment subsystem with pluggable strategies ([#172](https://github.com/Aureliolo/synthorg/issues/172)) ([c7f1b26](https://github.com/Aureliolo/synthorg/commit/c7f1b2628e37821f01605a206d5f36d5ec6f6c95)), closes [#26](https://github.com/Aureliolo/synthorg/issues/26) [#30](https://github.com/Aureliolo/synthorg/issues/30)
* implement task decomposition and routing engine ([#14](https://github.com/Aureliolo/synthorg/issues/14)) ([9c7fb52](https://github.com/Aureliolo/synthorg/commit/9c7fb526e7a469b8fd4a1ee106670b292a24879a))
* implement Task, Project, Artifact, Budget, and Cost domain models ([#71](https://github.com/Aureliolo/synthorg/issues/71)) ([81eabf1](https://github.com/Aureliolo/synthorg/commit/81eabf1042d30ab67a6e1c0976d0da58b78a9ab9))
* implement tool permission checking ([#16](https://github.com/Aureliolo/synthorg/issues/16)) ([833c190](https://github.com/Aureliolo/synthorg/commit/833c190de2d886ca5cb516341d50e4fb86bc6879))
* implement YAML config loader with Pydantic validation ([#59](https://github.com/Aureliolo/synthorg/issues/59)) ([ff3a2ba](https://github.com/Aureliolo/synthorg/commit/ff3a2ba973f915d8d7f71311188d71d1e461285d))
* implement YAML config loader with Pydantic validation ([#75](https://github.com/Aureliolo/synthorg/issues/75)) ([ff3a2ba](https://github.com/Aureliolo/synthorg/commit/ff3a2ba973f915d8d7f71311188d71d1e461285d))
* initialize project with uv, hatchling, and src layout ([39005f9](https://github.com/Aureliolo/synthorg/commit/39005f96bc665123fa25ce55121ae8fe25bc8cc3))
* initialize project with uv, hatchling, and src layout ([#62](https://github.com/Aureliolo/synthorg/issues/62)) ([39005f9](https://github.com/Aureliolo/synthorg/commit/39005f96bc665123fa25ce55121ae8fe25bc8cc3))
* Litestar REST API, WebSocket feed, and approval queue (M6) ([#189](https://github.com/Aureliolo/synthorg/issues/189)) ([29fcd08](https://github.com/Aureliolo/synthorg/commit/29fcd0851a4790fe9d25626a3d26890ca41908c6))
* make TokenUsage.total_tokens a computed field ([#118](https://github.com/Aureliolo/synthorg/issues/118)) ([c0bab18](https://github.com/Aureliolo/synthorg/commit/c0bab18e51c6bce227eec7ba112ba3178bd847d1)), closes [#109](https://github.com/Aureliolo/synthorg/issues/109)
* parallel tool execution in ToolInvoker.invoke_all ([#137](https://github.com/Aureliolo/synthorg/issues/137)) ([58517ee](https://github.com/Aureliolo/synthorg/commit/58517ee64a36d764142790640dfb996c9ff75100))
* testing framework, CI pipeline, and M0 gap fixes ([#64](https://github.com/Aureliolo/synthorg/issues/64)) ([f581749](https://github.com/Aureliolo/synthorg/commit/f581749ae57cb46f4fc687ab0d1f22a492593b64))
* wire all modules into observability system ([#97](https://github.com/Aureliolo/synthorg/issues/97)) ([f7a0617](https://github.com/Aureliolo/synthorg/commit/f7a0617a2659dcdc6d33447801623a879cf4c60c))


### Bug Fixes

* address Greptile post-merge review findings from PRs [#170](https://github.com/Aureliolo/synthorg/issues/170)-[#175](https://github.com/Aureliolo/synthorg/issues/175) ([#176](https://github.com/Aureliolo/synthorg/issues/176)) ([c5ca929](https://github.com/Aureliolo/synthorg/commit/c5ca92933a0cbe4b1943528150a22c529fa44f3f))
* address post-merge review feedback from PRs [#164](https://github.com/Aureliolo/synthorg/issues/164)-[#167](https://github.com/Aureliolo/synthorg/issues/167) ([#170](https://github.com/Aureliolo/synthorg/issues/170)) ([3bf897a](https://github.com/Aureliolo/synthorg/commit/3bf897a6ffde53bc940b2a993e0206d1d0bf2747)), closes [#169](https://github.com/Aureliolo/synthorg/issues/169)
* enforce strict mypy on test files ([#89](https://github.com/Aureliolo/synthorg/issues/89)) ([aeeff8c](https://github.com/Aureliolo/synthorg/commit/aeeff8ca16fdae92ec1b8fc6c8c1bc6161b64e79))
* harden Docker sandbox, MCP bridge, and code runner ([#50](https://github.com/Aureliolo/synthorg/issues/50), [#53](https://github.com/Aureliolo/synthorg/issues/53)) ([d5e1b6e](https://github.com/Aureliolo/synthorg/commit/d5e1b6ee1915bfb4c3342abd0d0e7aa79b9a1f20))
* harden git tools security + code quality improvements ([#150](https://github.com/Aureliolo/synthorg/issues/150)) ([000a325](https://github.com/Aureliolo/synthorg/commit/000a325a8a39db623d6ad397ad1d3f922e75e49e))
* harden subprocess cleanup, env filtering, and shutdown resilience ([#155](https://github.com/Aureliolo/synthorg/issues/155)) ([d1fe1fb](https://github.com/Aureliolo/synthorg/commit/d1fe1fbec2a50980efbc162e4662c373e2d166a3))
* incorporate post-merge feedback + pre-PR review fixes ([#164](https://github.com/Aureliolo/synthorg/issues/164)) ([c02832a](https://github.com/Aureliolo/synthorg/commit/c02832ac4d67aee9a19adcb4d713342f7f5bc45e))
* pre-PR review fixes for post-merge findings ([#183](https://github.com/Aureliolo/synthorg/issues/183)) ([26b3108](https://github.com/Aureliolo/synthorg/commit/26b31085e527a477bf2ebbc800929d0da743c6b2))
* resolve circular imports, bump litellm, fix release tag format ([#286](https://github.com/Aureliolo/synthorg/issues/286)) ([a6659b5](https://github.com/Aureliolo/synthorg/commit/a6659b5deb7c5f9f4a86e20e3a8728a200f3a885))
* strengthen immutability for BaseTool schema and ToolInvoker boundaries ([#117](https://github.com/Aureliolo/synthorg/issues/117)) ([7e5e861](https://github.com/Aureliolo/synthorg/commit/7e5e86189cf0229106911f4ba0f1238414edb401))


### Performance

* harden non-inferable principle implementation ([#195](https://github.com/Aureliolo/synthorg/issues/195)) ([02b5f4e](https://github.com/Aureliolo/synthorg/commit/02b5f4e742288fd644212c804395cd751d9ffc27)), closes [#188](https://github.com/Aureliolo/synthorg/issues/188)


### Refactoring

* adopt NotBlankStr across all models ([#108](https://github.com/Aureliolo/synthorg/issues/108)) ([#120](https://github.com/Aureliolo/synthorg/issues/120)) ([ef89b90](https://github.com/Aureliolo/synthorg/commit/ef89b901a86ca795ef1b58fd82c3950dbfd5b0f1))
* extract _SpendingTotals base class from spending summary models ([#111](https://github.com/Aureliolo/synthorg/issues/111)) ([2f39c1b](https://github.com/Aureliolo/synthorg/commit/2f39c1baf0de8c72911925c93ec94dc193d06916))
* harden BudgetEnforcer with error handling, validation extraction, and review fixes ([#182](https://github.com/Aureliolo/synthorg/issues/182)) ([c107bf9](https://github.com/Aureliolo/synthorg/commit/c107bf9986b54482d76f4495c9eb199e1e132f8a))
* harden personality profiles, department validation, and template rendering ([#158](https://github.com/Aureliolo/synthorg/issues/158)) ([10b2299](https://github.com/Aureliolo/synthorg/commit/10b2299989562e05868913ed90aec7e123b4dbf2))
* pre-PR review improvements for ExecutionLoop + ReAct loop ([#124](https://github.com/Aureliolo/synthorg/issues/124)) ([8dfb3c0](https://github.com/Aureliolo/synthorg/commit/8dfb3c0609ac2e9a7c3582fe7c515757f6cb6aa9))
* split events.py into per-domain event modules ([#136](https://github.com/Aureliolo/synthorg/issues/136)) ([e9cba89](https://github.com/Aureliolo/synthorg/commit/e9cba896aeb33925bba7c507fcd90729cb20f294))


### Documentation

* add ADR-001 memory layer evaluation and selection ([#178](https://github.com/Aureliolo/synthorg/issues/178)) ([db3026f](https://github.com/Aureliolo/synthorg/commit/db3026f41ea974bb85992cabb0cec722cba42f85)), closes [#39](https://github.com/Aureliolo/synthorg/issues/39)
* add agent scaling research findings to DESIGN_SPEC ([#145](https://github.com/Aureliolo/synthorg/issues/145)) ([57e487b](https://github.com/Aureliolo/synthorg/commit/57e487b1e029205cf6f733faefc50a29005b6b71))
* add CLAUDE.md, contributing guide, and dev documentation ([#65](https://github.com/Aureliolo/synthorg/issues/65)) ([55c1025](https://github.com/Aureliolo/synthorg/commit/55c102594428425882193afb80107120c93981e3)), closes [#54](https://github.com/Aureliolo/synthorg/issues/54)
* add crash recovery, sandboxing, analytics, and testing decisions ([#127](https://github.com/Aureliolo/synthorg/issues/127)) ([5c11595](https://github.com/Aureliolo/synthorg/commit/5c11595c87e61f72b0ffbfc004f9cf1c4639faf4))
* address external review feedback with MVP scope and new protocols ([#128](https://github.com/Aureliolo/synthorg/issues/128)) ([3b30b9a](https://github.com/Aureliolo/synthorg/commit/3b30b9a986a1f977092d5821e65189ed896cb63f))
* expand design spec with pluggable strategy protocols ([#121](https://github.com/Aureliolo/synthorg/issues/121)) ([6832db6](https://github.com/Aureliolo/synthorg/commit/6832db6e0d8a8295b2b1baf350e02c3f85d95cdd))
* finalize 23 design decisions (ADR-002) ([#190](https://github.com/Aureliolo/synthorg/issues/190)) ([8c39742](https://github.com/Aureliolo/synthorg/commit/8c39742b23404dc583d87ffa4611825521fb1bfc))
* update project docs for M2.5 conventions and add docs-consistency review agent ([#114](https://github.com/Aureliolo/synthorg/issues/114)) ([99766ee](https://github.com/Aureliolo/synthorg/commit/99766eee6ed9b0354cfa4d7e8dba7a6846299a74))


### Tests

* add e2e single agent integration tests ([#24](https://github.com/Aureliolo/synthorg/issues/24)) ([#156](https://github.com/Aureliolo/synthorg/issues/156)) ([f566fb4](https://github.com/Aureliolo/synthorg/commit/f566fb4bf469e119c434691c22f8894e49609a83))
* add provider adapter integration tests ([#90](https://github.com/Aureliolo/synthorg/issues/90)) ([40a61f4](https://github.com/Aureliolo/synthorg/commit/40a61f48a309d2b08797d1c840ce1d946d255d88))


### CI/CD

* add Release Please for automated versioning and GitHub Releases ([#278](https://github.com/Aureliolo/synthorg/issues/278)) ([a488758](https://github.com/Aureliolo/synthorg/commit/a4887580a2262bfd84e76c861f0106a13a438fd0))
* bump actions/checkout from 4 to 6 ([#95](https://github.com/Aureliolo/synthorg/issues/95)) ([1897247](https://github.com/Aureliolo/synthorg/commit/1897247a8bd561715639bf6dac4b136ccace7d75))
* bump actions/upload-artifact from 4 to 7 ([#94](https://github.com/Aureliolo/synthorg/issues/94)) ([27b1517](https://github.com/Aureliolo/synthorg/commit/27b15177b49357e2d9c051202b97487645cd8da5))
* bump anchore/scan-action from 6.5.1 to 7.3.2 ([#271](https://github.com/Aureliolo/synthorg/issues/271)) ([80a1c15](https://github.com/Aureliolo/synthorg/commit/80a1c157c69031d2d18beca6511edf5031e8595b))
* bump docker/build-push-action from 6.19.2 to 7.0.0 ([#273](https://github.com/Aureliolo/synthorg/issues/273)) ([dd0219e](https://github.com/Aureliolo/synthorg/commit/dd0219e27d3142cfe697f0f51beff71ad14e6c17))
* bump docker/login-action from 3.7.0 to 4.0.0 ([#272](https://github.com/Aureliolo/synthorg/issues/272)) ([33d6238](https://github.com/Aureliolo/synthorg/commit/33d6238d7d62a7c7c4902aa6a0f0108e66c7c7fc))
* bump docker/metadata-action from 5.10.0 to 6.0.0 ([#270](https://github.com/Aureliolo/synthorg/issues/270)) ([baee04e](https://github.com/Aureliolo/synthorg/commit/baee04e81d5664317a4835a0cec315316b47d6b7))
* bump docker/setup-buildx-action from 3.12.0 to 4.0.0 ([#274](https://github.com/Aureliolo/synthorg/issues/274)) ([5fc06f7](https://github.com/Aureliolo/synthorg/commit/5fc06f72c4d067cf0ea157f469e9bc0214cfc6ca))
* bump sigstore/cosign-installer from 3.9.1 to 4.1.0 ([#275](https://github.com/Aureliolo/synthorg/issues/275)) ([29dd16c](https://github.com/Aureliolo/synthorg/commit/29dd16c37ae148ff509d19627a9e884160292263))
* harden CI/CD pipeline ([#92](https://github.com/Aureliolo/synthorg/issues/92)) ([ce4693c](https://github.com/Aureliolo/synthorg/commit/ce4693ce859128e90c67beb519291ef7b4acf77e))
* split vulnerability scans into critical-fail and high-warn tiers ([#277](https://github.com/Aureliolo/synthorg/issues/277)) ([aba48af](https://github.com/Aureliolo/synthorg/commit/aba48af9d522b2d9d621955984b34abf47d6097a))


### Maintenance

* add /worktree skill for parallel worktree management ([#171](https://github.com/Aureliolo/synthorg/issues/171)) ([951e337](https://github.com/Aureliolo/synthorg/commit/951e337ce002e4756bc647d0710f483164a3d338))
* add design spec context loading to research-link skill ([8ef9685](https://github.com/Aureliolo/synthorg/commit/8ef9685f7fe5164768f206fae68970ba79f4c53f))
* add post-merge-cleanup skill ([#70](https://github.com/Aureliolo/synthorg/issues/70)) ([f913705](https://github.com/Aureliolo/synthorg/commit/f913705d04be847991854361ae1f0725623e4841))
* add pre-pr-review skill and update CLAUDE.md ([#103](https://github.com/Aureliolo/synthorg/issues/103)) ([92e9023](https://github.com/Aureliolo/synthorg/commit/92e9023c879384bb3c09cbcef0048f0a118fdcfe))
* add research-link skill and rename skill files to SKILL.md ([#101](https://github.com/Aureliolo/synthorg/issues/101)) ([651c577](https://github.com/Aureliolo/synthorg/commit/651c57772aa4f2696a41baa6ad89788e71be1f8c))
* bump aiosqlite from 0.21.0 to 0.22.1 ([#191](https://github.com/Aureliolo/synthorg/issues/191)) ([3274a86](https://github.com/Aureliolo/synthorg/commit/3274a8642e375fa0e51a215bcdf473fcf78c6515))
* bump pyyaml from 6.0.2 to 6.0.3 in the minor-and-patch group ([#96](https://github.com/Aureliolo/synthorg/issues/96)) ([0338d0c](https://github.com/Aureliolo/synthorg/commit/0338d0c42da16a0366b25c9b860d709ea5e3cc61))
* bump ruff from 0.15.4 to 0.15.5 ([a49ee46](https://github.com/Aureliolo/synthorg/commit/a49ee464ac475f3780c24902b5331509d0fb8562))
* fix M0 audit items ([#66](https://github.com/Aureliolo/synthorg/issues/66)) ([c7724b5](https://github.com/Aureliolo/synthorg/commit/c7724b55321a7d2d6b67523f95cfe43cce00f143))
* pin setup-uv action to full SHA ([#281](https://github.com/Aureliolo/synthorg/issues/281)) ([4448002](https://github.com/Aureliolo/synthorg/commit/44480022aa613f7898897a74c376b33b0dc41435))
* post-audit cleanup — PEP 758, loggers, bug fixes, refactoring, tests, hookify rules ([#148](https://github.com/Aureliolo/synthorg/issues/148)) ([c57a6a9](https://github.com/Aureliolo/synthorg/commit/c57a6a9e619ba3339d58df221edf332998a0d1d2))
