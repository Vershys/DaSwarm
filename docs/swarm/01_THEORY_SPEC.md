# Manu-Swarm-Test — Theory & System Specification
Version: 0.1 (Theory Freeze)
Status: Pre-implementation design
Purpose: Define the behavioral, architectural, data, learning, and media-synthesis theory before writing production code.

---

## 1. Mission

**Manu-Swarm-Test** is a persistent autonomous media-intelligence system built on top of AI-Manus. Its purpose is to discover internet content and emerging themes, understand them multimodally, rank and route them to specialized account identities, transform suitable material into original or substantially editorialized media products, publish through deterministic platform adapters, and learn from the downstream response.

The swarm is not modeled as “one AI = one account.” It separates:

1. **Agent roles** — reasoning specializations.
2. **Accounts** — durable public identities and audiences.
3. **Workers** — temporary compute/processes that execute jobs.
4. **Candidates** — discovered pieces of information or media.
5. **Content atoms** — salient subsegments extracted from candidates.
6. **Compositions** — generated/editorial outputs assembled from atoms and original material.

This separation is a core invariant of the project.

---

## 2. Core Design Principles

### 2.1 The swarm is a stateful organization, not a collection of chatbots

Agents coordinate through persistent shared state, queues, and structured objects. They should not need to “talk” conversationally unless reasoning requires it.

### 2.2 Accounts do not own workers

A publisher worker may service many accounts sequentially. Account identity, credentials, history, voice, and audience model are durable; workers are ephemeral.

### 2.3 Discovery must have high recall

The discovery layer should not discard content merely because it is not yet publishable. A candidate may remain useful for:

- trend detection,
- semantic learning,
- highlight extraction,
- motif learning,
- inspiration,
- source tracking,
- account-fit prediction,
- generation of original media,
- human review.

**Discovery eligibility and publish eligibility are separate states.**

### 2.4 Reasoning decides *what*; deterministic software decides *how*

The LLM/agent decides actions such as:

- investigate source,
- analyze candidate,
- route to account,
- create composition,
- publish candidate X to account Y.

Deterministic adapters execute platform-specific API calls, rendering, file operations, and other brittle low-level steps whenever possible.

### 2.5 Optimize outcomes, not one proxy metric

The system must not optimize only likes, raw views, or shortest duration. The objective is multi-dimensional and account-specific.

### 2.6 Content length is learned, not assumed

The system should optimize **information density, time-to-payoff, retention, completion, rewatchability, and account fit**, rather than assuming “shorter = better.”

### 2.7 Provenance is a routing dimension, not a discovery kill-switch

Each candidate receives provenance and rights-confidence metadata. Unclear provenance does not erase the candidate from the intelligence graph. It changes the permissible downstream path.

---

## 3. System Model

```text
                            DIRECTOR
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
         SCOUTS             WATCHERS          INGESTORS
            │                  │                  │
            └──────────────────┼──────────────────┘
                               ▼
                       CANDIDATE EVENT BUS
                               │
                               ▼
                       MULTIMODAL ANALYZER
                               │
                ┌──────────────┼──────────────┐
                │              │              │
             SEMANTICS       AFFECT        TEMPORAL
                │              │              │
                └──────────────┼──────────────┘
                               ▼
                        VIRALITY ENGINE
                               │
                               ▼
                          TREND GRAPH
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
              ROUTER                    SYNTHESIS FABRIC
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                          ACCOUNT QUEUE
                               │
                               ▼
                        PUBLISHER WORKERS
                               │
                               ▼
                        PLATFORM ADAPTERS
                               │
                               ▼
                         RESPONSE METRICS
                               │
                               ▼
                         LEARNING SYSTEM
```

---

## 4. Functional Divisions / Emergent Roles

These are functional roles, not necessarily permanent agent processes.

### 4.1 Director

Responsibilities:

- translate global strategy into objectives,
- allocate research and compute budget,
- set exploration/exploitation ratios,
- detect under-served niches,
- create or retire account proposals,
- monitor system health,
- arbitrate conflicts between growth, diversity, novelty, cost, and risk.

The Director should operate at a slower cadence than individual Scouts.

### 4.2 Discovery Fabric

The Discovery Fabric contains many specialized discovery behaviors:

- **Search Scout** — broad web/search discovery.
- **Platform Scout** — queries supported platform search/discovery interfaces.
- **Creator Scout** — watches specific creators or source lists.
- **Breakout Scout** — detects anomalous engagement velocity.
- **Cross-Platform Scout** — detects themes moving between platforms.
- **Archive Scout** — searches reusable archives and public-domain/owned libraries.
- **Semantic Scout** — searches by account concept rather than literal keywords.
- **Trend Clusterer** — groups large numbers of candidates into emerging concepts.
- **Source Scout** — discovers new high-yield sources.
- **Gap Scout** — finds categories producing high-quality candidates that currently have no matching account.

Scouts create candidate objects; they do not directly publish.

### 4.3 Multimodal Analysis Fabric

The analyzer converts raw media into structured representations:

- frame embeddings,
- audio features,
- speech transcript,
- on-screen text,
- scene boundaries,
- motion intensity,
- faces/objects/scenes as generic semantic features,
- event descriptions,
- affect/arousal estimates,
- novelty estimates,
- temporal saliency,
- metadata and source history.

The result is a machine-readable **Content Genome**.

### 4.4 Synthesis Fabric

This is the key creative division added in v0.1.

Its purpose is not merely to repost a found item. It converts discovered material, permitted source material, or a discovered *idea/motif* into new editorial products optimized for a target audience.

Subroles:

- **Highlight Miner** — identifies salient moments inside longer videos.
- **Atomizer** — cuts long candidates into semantically meaningful micro-segments.
- **Motif Detector** — identifies reusable structures such as reveal, rescue, escalation, transformation, spectacle, incongruity, or satisfying closure.
- **Story Architect** — chooses atom order and narrative structure.
- **Composer** — splices selected atoms and original/generated assets into a coherent short.
- **Variant Generator** — produces multiple duration, pacing, crop, caption, and opening variants.
- **Bridge Generator** — creates original transitions, graphics, captions, voice-over, or synthetic B-roll where useful.
- **Retention Critic** — estimates dead time, payoff latency, repetition, confusing cuts, and likely abandonment points.
- **Loop Designer** — creates seamless or conceptually satisfying loops when appropriate.
- **Quality Controller** — verifies visual/audio continuity and account alignment.

The Synthesis Fabric may exist as one orchestration graph rather than named persistent agents.

### 4.5 Router

The Router answers:

> Which eligible account, if any, is this candidate or composition most valuable for?

It operates on account-specific fit, not a universal viral score.

### 4.6 Publishers

Publishers are stateless workers that load the selected account identity/session and execute a deterministic publishing action.

### 4.7 Evaluators / Scientists

These jobs:

- analyze post-level outcomes,
- estimate which features mattered,
- update account models,
- compare variants,
- detect overfitting or content fatigue,
- recommend experiments,
- measure system-level health.

---

## 5. Core Data Objects

### 5.1 Candidate

```yaml
Candidate:
  id: string
  discovered_by: agent_or_source_id
  discovered_at: datetime
  source:
    platform: string
    url: string
    creator_id: string|null
    creator_name: string|null
    published_at: datetime|null
  media:
    type: video|image|text|article|audio
    local_asset_ref: string|null
    duration_seconds: float|null
  semantics:
    description: string
    categories: map[string,float]
    embedding_ref: string
  affect:
    arousal: float
    valence: float
    emotions: map[string,float]
  social:
    views: int|null
    likes: int|null
    comments: int|null
    shares: int|null
    velocity_features: map
  quality:
    visual: float
    audio: float
    originality: float
    novelty: float
  provenance:
    confidence: float
    status: owned|permission|licensed|public_domain|unknown|restricted
  dedupe:
    perceptual_hash: string|null
    nearest_candidate_ids: list
    duplicate_probability: float
  state: discovered|analyzed|routed|held|composed|published|archived
```

### 5.2 Content Atom

A Content Atom is a temporally localized, semantically coherent unit extracted from a video.

```yaml
ContentAtom:
  id: string
  candidate_id: string
  start: float
  end: float
  duration: float
  transcript: string|null
  semantic_embedding_ref: string
  event_label: string
  motif_labels: list[string]
  saliency: float
  arousal: float
  novelty: float
  payoff_score: float
  setup_dependency: float
  continuity_features: map
```

Typical motifs:

- hook,
- reveal,
- escalation,
- payoff,
- near-miss,
- transformation,
- rescue,
- spectacle,
- satisfying completion,
- surprise,
- incongruity,
- emotional reaction,
- before/after,
- loopable motion.

### 5.3 Composition

```yaml
Composition:
  id: string
  account_id: string
  source_candidate_ids: list[string]
  atom_ids: list[string]
  original_assets: list[string]
  generated_assets: list[string]
  edit_plan:
    target_duration: float
    aspect_ratio: string
    opening_strategy: string
    atom_order: list[string]
    caption_strategy: string
    audio_strategy: string
  predicted:
    retention: float
    shareability: float
    account_fit: float
    novelty: float
  provenance_summary: map
  variants: list[string]
  status: draft|review|approved|published|rejected
```

### 5.4 Account

```yaml
Account:
  id: string
  platform: string
  public_identity: map
  credentials_ref: secret_ref
  session_ref: string|null
  niche_description: string
  semantic_centroid_ref: string
  desired_affect: map
  voice_profile: map
  posting_constraints: map
  audience_genome_ref: string
  source_preferences: map
  active: bool
```

### 5.5 Audience Genome

An account-specific learned representation:

```yaml
AudienceGenome:
  account_id: string
  semantic_preferences: vector
  affect_preferences: vector
  motif_preferences: map
  duration_response_curve: map
  opening_response_curve: map
  pacing_response_curve: map
  posting_time_response: map
  caption_response: map
  source_response: map
  novelty_tolerance: float
  topic_saturation: map
  updated_at: datetime
```

---

## 6. Discovery and Trend Theory

### 6.1 Candidate discovery is broad

The system intentionally over-collects at the discovery stage and becomes selective later.

### 6.2 Breakout is relative

Raw popularity is insufficient.

A candidate should receive a **breakout score** based on:

```text
creator-normalized velocity
× freshness
× engagement mix
× acceleration
× cross-platform confirmation
× source credibility
```

Example conceptual metric:

```text
relative_velocity =
    observed_engagement_velocity
    / expected_velocity_for_creator_or_source
```

A video with 20k views from a creator whose normal first-hour result is 600 may be more interesting than a week-old video with millions of views.

### 6.3 Trend clusters

Candidates are embedded and clustered into emerging themes. A trend object tracks:

- member candidates,
- semantic centroid,
- rate of new-member arrival,
- platform distribution,
- creator distribution,
- age,
- engagement acceleration,
- saturation,
- suitable accounts.

---

## 7. Virality and Content-Value Theory

No single “viral score” should control the system.

### 7.1 Feature families

**Semantic**
- topic,
- entities,
- visual concepts,
- narrative structure.

**Affective**
- arousal,
- valence,
- awe,
- surprise,
- humor,
- anxiety/tension,
- anger,
- joy,
- sadness.

**Temporal**
- time-to-first-payoff,
- highlight density,
- dead-time ratio,
- motion/change density,
- setup-to-payoff distance.

**Social**
- view velocity,
- share rate,
- comment rate,
- creator-normalized anomaly,
- cross-platform replication.

**Production**
- visual quality,
- audio clarity,
- cropability,
- subtitle needs,
- re-editability.

**Account-relative**
- niche fit,
- audience genome fit,
- novelty,
- recent-topic saturation,
- motif fatigue,
- posting cadence fit.

### 7.2 Research grounding

The system adopts these principles from prior research:

- high-arousal emotion can increase sharing, but valence alone is insufficient;
- video popularity is multimodal;
- highlight detection can be modeled as temporal saliency rather than hand-written rules;
- watch time is useful but biased by video length, so completion/relative retention must also be modeled;
- content length should be learned per context rather than universally minimized.

---

## 8. Routing Model

Initial heuristic:

```text
RouteValue(candidate, account) =

  w1 * semantic_fit
+ w2 * audience_history_fit
+ w3 * affect_fit
+ w4 * predicted_retention
+ w5 * predicted_shareability
+ w6 * freshness
+ w7 * breakout_signal
+ w8 * novelty
+ w9 * provenance_confidence

- p1 * duplicate_probability
- p2 * topic_saturation
- p3 * recent_similarity
- p4 * quality_penalty
- p5 * operational_risk
```

Weights become account-specific over time.

### 8.1 Route states

- `DIRECT_PUBLISH_CANDIDATE`
- `SEND_TO_SYNTHESIS`
- `HUMAN_REVIEW`
- `REFERENCE_ONLY`
- `ARCHIVE`
- `NO_MATCH`
- `PROPOSE_NEW_ACCOUNT`

---

## 9. The Synthesis Fabric in Detail

### 9.1 Objective

Transform long, diffuse, or multi-source material into compact media that preserves the strongest attention-relevant and meaning-relevant moments.

**The objective is not simply shortening.**

The objective is:

```text
maximize:
    meaningful_information_per_second
    salient_event_density
    early-interest probability
    payoff strength
    continuity
    emotional trajectory
    rewatchability
    account fit

minimize:
    dead time
    redundant setup
    unexplained cuts
    context loss
    repetition
    visual discontinuity
```

### 9.2 Highlight extraction

For each source video:

1. segment into scenes/shots;
2. sample frames/audio/transcript;
3. compute query-conditioned saliency;
4. estimate emotion/arousal over time;
5. identify semantic event boundaries;
6. identify setup/payoff relationships;
7. create Content Atoms.

The Highlight Miner creates a temporal curve:

```text
time  ──────────────────────────────────────────►

saliency
  1.0          ▲          ▲▲              ▲
               │         ▲  ▲            ▲ ▲
  0.5     ▲   ▲│   ▲    ▲    ▲     ▲    ▲   ▲
         ▲ ▲ ▲ │  ▲ ▲  ▲      ▲   ▲ ▲
  0.0 ──────────────────────────────────────────
```

The system does not automatically choose only the highest independent peaks, because a payoff may require preceding setup.

### 9.3 Viral-aspect isolation

The system learns which moments repeatedly predict response.

A “viral aspect” can be represented as:

```yaml
ViralMotif:
  semantic_pattern: embedding
  temporal_role: hook|setup|escalation|payoff|closure
  affect_profile: vector
  motion_profile: vector
  audio_profile: vector
  observed_outcome_distribution: map
```

This allows the swarm to learn patterns such as:

- “unexpected reveal after 1–2 seconds of ambiguity,”
- “large-scale physical spectacle,”
- “rapid before/after transformation,”
- “animal-human interaction with visible payoff,”
- “near-failure followed by recovery,”
- “visually satisfying completion.”

These are learned correlations, not hard-coded universal truths.

### 9.4 Composition strategies

The system may generate:

**A. Compression**
- One source, dead time removed, salient interval retained.

**B. Multi-highlight montage**
- Several highlights from one source.

**C. Multi-source thematic montage**
- Several permitted/owned clips around one motif.

**D. Commentary transformation**
- Short excerpts + original narration/analysis/graphics.

**E. Comparative composition**
- Two or more clips showing contrast/evolution.

**F. Generative bridge**
- Real/source atoms joined by original generated transitions, diagrams, maps, title cards, or illustrative synthetic B-roll.

**G. Concept recreation**
- When source provenance is unsuitable for direct reuse, preserve the *idea/motif* but build the output from owned/licensed/generated material.

### 9.5 Variant generation

For each promising composition, create a small variant family:

```text
Variant A: 8 s / immediate payoff
Variant B: 14 s / 2 s setup
Variant C: 23 s / context + payoff
Variant D: 14 s / different opening
Variant E: 14 s / alternate atom order
```

The system learns rather than assuming the shortest version will win.

### 9.6 Automated editing stack

A practical first implementation can use deterministic tools:

- FFmpeg for cutting/concatenation/transcoding,
- scene detection,
- frame sampling,
- speech-to-text,
- crop/reframe,
- loudness normalization,
- subtitles/text layers,
- simple motion/zoom,
- aspect-ratio conversion.

Generative video editing is an optional later layer and should not be required for V1.

---

## 10. Provenance / Rights / Policy Routing

The project should be **productive under uncertainty**, not paralyzed by it.

### 10.1 Two independent questions

1. **Is this candidate useful intelligence?**
2. **Is this exact asset ready for automatic publishing?**

These must never be collapsed into one boolean.

### 10.2 Provenance states

- `OWNED`
- `CREATOR_PERMISSION`
- `LICENSED`
- `PUBLIC_DOMAIN`
- `UNKNOWN`
- `RESTRICTED`

### 10.3 Downstream policy

Unknown/restricted material may still be used for:

- trend analysis,
- semantic embedding,
- motif extraction,
- highlight research,
- source intelligence,
- editorial ideation,
- account matching,
- generating a new original concept,
- human review.

Automatic reuse of the exact asset is a distinct route.

This keeps the intelligence system high-recall without making “anything found online is automatically publishable” an architectural assumption.

---

## 11. Learning System

### 11.1 Metrics

Per post:

- impressions,
- views,
- watch time,
- completion rate,
- replay/loop rate where available,
- shares,
- saves,
- likes,
- comments,
- profile visits,
- follows,
- unfollows,
- clickthrough,
- moderation or failure events.

Derived:

```text
share_rate
follow_conversion_per_1k_impressions
watch_fraction
completion_adjusted_for_duration
engagement_velocity
retention_curve
account_growth_efficiency
```

### 11.2 Account-specific learning

Every result updates the Audience Genome.

The system should learn:

- which semantic clusters work,
- which affect profiles work,
- which motifs work,
- ideal duration distribution,
- acceptable setup length,
- opening styles,
- content fatigue,
- optimal source diversity,
- post timing.

### 11.3 Exploration versus exploitation

Use a conservative contextual-bandit-style policy:

- mostly exploit known high-value regions;
- reserve a controlled fraction for adjacent unexplored content;
- log each experiment and its context.

V1 can use simple epsilon-greedy or Thompson-style logic before any sophisticated model is trained.

---

## 12. Shared Memory

### 12.1 Candidate Memory
“Have we seen this or a near-duplicate?”

### 12.2 Source Memory
“What does this creator/source reliably produce?”

### 12.3 Account Memory
“What historically works for this audience?”

### 12.4 Trend Memory
“How did this concept move through platforms over time?”

### 12.5 Motif Memory
“What temporal/emotional patterns recur in successful clips?”

### 12.6 Experiment Memory
“What variants have already been tested?”

### 12.7 Operational Memory
“What integrations fail, rate-limit, or require intervention?”

---

## 13. Scheduling and Physical Execution

AI-Manus supplies:

- agent planning/execution,
- sandboxed tools,
- browser control,
- search,
- MongoDB,
- Redis,
- background tasks,
- distributed Celery workers,
- VNC browser inspection.

Manu-Swarm adds a domain-specific queue over those capabilities.

### 13.1 Queue classes

```text
DISCOVER
FETCH_METADATA
ANALYZE_TEXT
ANALYZE_VIDEO
EMBED
TRANSCRIBE
CLUSTER
ROUTE
ATOMIZE
COMPOSE
RENDER
REVIEW
PUBLISH
COLLECT_METRICS
UPDATE_MODEL
```

### 13.2 Worker classes

- browser worker,
- lightweight network worker,
- CPU media worker,
- GPU analysis worker,
- LLM reasoning worker,
- render worker,
- publisher worker.

A worker is not permanently attached to an account.

---

## 14. Account Creation as an Emergent Capability

The system can detect **orphan demand**:

```text
high-quality candidate cluster
+ persistent discovery volume
+ high predicted engagement
+ no existing account fit
```

It can generate a `NewAccountProposal` containing:

- proposed niche,
- candidate backlog,
- estimated source volume,
- account differentiation,
- initial posting strategy,
- evidence from existing account response.

Account creation remains human-approved in early versions.

---

## 15. System-Level Objectives

A suggested global reward model:

```text
SystemUtility =

  growth_value
+ retention_value
+ sharing_value
+ audience_fit
+ content_novelty
+ source_diversity
+ learning_value

- duplication
- audience_fatigue
- low_quality
- operational_cost
- moderation_failure
- provenance_risk
```

No one term should dominate by default.

---

## 16. Anti-Patterns

Do not design the project around:

- one browser per account permanently,
- one LLM per account permanently,
- asking an LLM to manually click every publishing step,
- maximizing raw views alone,
- treating all short videos as better than long ones,
- treating all discovered media as publishable,
- discarding all uncertain media before intelligence extraction,
- posting near-identical content across many accounts,
- using a single universal “viral score.”

---

## 17. V1 Research Prototype

### Goal

Prove that the intelligence pipeline works before integrating production posting.

### Inputs

- 3–5 test account profiles.
- 50–500 discovered candidates/day.
- At least two discovery methods.

### V1 Pipeline

```text
discover
  ↓
normalize
  ↓
deduplicate
  ↓
analyze
  ↓
atomize videos
  ↓
cluster trends
  ↓
score
  ↓
route
  ↓
optionally synthesize
  ↓
dashboard
```

### V1 Dashboard should show

- candidate stream,
- source,
- trend cluster,
- breakout score,
- emotion/arousal profile,
- highlight timeline,
- extracted Content Atoms,
- best matching accounts,
- reasons for routing,
- synthesis proposal,
- provenance state,
- predicted value,
- human accept/reject.

No real account credentials are required for this milestone.

---

## 18. V2

Add:

- media renderer,
- composition variants,
- draft queue,
- platform adapter for one platform,
- human approval mode,
- metrics ingestion,
- Audience Genome updates.

---

## 19. V3

Add:

- multi-platform routing,
- distributed workers,
- contextual exploration,
- automatic composition experiments,
- source discovery,
- trend propagation graph,
- new-account proposals.

---

## 20. Research Foundations

The theory is informed by these research areas:

- affect and social transmission: high-arousal emotion and sharing;
- multimodal popularity prediction for short-form video;
- video moment retrieval and highlight detection;
- temporal video-language grounding and summarization;
- watch-time modeling and video-length bias;
- contextual bandits for adaptive ranking;
- diffusion/video-editing research for later generative layers.

Important references include:

- Berger & Milkman (2012), *What Makes Online Content Viral?*
- Moon et al. (CVPR 2023), *Query-Dependent Video Representation for Moment Retrieval and Highlight Detection*
- Lin et al. (ICCV 2023), *UniVTG: Towards Unified Video-Language Temporal Grounding*
- Han et al. (CVPR Workshops 2024), *Unleash the Potential of CLIP for Video Highlight Detection*
- Xiao et al. (CVPR 2024), *Bridging the Gap: A Unified Video Comprehension Framework for Moment Retrieval and Highlight Detection*
- AMPS (2024), multimodal popularity prediction for short-form video
- Nishimura et al. (EMNLP 2024), *Lighthouse*
- Wang et al. (ICML 2024), adaptive select/rank in online platforms
- Feng et al. (CVPR 2024), *CCEdit*
- Wu et al. (CVPR 2024), *Fairy*

---

## 21. Theory Freeze: Core Invariants

The following should be treated as architectural commitments unless later evidence disproves them:

1. Accounts, agents, and workers are separate entities.
2. Discovery and publish eligibility are separate.
3. Every candidate becomes structured state.
4. Video is decomposed into Content Atoms before advanced synthesis.
5. Routing is account-relative.
6. The system learns duration/pacing instead of assuming “shorter wins.”
7. Synthesis is a first-class subsystem, not an afterthought.
8. Generative media augments deterministic editing; it does not replace it in V1.
9. Shared memory prevents duplicate work and makes the swarm cumulative.
10. The system is judged by long-run audience/account value, not only post-level views.
