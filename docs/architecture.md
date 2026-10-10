# Unified Scam Intelligence Platform: Complete Architecture (Text + Voice)

Text channel (ScamRoom) + recorded voice (Raksham) + live call (Voice Scam Shield) + adaptive action layer (Part 04) + Cline integration

Prepared 10 Oct 2026. Status: design document. No validated results are claimed anywhere in it.

Source documents merged: ScamRoom v5 overview; Raksham approach and Cline engineering plan; Voice Scam Shield end-to-end plan; Voice-clone preprocessing and Cline integration guide; Raksham Part 04 contextual-bandit master prompt.

## 1. Purpose, scope and principles

### 1.1 What the platform does

Given a communication stream, the platform produces risk evidence: per-signal scores with stated semantics, flagged messages or time intervals, a scam-type guess, a plain-language explanation and an action tier. Humans make the final call. The platform never accuses a person, never proves identity or liveness, and never blocks anything automatically on a model score.

| Channel | Input | Timing | Origin |
| --- | --- | --- | --- |
| T: text chat | Streaming messages (SMS, chat apps, exports) | p95 <= 50 ms per message, CPU only | ScamRoom v5 |
| V1: recorded voice | Call recording or voice note (authorized) | Offline, seconds to minutes | Raksham Parts 01-03 |
| V2: live call | Transcript chunks (10-15 s) plus parallel audio | Seconds, continuous | Voice Scam Shield |

### 1.2 Non-goals

- Months-long pig-butchering and expert slow-burn scams.
- Tapping native carrier calls. Live demo runs through a browser call simulator or WebRTC; telephony integration is roadmap.
- Speaker identity verification, liveness proof, deepfake video, kidnapping-ransom and stolen-phone cases.
- Using a detector score as a fraud verdict, or retraining detectors from the feedback loop automatically.

### 1.3 Design principles (apply to every layer)

1. **Three concepts are never conflated:** synthetic voice, suspicious content, confirmed fraud. A genuine voice can deliver a scam; a cloned voice can say something harmless.
2. **Evidence, not verdicts.** Outputs are risk indicators with reasons, never 'this person is a scammer'.
3. **Missing is neither safe nor risky.** A lookup timeout is 'unknown', a missing signal is masked or renormalized under a documented policy, poor formant quality is never spoof evidence. A live call that ends below threshold is logged as 'no alert raised', not 'verified safe'.
4. **Deterministic decisions live in the backend.** LLMs (Cline API) return structured signals; code computes scores, hysteresis and alert state.
5. **Priors, never gates.** Reputation, graph, trust badge, Truecaller and trending-scam patterns shift priors or thresholds; none can suppress analysis permanently.
6. **Calibrate before calling anything a probability.** Uncalibrated outputs are labelled 'model score'. Raw logits from different models are never compared.
7. **Privacy by minimization.** On-device first, salted hashes, no raw audio or full transcripts in logs, retention and deletion documented.
8. **Traceability.** Every number in a report or submission traces to a saved experiment with split, seed, model version and date.
9. **Everything is flag-gated and ablatable,** so a module that fails to earn its place can be dropped.
10. **Safety constraints are enforced outside any learned policy.** The bandit cannot override them.

## 2. System at a glance

### 2.1 Layered view

```
SOURCES
 chat apps / SMS / notifications / exports | recorded call or voice note | live call (WebRTC / simulator)
        |                                        |                              |
L0  INGESTION ADAPTERS -> canonical events (message, edit, delete, member_join, profile_change,
        |                  call_event, media, audio_asset, transcript_chunk) + capability flags
        |                                        |                              |
   TEXT PIPELINE (T)                  RECORDED VOICE (V1)             LIVE CALL (V2)
   Stage 1: normalize, lexicon,       validate, 16 kHz mono, VAD,     STT -> 10-15 s chunks
     encoder, MinHash/SimHash,        quality metadata, windows       pre-call signals (caller no.,
     entity enrichment                Branch A: AASIST                  Truecaller hint, user context)
   Stage 2: Room 1, Room 2, GNN,      Branch B: formants + LR         RAG scam patterns + lookalikes
     Trust Badge, router, assembler   calibration + fusion            Cline API analyser -> signals
   Stage 3: small SLM                 interval detection              call risk engine + hysteresis
                                      STT + content signals           voice-authenticity badge
        |                                        |                              |
        +--------------- SIGNAL BUS (unified Signal schema) ----------------+
                                          |
L4  FUSION + POLICY ENGINE  (case-level stacker, cost-aware thresholds, tiers, hysteresis, alert budget)
                                          |
L4b PART 04 CONTEXTUAL BANDIT  (chooses next permitted action under external safety constraints)
                                          |
L5  UX / REPORT / REVIEW CONSOLE  -> user outcomes -> FEEDBACK LEDGER -> label ops, evaluation,
                                                                   separate retraining workflows
SIDE RAILS: security | lifecycle (registry, shadow, rollback) | governance | threat intel | Cline (DEV, AUTO, RUNTIME)
```

### 2.2 Component inventory

| ID | Component | Channel | Source document | State |
| --- | --- | --- | --- | --- |
| C01 | Ingestion adapters + canonical events | All | ScamRoom v5 | Specified |
| C02 | Stage 1 encoding + entity enrichment | T | ScamRoom v5 | Specified |
| C03 | Room 1 (entity reputation) | T, V | ScamRoom v5 | Specified |
| C04 | Room 2 (chat context, funnel, dormancy) | T | ScamRoom v5 | Specified |
| C05 | GNN prior (ablation-gated) | T | ScamRoom v5 | Specified, unproven |
| C06 | Trust Badge | T | ScamRoom v5 | Specified |
| C07 | Router + context assembler | T | ScamRoom v5 | Specified |
| C08 | Stage 3 SLM + change-point localization | T | ScamRoom v5 | Specified |
| C09 | Audio preprocessing module (Part A/B) | V1, V2 | Voice-clone guide | Specified with code |
| C10 | Branch A: AASIST adapter | V1 | Raksham | Specified |
| C11 | Branch B: phonetic formant branch | V1 | Raksham | Specified |
| C12 | Calibration + score fusion | V1 | Raksham | Specified |
| C13 | Interval detector | V1 | Raksham | Specified |
| C14 | STT + content-risk signals | V1, V2 | Raksham, Scam Shield | Specified |
| C15 | Voice risk engine + report | V1 | Raksham | Specified |
| C16 | Live analyser (Cline API) | V2 | Voice Scam Shield | Specified |
| C17 | Live call risk engine (hysteresis) | V2 | Voice Scam Shield | Specified |
| C18 | Caller-reputation hint (Truecaller or mock) | V2 | Voice Scam Shield | Risk: SDK capability unconfirmed |
| C19 | RAG scam-pattern store | V2, T | Voice Scam Shield | Specified |
| C20 | Voice-authenticity adapter | V2 | Voice Scam Shield | Reuses C10/C09 or mock |
| C21 | Fusion + policy engine | All | ScamRoom v5 + new | Specified here |
| C22 | Part 04 contextual bandit | All | Part 04 prompt | Specified, phased |
| C23 | Feedback ledger | All | Part 04 + ScamRoom | Specified |
| C24 | Reviewer console + label ops | All | ScamRoom v5 | Specified |
| C25 | Threat-intel registry | T, V | ScamRoom v5 | Specified |
| C26 | Payment-signal merge | T, V | ScamRoom v5 | Optional |
| C27 | Lifecycle, security, governance rails | All | ScamRoom v5 + Raksham | Specified |
| C28 | Cline harness (DEV / AUTO / RUNTIME) | All | Raksham, guide docs | Specified |

## 3. Shared foundations

### 3.1 Identifiers and hashing

- `case_id`: pseudonymous identifier for one analysed unit (a chat episode, a recording, or a call).
- `chat_id_hash`, `sender_id_hash`, `entity_hash`: salted hashes created on-device. Same salt policy across channels so the same phone number, UPI ID or domain resolves to one entity.
- `recording_id`: pseudonymous recording identifier. Raw file names, phone numbers and names never enter logs, contexts or ledgers.

### 3.2 Canonical event schema

Every source is adapted to one event stream. Text event types: `message`, `edit`, `delete`, `disappear`, `reaction`, `member_join`, `member_leave`, `profile_change`, `call_event`, `media`. Voice adds `audio_asset` (a recording handle, never the bytes) and `transcript_chunk` (text, start\_s, end\_s, asr\_confidence).

Rules: order by `(chat_id, seq)` not wall-clock; dedup by `event_id`; keep deleted and edited messages as flagged records (delete-after-link and edit-after-send are scammer behaviours); disappearing-message chats are processed in memory only; each adapter declares capability flags (for example 'cannot see outgoing messages') so absence of evidence is never read as safety.

### 3.3 Unified Signal schema

Every detector, enrichment module and LLM analyser emits the same object, so the fusion engine and bandit never import feature-specific code.

| Field | Meaning |
| --- | --- |
| name, version | Signal identity, e.g. `aasist_spoof` v1.0 |
| case\_id, channel | T, V1 or V2 |
| value | The score |
| score\_semantics | `calibrated_probability`, `model_score`, `policy_score_0_100`, `categorical`, `unavailable` |
| orientation | Always 'higher = more risk' after adaptation; raw orientation recorded |
| confidence / uncertainty | Separate from risk |
| window | start\_s, end\_s or message ids, where applicable |
| evidence\_ids | Stable ids so the same evidence is credited once across overlapping chunks |
| quality\_flags | e.g. `phone_band`, `short_audio`, `ood` |
| latency\_ms, ts\_utc | Audit |

### 3.4 Score semantics registry

| Signal | Produced by | Semantics | Rule |
| --- | --- | --- | --- |
| p\_slm | C08 | Calibrated probability (temperature-scaled per language slice) | Usable in stacker |
| p\_url, p\_pay, p\_rep | C02, C26, C03 | Probability-like, calibrated on validation | Usable in stacker |
| aasist\_spoof | C10 | Model score until calibration validated | Never mixed raw with other logits |
| phonetic\_spoof | C11 | Model score until calibration validated | Same |
| voice\_fused | C12 | Calibrated only if held-out calibration holds | Else labelled model score |
| content\_risk | C14 | Categorical (low / medium / high / inconclusive / unavailable) | Unvalidated unless a validated classifier exists |
| call\_risk | C17 | Policy score 0-100, not a probability | Alert driver for V2 only |
| voice\_authenticity (live) | C20 | Model score plus confidence | Separate field, never folded into call\_risk |
| spam\_hint | C18 | Prior only | Scales threshold, never blocks |

### 3.5 Shared entity layer

Phone numbers, UPI IDs, domains and sender IDs are entities in one store (Room 1 sketches, TTL, hub exclusion). A caller number seen in a V2 call is looked up exactly like a phone number in a text chat. A UPI ID from a chat and the same ID in a pending payment resolve to the same hash. Cross-channel presence is a feature (`seen_on_n_channels`) and a GNN edge type with hub caps.

### 3.6 Time base

Text uses `ts_utc` and `seq`. Audio uses seconds from recording start, preserved through windowing so every flagged interval maps back to the original file. Live calls carry both (`ts_utc` of chunk and `start_s` within call).

## 4. Text channel architecture (ScamRoom v5)

### 4.1 Targets and scope

Mid-level, mass-blast scams (fake jobs, UPI/QR fraud, OTP phishing, fake KYC, wrong-number openers, compromised-friend money asks). Decision window: first 3-15 messages or last 48 h. CPU only, <= 4 GB RAM, models <= 25 MB int8, p95 <= 50 ms per message, <= 200 KB per active chat.

### 4.2 Stage 1: cheap per-message encoding

| Part | What it does |
| --- | --- |
| Metadata | contact status, group flag, forwarded flag, time, join and profile-change events |
| Normalizer + lexicon | leetspeak, homoglyph, zero-width and Hinglish handling; category weights (urgency, money, OTP, authority, off-platform); negation-aware (a warning like 'never share your OTP' suppresses the hit) |
| Tiny encoder | int8, <= 8 MB, per-message embedding |
| MinHash + SimHash | template reuse (exact shingles) and paraphrase reuse (embedding hash) |
| Image path | OCR, QR parse (payee, amount, direction), UPI parse, pHash, verified sender registry |
| Entity enrichment | URL: domain age, TLD risk, punycode, typosquat distance, shortener depth, blocklists. Phone: line type, region, blocklists. UPI: handle validity, first-time payee, collect vs pay. SMS header: look-alike distance to registry. Tiered lookup (Bloom filter, TTL cache, optional hash-prefix server) with hard timeout returning 'unknown'. Never fetch live URL content from the device |

### 4.3 Stage 2: memory and context (priors, never a gate)

- **Room 1, entity reputation:** time-decayed traffic R\_e(t) = sum of w\_i \* 2^(-(t - t\_i)/tau), tau 24-48 h; recipient ratio rho = U/D (no-prior-contact recipients over distinct recipients, HyperLogLog) so banks and couriers are not flagged. Anti-poisoning: reporter-trust weighting, per-reporter caps, quarantine before Bloom-filter promotion.
- **Room 2, chat context (always on):** ring buffer, event index, scam-funnel stage (contact, rapport, off-platform, link/payment, pressure), leaky accumulator s\_t = min(S\_max, lambda \* s\_(t-1) + sum of new weighted signals) with each signal type counted once per episode, funnel-order bonus beta for in-order evidence, dormancy-then-burst multiplier (never an alarm alone).
- **GNN layer:** relational message passing over shared sender, link, UPI, similarity, time and cross-channel edges, time-decayed edge weights, hub degree cap, Trust-Badge chats as propagation barriers. Kept only if the ablation shows it beats entity counters.
- **Trust Badge:** user-granted, on-device, expires in 90 days, reduces monitoring but never to zero; hard tripwires (money ask, link to new domain, off-platform request, 'whitelist me' phrases, profile or device change) suspend it before the policy runs.

### 4.4 Router and context assembler

Router runs the SLM when a trigger fires (link, money ask, OTP, platform shift, dormancy-burst, tripwire), every N\_c messages, or with probability epsilon + kappa \* entropy of the previous score. A chat is never skipped permanently. Assembler packs 384 tokens: first message, last N, event messages, funnel state, Room 1 and GNN priors, 2-3 scam exemplars. Event-indexed packing means padding attacks cannot push the scam out of the window.

### 4.5 Stage 3: small attention SLM

<= 6 layers, d <= 256. Heads: per-message suspicion p\_j, chat score, scam type, calibration (p = sigmoid(z / T)). Training uses entity-feature dropout (Bernoulli mask, p in \[0.3, 0.5\]) so cold entities still score. Timestamp localization: t\* is the first message from which per-message score stays above threshold theta, shown to the reviewer as 'turned suspicious here' (not raw attention).

### 4.6 Text outputs

Calibrated scam probability, scam type, short warning, flagged message ids with timestamps (t\*), funnel state, trust status with the tripwire that suspended it, and hashed feedback records.

### 4.7 Text evaluation and the decisive first experiment

Metrics: PR-AUC, recall at 0.5% FPR, time-to-detection, localization within +/-2 messages, latency and memory per chat, robustness to paraphrase, obfuscation and padding, per-category false positives, cold-entity vs known-entity recall, per-language and per-script slices with ECE. On campaign-held-out data with hard negatives (rent splitting, delivery OTPs, genuine bank alerts, family warning forwards, fundraisers, friends reconnecting), compare small-model-alone and entity-counters-only against the full pipeline. If the full pipeline does not beat a small model plus counters, the extra stages are not justified.

## 5. Recorded voice architecture (Raksham Parts 01-03)

### 5.1 Flow

```
recording -> validate -> mono 16 kHz -> VAD -> quality metadata -> overlapping windows (timestamps kept)
   Branch A: AASIST window scores            Branch B: vowel segments -> F1/F2/F3 -> quality filter -> LR
          \                                   /
           calibration (per branch) -> weighted fusion (weights from validation)
                        |
         smoothing -> threshold at validation operating point -> merge -> suspicious intervals
                        |
   optional STT chunks -> content-risk signals (separate field) -> risk engine -> report (JSON + readable)
```

### 5.2 Part A: dataset preprocessing (training side)

Dataset: ASVspoof 2021 DF (`SpeechAntiSpoofingBenchmarks/ASVspoof2021_DF`), binary bonafide vs spoof, 611,829 eval trials, about 96% spoof, 100+ attack algorithms. Audio is already 16 kHz mono FLAC, so inspect first and reuse valid files.

1. **Inspect:** label counts per split, duration stats, sample rate and channels of every file, parse `notes` (codec, attack\_id, vocoder), corrupt and zero-length files.
2. **Validate:** readable, float32, stereo to mono, resample only if not 16 kHz, reject NaN/Inf, flag peak < 1e-4.
3. **Waveform:** pre-emphasis y\[n\] = x\[n\] - 0.97 \* x\[n-1\]; fixed 64,600 samples (about 4.04 s): longer = random crop (train) or first crop (eval), shorter = repeat-pad; denoising off by default (enable only if an experiment improves EER).
4. **Features:** Wav2Vec2-style detectors take the waveform directly; log-Mel, LFCC and the 193-dim hybrid vector are optional baselines only.
5. **Split integrity:** official train/dev/eval, duplicate and speaker/source overlap checks, label consistency, no tuning on eval.
6. **Deliverables:** `manifest.csv` (file\_id, path, label 0/1, duration, codec, attack\_id, vocoder, split), `bad_files.csv`, `quality_report.md`, imbalance note (report EER and class-wise errors, not accuracy).

### 5.3 One shared waveform function, versioned per detector

`to_model_waveform()` is the single function used in training and inference (reference code in the preprocessing guide). It is versioned by detector spec: sample rate, length, pre-emphasis flag, crop policy. **Open item to confirm in the audit:** the preprocessing guide applies pre-emphasis 0.97 for a Wav2Vec2 detector, while the official AASIST recipe works on fixed-length (about 4 s, 16 kHz) raw waveform segments; each detector adapter must declare its own spec and the audit must verify it against that detector's own evaluation code. A mismatch between training and inference preprocessing collapses accuracy.

### 5.4 Part B: inference preprocessing

- **Diarization:** `pyannote/speaker-diarization-3.1` (gated; accept terms, token via `HF_TOKEN` env var). Returns (speaker\_id, start, end). Labels are anonymous and local to one recording. Send pyannote mono 16 kHz audio without pre-emphasis or the 64,600 crop.
- **Chunking:** each speaker turn cut into detector-sized windows (default hop = half window, drop turns under 1 s), original timestamps preserved, `to_model_waveform()` applied per chunk only.
- **Aggregation:** per-speaker mean / max / top-k of chunk scores; never trust a single chunk.
- **Telephony reality:** ASVspoof is clean single-speaker audio; real calls are 8 kHz band-limited (G.711/AMR), noisy, overlapping. Training adds codec and telephony augmentation; overlapping speech lowers diarization confidence and is flagged.

### 5.5 Branch A: AASIST

Official AASIST (spectro-temporal graph attention) vendored untouched at a recorded commit; adaptations in wrapper modules. Before any experiment verify input tensor shape, sample rate, input length, checkpoint loading, genuine/spoof label mapping and score orientation, and save the verification output. Reproduce the repository's own evaluation first, then evaluate on the team split file; report both and label ours as a reproduction, never as official performance.

### 5.6 Branch B: phonetic evidence

Vowel segments (forced alignment with a tool such as Montreal Forced Aligner, or STT timestamps plus a pronunciation dictionary; decide in a decision-log entry after checking alignment quality on a labelled subset). Praat via Parselmouth: F1, F2, F3 at the vowel midpoint; evaluate fixed vs adaptive formant ceilings (around 5000 Hz male, 5500 Hz female typical, five formants) because speaker sex and accent cannot be assumed. Quality filters reject short, noisy or implausible vowels and record the usable-vowel fraction. Too few usable vowels means 'unavailable' for that window, never spoof evidence. Classifier: logistic regression first, small gradient-boosted model as optional comparison, trained on training speakers only. Source paper is speaker-specific; generalization to unknown speakers is not assumed.

### 5.7 Calibration and fusion

Both scores oriented so higher = more spoof-like. Calibration (Platt or isotonic) fitted on validation data per branch or on the fused score, then ECE, Brier score and reliability diagram on held-out data. Fusion S = wA \* A + wP \* P, non-negative weights summing to one, selected on validation; a learned fusion model only if validation size supports it. Missing branch for a window: use the separately validated AASIST-only calibrated score or return inconclusive, and record which. Always report AASIST alone, phonetic alone and fusion on identical splits, negative results included.

### 5.8 Interval detection

Overlapping windows, each carrying AASIST score, phonetic features (where enough speech), fused score, quality indicators, model version, original start/end. Documented smoothing (for example short moving median), threshold at the validation operating point, merge adjacent flags under a maximum gap and minimum duration. Raw window scores stay in the report appendix. Window length, stride and minimum region duration are evaluated parameters. Localization metrics only where segment-level reference labels exist; otherwise intervals are a review aid, not validated boundaries, and never 'word-level detection'.

### 5.9 STT and content signals

STT (candidate: Whisper) produces timestamped chunks linked to audio windows. Content signals: requests for password, PIN or OTP, urgent payment demands, institution impersonation, suspicious links or instructions. These are signals, not proof, and are reported as unvalidated unless a classifier with its own labels and validation exists. Transcript text can also enter the text pipeline (section 7.5) as a `message` with `media.kind = audio`.

### 5.10 Voice risk engine

Separate fields: voice authenticity (genuine-like, spoof-like, inconclusive), content risk, optional context risk, audio quality, uncertainty, overall category. Prototype policy: R\_voice = 100 \* p\_spoof; R\_content = 100 \* sum(w\_i \* c\_i); R\_overall = alpha \* R\_voice + beta \* R\_content + gamma \* R\_context, non-negative weights summing to one over the signals that apply. Missing signals are never zero risk: renormalize under the documented policy or return inconclusive. Low-quality or out-of-distribution audio yields a low-confidence warning, not a fraud flag. Weights and thresholds are policy choices, not established fraud probabilities, and every report stores component scores, weights, thresholds, calibration version and model versions.

### 5.11 Report

Recording id, duration, quality summary, overall category, authenticity and content assessments side by side, scores with calibration status, suspicious intervals with playback reference, transcript excerpts, reason per flag, model, configuration, calibration and policy versions, uncertainty, limitations, and a next step matched to risk: low is not a guarantee of safety; medium means review highlighted sections and verify unusual requests independently; high means do not act on suspicious requests until verified through a trusted channel; inconclusive means obtain clearer audio or request human review. Exports: JSON and readable document. No example scores or timestamps are hardcoded in the generator.

### 5.12 Research extension (only if time permits)

NSF-PINN-inspired source-filter branch: WavLM-Base+ backbone, learned source and filter latents, reconstruction, temporal-smoothness and orthogonality losses, auxiliary-loss warmup, optional SAM. Described as learned latents, never exact vocal-anatomy reconstruction; evaluated independently before any score-level fusion; feature-level fusion only if interfaces genuinely match. Dropped first if time is short.

### 5.13 Evaluation and robustness

Speaker-aware (and attack-aware) split file versioned once; final test touched once per frozen configuration; EER, precision, recall and FPR at stated thresholds, calibration quality, results per attack type, latency and memory, multi-seed variability. Robustness harness with recorded parameters: additive noise at several SNRs, codec re-encoding and narrowband telephony simulation, resampling, reverberation, volume change, trimming; unseen-synthesis experiment holds out whole generator families. Results tables always have three groups: measured by us, reported in literature, not yet run.

## 6. Live-call architecture (Voice Scam Shield)

### 6.1 Flow

```
audio -> STT -> 10-15 s chunk -> [caller-number hint + RAG patterns + lookalike list + user context]
                               -> Cline API analyser (structured JSON signals)
                               -> call risk engine (score + hysteresis) -> banner + beep / report
audio -> voice-authenticity model -> score + confidence -> separate badge, steers pattern priority only
```

### 6.2 Evidence sources

Live transcript chunks; rolling call summary; caller identity claims vs caller ID ('I am your bank' from a personal mobile number); caller-reputation hint (Truecaller or mock, prior only); contact prior (saved contact lowers prior slightly, never zero); user-side legitimate context declared passively in advance (pending login, OTP request, active delivery order); trending scam patterns (RAG); voice-authenticity score. No questions are ever asked to the user mid-call.

### 6.3 Analyser contract

The Cline API (OpenAI-compatible `chat/completions`) receives latest chunk, rolling summary, pre-call signals, retrieved patterns, lookalike list and the latest authenticity result. It must reason from first principles (what is asked, by whom, with what pressure) before consulting retrieved patterns, and returns schema-validated JSON: `signals[{type, strength, evidence}]`, `legit_indicators`, `scam_type_guess`, `novel_pattern`, `risky_ask`, `confidence`, `summary_so_far`. Invalid JSON gets one retry, then a canned fallback. Critical triggers (OTP/PIN request, payment by gift card or wire, remote-access request) also have a deterministic keyword/regex pre-check in the risk engine so LLM latency cannot delay the alert.

### 6.4 Call risk engine

- Score 0-100 starting from a prior set by the caller-reputation hint and contact status. Each signal adds a type- and strength-weighted delta; legitimate indicators subtract up to a cap and never cancel a risky ask; slow decay when the call turns benign.
- **Hysteresis:** raise alert at upper threshold (example 70), clear only below lower (example 50); two consecutive chunks above upper unless a critical trigger fires immediately.
- Spam hint multiplies the alert threshold by about 0.8 (demo value) instead of blocking.
- Each evidence item has an id and is credited once across overlapping chunks.
- End of call: if the threshold was never crossed, log 'no alert raised' silently; no report, no notification.

### 6.5 Taxonomy and lookalikes

Personal: family emergency / voice clone, fake authority, bank/KYC/OTP fraud, tech-support remote access, prize/refund/investment, romance. Business: executive impersonation, vendor/invoice change, customer account takeover, helpdesk social engineering. **Lookalikes that must not alert:** bank OTP automated calls tied to a user-initiated action, two-step login calls, delivery and ride calls matching an active order, appointment and airline reminders, genuine support callbacks, government and utility notices without gift-card or personal-UPI payment or threats, a real family call from a new number (money ask alone proves nothing either way). Each lookalike is a test case.

### 6.6 Voice-authenticity signal in the live path

High AI-generated: extra weight on impersonation patterns (cloned family member, executive, authority). High human-like: normal analysis, never proof of safety. Uncertain: rely on conversation and reputation evidence. No fixed multiplier on overall risk; configurable evidence weights; shown as its own badge; never presented as speaker identity (matching an enrolled family voice would need separate speaker verification, future work). If no open-weight classifier is ready, a mock behind the same interface is used and disclosed.

### 6.7 Demo constraints and honesty

Primary demo: call-simulator page playing scripted scam and legitimate scenarios through the same STT pipeline; optional WebRTC two-tab variant. Real carrier-call tapping is not promised. Truecaller SDK capability for arbitrary incoming-number spam lookup is unconfirmed (RISK): verify first, otherwise mock behind `getNumberHint(number)` and say so. Consent notice shown; audio not stored; synthetic data only.

## 7. Cross-channel fusion and policy engine (L4)

The source documents define three separate decision rules: ScamRoom (cost-aware thresholds, tiers), Raksham (weighted voice/content/context risk, abstention) and Voice Scam Shield (0-100 score with hysteresis and critical triggers). This section reconciles them into one policy layer.

### 7.1 Two-level fusion

1. **Channel level (unchanged from each design):** T produces p\_slm and enrichment signals; V1 produces voice\_fused, content\_risk and quality; V2 produces call\_risk and the authenticity badge.
2. **Case level (new):** a small stacker (logistic regression or shallow GBM) combines calibrated probabilities only: z = w . \[logit(p\_slm), logit(p\_url), logit(p\_pay), logit(p\_rep), logit(p\_voice\_fused, if calibrated), logit(p\_content, if validated)\] + b, then p = sigmoid(z / T). Signals with `score_semantics` of `model_score`, `policy_score_0_100` or `categorical` are never fed in as probabilities; they enter as masked features, tier modifiers or display fields.
3. **Missing signals** are masked (weight zeroed, learned 'absent' input), so the engine degrades gracefully when no payment app, no STT or no authenticity model is present.

### 7.2 Reconciliation of rules from the source documents

| Topic | Source rule | Unified rule |
| --- | --- | --- |
| No evidence | Scam Shield: insufficient evidence at call end = not a scam. Raksham: low quality = inconclusive | Output state is one of `alert`, `no_alert_raised`, `inconclusive`. 'no\_alert\_raised' is not 'verified safe'. Low quality or out-of-distribution input yields `inconclusive` with a reason code |
| Risky ask without context | Scam Shield: alert if legitimate context is absent | A critical trigger (OTP/PIN request, gift-card or wire payment, remote access) with no legitimate context fires at once; absence of context alone does nothing |
| Voice synthetic or not | Scam Shield: separate badge; Raksham: separate field | Authenticity never multiplies risk. It can steer which scam patterns the analyser prioritizes and appears as its own field; a human voice reading a scam script still alerts on content |
| Threshold | ScamRoom: cost-aware theta\* = C\_fp / (C\_fp + C\_miss); Scam Shield: fixed 70/50 | V2 keeps 70/50 hysteresis on call\_risk. Case-level tiers use cost-aware thresholds. Both are configuration, versioned |
| Reputation hint | Scam Shield: Truecaller scales threshold x0.8; ScamRoom: Room 1 prior | Both are priors. Spam hint and Room 1 reputation lower the threshold or raise the prior, never block, never alone alert |
| Weights | Raksham: alpha, beta, gamma sum to 1 over applicable signals | Renormalize only under the documented policy; otherwise `inconclusive` |
| Retrieved patterns | Scam Shield: RAG patterns as hints | At most a modest nudge; the first-principles path always runs; `novel_pattern` flag preserved |

### 7.3 Severity tiers and actions

| Tier | Condition (example, configurable) | Action |
| --- | --- | --- |
| 0 | p < theta\_1 | Nothing |
| 1 | theta\_1 <= p < theta\_2 | Quiet nudge (small banner: 'new contact asked for a link') |
| 2 | theta\_2 <= p < theta\_3 | Strong warning with flagged messages (from t\*) or flagged intervals |
| 3 | p >= theta\_3, or tier 2 with a payment pending, or a V2 critical trigger | Payment friction: short cooling-off, confirm-payee screen, optional guardian alert (signal only, never content) |

Cost-aware threshold: act when p \* C\_miss > (1 - p) \* C\_fp, i.e. p > C\_fp / (C\_fp + C\_miss), with C\_miss multiplied by (1 + eta) when a payment is pending to an entity seen in a flagged case.

### 7.4 Anti-flapping and alert fatigue

- **Hysteresis:** raise at p >= theta\_hi; clear only when p < theta\_lo for n consecutive messages or chunks.
- **Alert budget:** cap tier-1 and tier-2 alerts per user per day, with a per-sender cooldown; tier 3 and V2 critical triggers are exempt.
- **Trust Badge:** raises the threshold only while no tripwire has fired; a tripwire suspends the badge before policy runs.
- Each piece of evidence has an id and is credited once, so overlapping chunks or repeated messages cannot inflate the score.

### 7.5 Bridges between channels

| Bridge | Mechanism |
| --- | --- |
| Voice note to text pipeline | ASR transcript becomes a `message` with `media.kind = audio`; ASR-error augmentation in text training; the voice-authenticity result travels as a separate signal on the same case |
| Call to text | Caller number and any UPI ID or link spoken in the call become entities in Room 1; a later chat from the same number inherits reputation |
| Text to call | A flagged chat with the same number raises the V2 prior, same as a spam hint |
| Payment to either | A payee hash that appeared in a flagged chat or call raises C\_miss; a payment-side fraud report turns the linked case into a confirmed label |
| Cross-channel resolution | Shared salted hashes; GNN `cross_channel` edge type (gated, hub-capped); feature `seen_on_n_channels` |

## 8. Part 04: contextual-bandit action layer (L4b)

### 8.1 Role and limits

A lightweight contextual bandit selects the most useful permitted next action from a privacy-minimized context assembled from the upstream parts. It does not decide whether anyone is fraudulent, does not replace any detector, does not change thresholds or weights, and does not block calls. Mandatory safety constraints are enforced outside the learned policy.

### 8.2 Action space (only actions that exist or are documented interfaces)

| Action id | Meaning | Typical eligibility |
| --- | --- | --- |
| `return_standard_report` | Deliver the evidence report as built | Always eligible (fallback) |
| `prioritize_human_review` | Place the case or interval in the review queue | Reviewer available, case uncertain or tier >= 2 |
| `run_additional_analysis` | Run an approved extra analysis (for example a second window size, a phonetic re-run, an alternative diarization setting) | Module available, compute and latency within budget, audio quality sufficient |
| `request_clearer_audio_or_verification` | Ask for better audio or independent verification through a trusted channel | Inconclusive quality, high-impact request pending |

The action registry records, per action: identifier, eligibility conditions, required inputs, execution interface, expected latency and cost, safety constraints, failure and fallback behaviour.

### 8.3 Context schema (versioned and validated)

Fields are optional where upstream modules may be absent, and missing values are explicit.

| Group | Fields |
| --- | --- |
| Identity | `recording_id` or `case_id` (pseudonymous), `context_schema_version` |
| Voice | `aasist_score` + `score_semantics`, `phonetic_score` + `score_semantics`, `fused_score` + `calibration_status`, `model_disagreement`, `valid_formant_coverage` |
| Quality | `uncertainty_level`, `out_of_distribution_flag`, `duration_seconds`, `audio_quality_features` |
| Content | `transcript_content_risk_features` (categorical features only) |
| Text | tier, funnel stage, `p_slm` with calibration status (when the case includes chat evidence) |
| Capability | `available_analysis_modules`, `identification_module_type` and `available_results` (it may be diarization or entity extraction, not speaker identification) |
| Cost | `estimated_action_latency`, `estimated_compute_cost`, `reviewer_availability` |
| History | `previous_verified_outcome_summary`, only where permitted |

Never in context: raw audio, full transcripts, names, phone numbers, credentials. Raw logits from different models are never compared as calibrated probabilities.

### 8.4 Policies

1. **Baseline:** fixed rule-based policy, always present, used as fallback and as the comparison arm.
2. **Contextual linear bandit (Linear UCB)** only if data and reward structure justify it: for each eligible action a, score = theta\_a . x + alpha \* sqrt(x^T A\_a^-1 x), where A\_a = I + sum of x x^T over observed contexts for a and theta\_a = A\_a^-1 b\_a. Rank eligible actions and select per configured policy.
3. Exploration only in offline experiments or explicitly approved low-risk review allocation; never randomized experiments on consequential real-world decisions. Action-selection probability is logged whenever selection is stochastic.
4. If context validation fails or the policy is unavailable, return an explicit fallback action.

### 8.5 Safety constraints (outside the learned policy)

- Only eligible actions can be selected; empty eligible set returns the fallback.
- No action may auto-block a call, accuse a person, change a detector threshold, alter an authenticity label or edit detector weights.
- High-impact requests still carry the 'verify through an independent trusted channel' recommendation regardless of policy output.
- Compute, latency and reviewer-load ceilings enforced before selection.

### 8.6 Reward and feedback

Configurable components with individually reported contributions: review usefulness, evidence completeness, time to resolve uncertainty, compute and latency cost, avoidable reviewer burden, whether the action completed. Not rewarded: high spoof scores, number of flags, agreement with an unverified opinion.

Outcome provenance is always recorded and kept distinct: user feedback, reviewer assessment, independently verified outcome, unknown or unresolved. Unknown is never silently converted to a negative or positive label. Missing, duplicated, invalid or unverified labels are not trained on as ground truth.

### 8.7 Feedback ledger

Local JSONL or SQLite first. One record per decision: `case_id`, `context_schema_version`, `policy_version`, `eligible_actions`, `selected_action`, `action_selection_probability` (when applicable), `execution_status`, `reward_components`, `total_reward` (when computable), `feedback_source`, `outcome_verification_status`, `outcome_timestamp`, model and configuration versions, error or abstention reason. Never stored: secrets, API keys, raw audio, unnecessary personal data. Retention, access and deletion behaviour documented; duplicates handled idempotently.

### 8.8 Offline evaluation and promotion

- Compare fixed baseline vs contextual bandit (optional third policy only if justified) on held-out data with fixed seeds and confidence intervals.
- Metrics: mean observed reward with intervals, useful completed reviews per unit time, decision and analysis latency, compute cost, failed or unavailable action rate, reviewer burden, coverage of unresolved or low-quality cases, safety-constraint violations, performance by audio-quality and model-disagreement groups.
- Off-policy evaluation (inverse propensity scoring or doubly robust) only where logged probabilities support it; check overlap/positivity, logging correctness, sample size and variance, and do not present estimates as reliable when assumptions fail.
- A small synthetic simulation tests that the policy can learn under known reward distributions and is labelled simulation, not real-world evidence.
- **Promotion** needs: offline evaluation against baseline, safety and privacy checks, review of eligibility and fallback, documented reward configuration and evaluation data, human approval, versioning and a tested rollback. A failed policy leaves the previous one in place.
- The bandit is never claimed to improve deepfake-detection accuracy unless a separate valid experiment shows it.

### 8.9 Modules and integration interface

Modules (adapt names to the repository): `context_builder`, `context_schema`, `action_registry`, `baseline_policy`, `contextual_bandit`, `reward_calculator`, `feedback_ledger`, `policy_evaluation`, `policy_manager`, `safety_constraints`, `integration_adapter`, `tests/`.

Interface in: validated context, available and eligible actions, current policy version, safety constraints, action cost estimates. Interface out: selected action, ranked eligible actions, estimated utility, exploration or selection metadata, rationale built only from logged features, eligibility rules and policy estimates (no private chain-of-thought), applied constraints, policy version, audit metadata.

Implementation sequence: A repository audit and integration report; B schemas, registry, baseline; C ledger and reward; D bandit; E simulation and offline evaluation; F adapters to Parts 01-03; G versioning, rollback, safety, docs; H final evidence-based report. One phase at a time, with files changed, tests run and actual results shown after each.

## 9. Data contracts (examples)

All examples are illustrative format examples, not results.

### 9.1 Signal

```json
{
  "name": "aasist_spoof", "version": "1.0", "case_id": "c_01", "channel": "V1",
  "value": 0.91, "score_semantics": "model_score", "orientation": "higher_is_more_spoof",
  "uncertainty": 0.2, "window": {"start_s": 12.4, "end_s": 16.4},
  "evidence_ids": ["w_0031"], "quality_flags": ["phone_band"], "latency_ms": 84
}
```

### 9.2 Live analyser output (V2)

```json
{
  "signals": [{"type": "urgency", "strength": 0.7, "evidence": "asks to send money within minutes"}],
  "legit_indicators": [], "scam_type_guess": "family_emergency", "novel_pattern": false,
  "risky_ask": true, "confidence": 0.75, "summary_so_far": "Caller claims to be the user's child and asks for money."
}
```

### 9.3 Bandit context and decision

```json
{
  "context_schema_version": "1.0", "case_id": "c_01",
  "fused_score": {"value": 0.74, "calibration_status": "uncalibrated"},
  "model_disagreement": 0.31, "duration_seconds": 38.5, "out_of_distribution_flag": true,
  "available_analysis_modules": ["phonetic_rerun"], "identification_module_type": "diarization",
  "reviewer_availability": "limited", "transcript_content_risk_features": null
}
```

```json
{
  "selected_action": "request_clearer_audio_or_verification",
  "ranked_eligible": ["request_clearer_audio_or_verification", "prioritize_human_review", "return_standard_report"],
  "estimated_utility": {"request_clearer_audio_or_verification": 0.42},
  "selection": {"policy": "baseline_rules", "probability": 1.0},
  "rationale": "OOD flag set; fused score uncalibrated; reviewer availability limited.",
  "applied_constraints": ["no_auto_block", "no_threshold_change"], "policy_version": "rules-0.1"
}
```

### 9.4 Ledger record

```json
{
  "case_id": "c_01", "context_schema_version": "1.0", "policy_version": "rules-0.1",
  "eligible_actions": ["return_standard_report", "prioritize_human_review", "request_clearer_audio_or_verification"],
  "selected_action": "request_clearer_audio_or_verification", "action_selection_probability": 1.0,
  "execution_status": "completed", "reward_components": {"completed": 1.0, "latency_cost": -0.05},
  "total_reward": null, "feedback_source": "reviewer", "outcome_verification_status": "unverified",
  "outcome_timestamp": null, "abstention_reason": null
}
```

### 9.5 Report (voice) required fields

recording id; duration; quality summary; overall category; voice authenticity (genuine-like / spoof-like / inconclusive) with score type and calibration status; content risk (low / medium / high / inconclusive / unavailable) with trigger signals and validation status; per-interval AASIST and phonetic evidence; suspicious intervals (start, end, supporting signals, reliability, playback reference); transcript excerpts; reasons; model, configuration, calibration and scoring-policy versions; uncertainty; limitations; recommended next step.

## 10. Where and how Cline is used

Cline is an open-source coding agent. The documents use it in three distinct ways; they are kept separate because they carry different risk.

### 10.1 DEV: Cline as the builder (VS Code)

| Practice | Detail |
| --- | --- |
| Setup | Install the extension, open the repository folder first, sign in with the Cline provider, choose credits or ClinePass deliberately (they are separate providers), enable separate Plan and Act models, keep checkpoints on, auto-approve reads only, no YOLO mode |
| Loop | One goal per task, @-mention files, Plan then Act, review each diff, run tests, commit at each good state, /newtask to hand off, /deep-planning for big components |
| Models | Strongest affordable in Plan (architecture, splits, calibration, fusion, policy), mid-tier in Act (implementation, tests), cheapest only on public code (commit messages, renames) |
| Rules pack (`.clinerules/`) | 00-master-workflow, 10-scientific-integrity, 11-baseline-preservation, 20-evaluation-protocol (conditional on evaluation paths), 30-risk-engine-and-report (conditional), 40-privacy-and-safety, 50-engineering-conventions (conditional), 60-notebook-hygiene (conditional); for the live-call build also 10-scope, 30-backend and 40-frontend conditional rules |
| Skills | `raksham-repo-audit`, `raksham-run-experiment`, `raksham-results-table`, `raksham-report-check`, `raksham-precommit-review`, `raksham-formant-qa` |
| Memory Bank | projectbrief, productContext, activeContext, systemPatterns, techContext, progress, plus a decisions log (split design, calibration method, vowel segmentation, each threshold with its validation data) |
| Jupyter | Cell generate/explain/improve; notebooks as thin drivers over importable modules |
| Data boundary | Audio, transcripts and non-public data never enter Cline chat, @-mentions, drag-and-drop or terminal output Cline reads; Cline handles code, config and aggregate metrics; humans run training on own compute |

### 10.2 AUTO: headless Cline tasks (CLI)

| Step | Task | Guardrail |
| --- | --- | --- |
| Dataset audit | `cline -y --json` reads `quality_report.md` and `bad_files.csv`, writes `audit.md` | Reads metadata only |
| Self-healing ingestion | On a non-empty `bad_files.csv`, write a converter in `converters/` plus a pytest test; stop if tests fail | Sandbox only; human approves merge |
| Ablation runner | Denoise vs no-denoise, raw vs log-mel vs LFCC; EER table to `experiment_log.md` | Numbers come from saved outputs |
| Split integrity | Duplicate id and speaker-overlap check; `split_report.md` | Advisory |
| PR review in CI | Cline CLI reviews diffs: unsupported claims, label or score-orientation mistakes, leakage, hardcoded thresholds, secrets, missing tests, example values in report code | Advisory; human approves merges; model key as repository secret |
| Nightly health check | Scheduled test and lint run with status file | Code repository only |

The CLI's bare prompt runs Act mode with auto-approve on; always use plan mode or disable auto-approve. Third-party hooks, plugins and MCP servers are reviewed as code before enabling.

### 10.3 RUNTIME: Cline inside the product

| Use | Surface | Constraint |
| --- | --- | --- |
| Adaptive preprocessing agent (recorded voice) | Headless `cline -y --json` calling MCP tools `inspect_audio`, `diarize_audio`, `score_call` (and optional `write_report`) under a runtime `.clinerules` | Chooses `num_speakers` hint, chunk overlap, warnings, retries and report wording; never changes the waveform spec, detector, thresholds or pyannote version; not in the real-time scoring path; falls back to defaults on failure |
| Live chunk analyser | Cline API (`https://api.cline.bot/api/v1/chat/completions`, key in environment) | Plain API call with a tight prompt, not a multi-step agent; returns schema-validated signals; backend computes the score |
| Report wording (optional, off by default) | Cline API | Rephrases fields already computed; never sees raw audio; never decides authenticity or scores; data-handling terms checked before any transcript is sent |

Runtime policy for the adaptive agent (summary): always call `inspect_audio` first; two-party call or voice note uses `num_speakers = 2`; duration under 8 s uses overlap 0.75, otherwise 0.5; phone-quality audio lowers confidence and is stated in the report; no denoising unless the experiment log shows improved EER; scores reported exactly as returned; `report.md` lists settings and why, per-speaker timestamps and scores, warnings. Every tool call and decision is logged into the report for audit.

### 10.4 Surface limits

Sub-agents, agent teams, scheduling, custom plugin tools and hooks are not in the VS Code extension; they live in the CLI, Cline Desktop, Kanban or SDK. Cloud Agents run only on the public code repository, do not load rules, skills or MCP servers, and must be given constraints in the task prompt. Credit expiry, refund and minimum top-up terms are unconfirmed in the documents; verify before large spend. The Cline Complete Guide's own cross-check log lists further version-dependent items (restore button names, free-model API support, model counts).

## 11. Security, privacy and governance

### 11.1 Threat model and defences

| Threat | Defence |
| --- | --- |
| Text injection aimed at the model ('this chat is safe', fake authority tags) | Scoring path is a classifier, not an instruction-following LLM. LLM output (analyser, explanations) is schema-validated, treats message and web text as data, and never changes a score directly. 'Whitelist me' phrases are a tripwire |
| Prompt injection via RAG refresh or web content | All scraped content treated as data; patterns are hints only; no instruction execution |
| Probing the detector | Never expose scores or alerts to the counterparty; rate-limit and monitor near-duplicate variants |
| Model extraction or tampering | Signed versioned bundles, integrity check at load, no raw scores via any API |
| Trust Badge tampering | Hardware-backed keystore, explicit user action with local auth, logged suspensions |
| Room 1 / GNN poisoning | Reporter-trust weighting, diversity thresholds, per-reporter caps, anomaly detection, quarantine before promotion |
| Feedback poisoning | Audited random sample, double annotation, reviewer reputation, canary campaigns |
| Padding or flooding | Event-indexed assembler, per-chat rate caps |
| Agent mistakes (Cline claims success, loops, over-edits) | Plan-first, small milestones, tests, checkpoints, conservative auto-approve, real command output required, human review of every diff affecting results |
| Supply chain | Pinned dependencies and GitHub Action versions; review every package an agent proposes |
| Secrets | Environment variables only; `.env` in `.gitignore`; no tokens in prompts, rules or committed MCP config |

### 11.2 Privacy and consent

- On-device first; ring buffer in memory; persist only hashed entity keys, aggregate counters and audit events. Raw text and audio are never logged.
- Only public, licensed, consented or authorized audio is used for development; recordings are never committed.
- Granular, revocable consent (local scanning, reputation queries, report sharing, guardian alerts). Local-only mode works with everything else off. Live calls show a consent notice and store no audio.
- One-action deletion of local state, trust badges and queued reports. Retention of uploads and transcripts is configurable with a deletion job or endpoint.
- Server reputation uses hash-prefix queries and a k-anonymity gate (an entity is published only after at least k distinct trusted reporters flag it); optional differential-privacy noise; federated learning only for encoder and lexicon weights with secure aggregation.
- Stricter defaults for minors. Legal review items: DPDP-style consent and purpose limitation, platform terms for each ingestion method, defamation risk of warning wording, retention, cross-border transfer, call-recording consent. This document is not legal advice.

### 11.3 Wording and user safety

Warnings say 'risk indicators' and describe behaviour ('asked you to move to another app and pay a new account'); they never call a person a scammer. They show why (flagged messages or intervals and top evidence tags) and are short, local-language and screen-reader friendly. Tier 3 uses a short pause with a plain-language checklist, not a hard block. Reporting handoff to the relevant national cybercrime channels is offered; verify current names and flows before shipping.

## 12. Model lifecycle and evaluation framework

### 12.1 Lifecycle

- **Registry:** semantic versions for weights, lexicon, thresholds, feature schema, blocklists, scoring policy and bandit policy; a bundle is valid only as a consistent set.
- **Signed OTA updates** with delta updates where possible (bundle budget about 5 MB per update).
- **Shadow mode** before any new version can alert; **staged rollout** 1% to 10% to 100% with automatic halt on drift (PSI), false-positive spikes, latency or battery regressions; **one-switch rollback**, drilled.
- **Calibration** per language and region slice with ECE = sum over bins of (|B\_b| / n) \* |acc(B\_b) - conf(B\_b)|; stacker recalibrated after each retrain.
- **Cadence:** lexicon and blocklists daily or weekly; encoder monthly or on drift. Detector retraining (AASIST, phonetic, SLM) is a separate labelled-data workflow, never a side effect of the feedback loop.

### 12.2 Evaluation matrix

| Layer | Metrics | Protocol rules |
| --- | --- | --- |
| Text (T) | PR-AUC, recall at 0.5% FPR, TTD, localization +/-2, latency, memory, per-language ECE, cold-entity recall | Campaign-held-out splits, hard negatives, ablations for every stage |
| Voice (V1) | EER, precision/recall/FPR at stated threshold, calibration (ECE, Brier), per-attack results, localization only with reference labels | Speaker-aware splits, one frozen test run, identical split and script for all systems, multi-seed |
| Live (V2) | Scenario table (6 demo scenarios), false-alert rate on lookalikes, alert latency, JSON validity rate, critical-trigger latency | Scripted scenarios with expected outcomes; synthetic data labelled as such |
| Fusion | Each signal on/off, masked-signal robustness, stacker vs simple average, cost-aware vs fixed 0.5 threshold | Validation-only fitting |
| Bandit | Reward with intervals, OPE with overlap checks, constraint violations, burden, coverage | Simulation labelled separately from real verified outcomes |
| Harm and fairness | Alerts per user per week, override rate, feature-disable rate, FP/miss by language, script, age group, chat type | Online shadow metrics |
| Security | Injection, probing, tamper and poisoning red-team results | Documented pass/fail |
| Resources | Battery, thermal, memory per chat, bundle size, cache hit rate | Measured on target hardware |

### 12.3 Result-reporting rule

Every results table has three labelled groups: measured by us (with ledger entry), reported in the literature, not yet run. Anything stubbed, mocked or synthetic-only is marked explicitly. Numbers from incompatible splits are never compared as equivalent.

## 13. Deployment topologies and budgets

| Topology | Components | Constraints |
| --- | --- | --- |
| On-device (text) | Stage 1, Room 2, Trust Badge, Bloom filters, int8 encoder and SLM, router, local policy | CPU only, <= 4 GB RAM, <= 25 MB models, p95 <= 50 ms per message, <= 200 KB per active chat; background limits respected |
| Optional server (text) | Hash-prefix reputation, threat-intel registry, exemplar index, OTA registry | Hash-only queries, k-anonymity gate, hard client timeout returns 'unknown' |
| Backend (recorded voice) | Preprocessing, AASIST, phonetic branch, calibration, intervals, STT, risk engine, report, API | GPU optional for inference; upload retention configurable; structured errors and degraded honest reports when STT or identification are down |
| Live demo (V2) | Call-simulator web app, WebSocket transcript stream, Cline API analyser client, RAG JSON store, call risk engine, authenticity adapter, caller-hint adapter | Scripted scenarios for reliability; WebRTC variant optional; backup recorded demo; no real telephony |
| CI and automation | Cline CLI PR review, nightly checks, scheduled drift check | Public code only; no recordings; advisory output |

Latency rules: LLM latency must never delay a critical alert (deterministic pre-check); the analyser is a single tight API call; the adaptive preprocessing agent is outside the real-time scoring path; SLM runs only when the router says so.

### 13.1 Recorded-voice API (names to finalize in planning)

Submit recording; check status; fetch JSON report; fetch readable report; fetch audio excerpt for a flagged interval; list model and configuration versions; health check; deletion endpoint or job. Errors covered: unsupported format, too short or too long, corrupt file, missing model files, inference failure, unavailable optional services.

### 13.2 Public text-engine API (merge contract)

`process_event(event)` returns score, stage, warning, flagged message ids, trust status and tier. `submit_signal(signal)` lets other modules push risk signals. `get_chat_state(chat_id_hash)` is read-only and on-device. `grant_trust`, `revoke_trust`, `trust_status` are on-device only. `report_outcome(chat_id_hash, outcome)` feeds the feedback loop (hashed, consent-gated).

### 13.3 Merge steps for any new feature

1. Define its events (source) or its Signal (detector).
2. Write the adapter to the canonical schema with contract tests.
3. Register the signal in the fusion engine and fit its weight on a validation set.
4. Add it to shadow mode and the on/off ablation grid.
5. Complete its privacy review and consent text before rollout.

## 14. Repository layout

```
README.md  AGENTS.md  environment (pinned)  .env.example  LICENSES
.clinerules/            rules pack (section 10.1)
.cline/skills/          project skills
memory-bank/            Cline Memory Bank + decisions log
third_party/aasist/     vendored official code at recorded commit, untouched
platform/
  ingestion/            adapters, canonical events, replay harness
  text/                 stage1/ (encoding, enrichment), rooms/, gnn/, router/, slm/
  voice/                audio_prep (to_model_waveform), validation, vad, windowing,
                        aasist_adapter, phonetic/, calibration, fusion, intervals
  speech/               stt_adapter, content_signals, identification_adapter
  live/                 analyser_client, call_risk_engine, caller_hint, rag_store, authenticity_adapter
  fusion/               signal_bus, stacker, policy_tiers, hysteresis, alert_budget
  bandit/               context_builder, context_schema, action_registry, baseline_policy,
                        contextual_bandit, reward_calculator, feedback_ledger,
                        policy_evaluation, policy_manager, safety_constraints, integration_adapter
  agent/                mcp_server.py (inspect_audio, diarize_audio, score_call), runtime rules
  threatintel/  payment/  labelops/  i18n/  governance/  security/  lifecycle/  ux/
  api/                  recorded-voice service, report builder
web/                    call simulator, review interface, flagged-region playback
configs/                audio, windows, branches, calibration, fusion, risk weights, tiers, bandit, reports
experiments/            split files, run configs, predictions, metrics, results ledger, figures
tests/                  unit, integration (mocked Parts 01-03), leakage/protocol, report, security
docs/                   audit, architecture, datasets, evaluation protocol, decisions log, limitations, demo script
```

No recordings or secrets are committed. Weights, thresholds and window parameters are never hardcoded; every report and ledger record stores the configuration ids that produced it.

## 15. Build roadmap with exit gates

Rule: do not start phase N+1 until phase N's exit criterion is measured, not assumed. If time is short (for example the one-day live-call build), protect the core in the order given and cut the rest first.

| Phase | Build | Exit criterion |
| --- | --- | --- |
| 0 | Cline setup, rules pack, Memory Bank, skills, canonical event schema, replay harness | Rules reviewed; a recorded chat replays deterministically |
| 1 | Repository and environment audit (AASIST, WavLM feasibility, datasets and licenses, compute); split file frozen | `REPO_AUDIT.md` with 'missing requirements and documented defaults'; nothing invented |
| 2 | Reproducible AASIST baseline | Verified shapes, label mapping, EER on correct partition, saved predictions, labelled as our reproduction |
| 3 | Audio preprocessing, VAD, quality metadata, windowing, shared `to_model_waveform` per-detector spec | Silent or short audio never auto-labelled; timestamps preserved; pytest green |
| 4 | Text core: Stage 1, Room 2, enrichment, baselines (small model, LightGBM, entity counters) | Baselines reproducible; latency measured; first experiment run |
| 5 | Phonetic branch with speaker-disjoint evaluation | Leakage tests pass before any number is reported |
| 6 | Calibration, fusion, ablations (voice) | AASIST-only vs phonetic-only vs fusion on identical splits, negatives reported |
| 7 | Router, Room 1, Trust Badge; Stage 3 SLM; localization | Cold-entity set evaluated with and without entity dropout |
| 8 | Interval detection and temporal evaluation | Parameter study; no word-level claim |
| 9 | Live path: analyser client, call risk engine, RAG store, caller hint (real or mock), authenticity adapter, simulator UI | All 6 demo scenarios behave as expected; lookalike scenarios produce no alert |
| 10 | Fusion + policy engine, UX prototype, reviewer console, feedback ledger | Tiers on replayed cases; alert budget respected |
| 11 | Part 04 bandit phases A-H | Baseline vs bandit offline report; promotion gate with rollback drill |
| 12 | Robustness harness; security red-team; governance review | Per-condition tables; injection and tamper tests green |
| 13 | Lifecycle: signed bundles, shadow mode, staged rollout, rollback | Rollback drill passes |
| 14 | Optional: GNN (keep only if ablation justifies), payment merge, source-filter research branch, extra languages | Per-slice metrics reported; unproven parts dropped |
| 15 | Hardening: honesty pass, README, demo | Clean checkout runs from the README; every stated number has a ledger entry |

Cut order if time runs out: source-filter research branch, GNN, push notifications, RAG refresh (use a hand-written patterns file), real caller-reputation integration (use a mock), live authenticity model (use a mock), business scenarios beyond one.

## 16. Risks, conflicts between source documents and open decisions

### 16.1 Risk register

| Risk | Mitigation |
| --- | --- |
| Full text pipeline may not beat a small model plus entity counters | First experiment decides; build extra layers only around the surviving core |
| Fusion of AASIST and phonetic branches may not help | Report negative result; drop the phonetic branch from fusion if it adds nothing |
| Formants unreliable on compressed or noisy speech | Quality filters, 'unavailable' state, never spoof evidence |
| Detector trained on clean ASVspoof fails on phone audio | Telephony and codec augmentation; call-like evaluation samples; robustness suite |
| Training/inference preprocessing mismatch | One versioned function per detector spec; tests; audit against each detector's own eval code |
| LLM latency or bad JSON in live path | Critical-trigger pre-check, schema validation with one retry, canned fallback |
| False positives on lookalikes (bank OTP, delivery) | Lookalike list, legitimate-context declarations, capped subtraction, scenario tests |
| Missed novel scams | First-principles prompt, `novel_pattern` flag, patterns as hints only |
| Slow-burn scams below threshold | Stated limitation of the end-of-call rule; future work |
| Truecaller SDK may not expose spam lookup | Verify first; mock behind the same interface and disclose |
| Bandit learns from unverified or biased feedback | Provenance tracking, no training on unverified labels, overlap checks, human-approved promotion |
| Synthetic data flatters every number | Label synthetic results; treat as provisional until real held-out data |
| Alert fatigue makes users disable the product | Alert budget, hysteresis, harm metrics, shadow mode |
| Privacy and legal exposure | Minimization, consent, deletion, k-anonymity, early legal review |
| Compute limits for GPU work | Estimate in audit; cut research extension first |
| Version drift in Cline menus and flags | Verify against the installed version and current docs before building |

### 16.2 Conflicts and inconsistencies found across the source documents

| # | Finding | Proposed resolution |
| --- | --- | --- |
| 1 | Preprocessing guide specifies pre-emphasis 0.97 and 64,600 samples for a Wav2Vec2 detector; Raksham specifies the official AASIST baseline | Per-detector spec versioning; verify in audit; do not assume AASIST needs pre-emphasis |
| 2 | Preprocessing guide has Cline as a runtime agent via MCP; Raksham limits Cline to development and optional report wording; Scam Shield uses the Cline API as the live analyser | Three scoped runtime uses (section 10.3), all signal-only; none sets a score or touches raw audio except through code the team wrote |
| 3 | Scam Shield treats insufficient evidence as 'not a scam'; Raksham and ScamRoom emphasize abstention and 'unknown' | Output states `alert` / `no_alert_raised` / `inconclusive`; no claim of verified safety |
| 4 | Three different risk scales (0-100 policy score, calibrated probability, 0-100 voice risk) | Score semantics registry (section 3.4); only calibrated probabilities enter the stacker |
| 5 | Raksham says the identification module might not be speaker identification; Scam Shield mentions family voice matching as future work | Bandit context records `identification_module_type`; speaker verification is a separate future capability; authenticity is never shown as identity |
| 6 | ScamRoom is hardware-light and on-device; voice branches (AASIST, WavLM, pyannote) need heavier compute | Voice V1 runs on backend; on-device text stays within its budget; V2 live path uses cloud STT and API |
| 7 | Truecaller capability unconfirmed; free-model API support documented inconsistently; credit expiry undocumented | Verify before depending; mock where needed; top up small |
| 8 | Bandit prompt says Part 03 may contain identification, risk engine and reporting; actual module names unknown | Phase A repository audit decides real interfaces; adapters, not rewrites |

### 16.3 Open decisions

1. Corpus choice and licenses for AASIST training and evaluation (ASVspoof 2019 LA vs 2021 DF vs in-the-wild set) and exact official splits.
2. Compute available (GPU type, memory, session limits); gates the source-filter branch and WavLM.
3. Vowel-segmentation approach (forced alignment vs STT timestamps plus dictionary).
4. STT engine and live analyser model (latency and JSON reliability to be measured).
5. Whether to enable optional hosted-model report wording, and under which data-handling terms.
6. Whether the demo shows real or mocked caller reputation and authenticity.
7. Hackathon length, deadlines, credit allowances and agent-usage rules.
8. Team roles and the single owner of the Cline main-branch driver seat.

### 16.4 Definition of done (platform level)

A fresh checkout builds and runs from the README; tests pass, including leakage, report, security and fallback tests; no secrets or recordings in the repository; every stated number or capability has a ledger entry or an implemented, tested feature; final test sets were evaluated once per frozen configuration; the bandit selects only eligible actions, never alters detector outputs, and its evaluation separates simulation from independently verified outcomes; progress file and README are accurate; the honesty-check pass reports no unsupported statements.

## 17. Source map and glossary

### 17.1 Which source feeds which section

| Section | Primary source |
| --- | --- |
| 1, 3, 7 (policy), 11, 12 | All documents, reconciled here |
| 4, 7.3-7.4, 11.1-11.2 | ScamRoom v5 overview |
| 5, 9.5, 10.1, 15 | Raksham approach and Cline engineering plan |
| 5.2-5.4, 10.2-10.3 | Voice-clone preprocessing and Cline integration |
| 6, 13 (demo), 16 | Voice Scam Shield end-to-end plan |
| 8, 9.3-9.4 | Raksham Part 04 contextual-bandit master prompt |

### 17.2 Glossary

| Term | Meaning |
| --- | --- |
| AASIST | Spectro-temporal graph-attention anti-spoofing model used as the voice baseline |
| Authenticity | Whether speech looks synthetic; not identity, not intent, not fraud |
| Content risk | Suspicious-request signals in what is said; independent of voice authenticity |
| Hysteresis | Separate raise and clear thresholds so alerts do not flicker |
| Lookalike | Legitimate event that resembles a scam (bank OTP, delivery call) |
| OPE | Off-policy evaluation of a new policy from logged decisions (IPS, doubly robust) |
| Room 1 / Room 2 | Entity-reputation memory / per-chat context memory |
| Signal | Unified module output with score semantics, uncertainty and evidence ids |
| t\* | First message from which per-message suspicion stays above threshold |
| Tripwire | Hard condition that suspends the Trust Badge |
| Trust Badge | User-granted, on-device reduced monitoring for a chat or contact |
